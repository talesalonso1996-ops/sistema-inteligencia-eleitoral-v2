"""Analise geografica: local de votacao -> setor censitario / bairro
(secao 8 e 9 do briefing).

Fluxo:
1. Coordenadas de cada local de votacao vem do arquivo nacional
   eleitorado_local_votacao_2024.csv (TSE) - chave (CD_MUNICIPIO, NR_ZONA,
   NR_LOCAL_VOTACAO).
2. Os votos por local (agregados a partir de votos_da_candidatura /
   votos_da_disputa) sao unidos a essas coordenadas.
3. Um join espacial (ponto-em-poligono) com as malhas IBGE CD2022
   (SP_setores_CD2022.gpkg / SP_bairros_CD2022.gpkg) atribui setor
   censitario e bairro oficiais a cada local de votacao.

O codigo de municipio do TSE (CD_MUNICIPIO) e diferente do codigo IBGE
(CD_MUN) usado nas malhas - a compatibilizacao e feita pelo NOME do
municipio (maiusculo, sem acento), unico dentro de uma UF.
"""
from __future__ import annotations

import unicodedata

import duckdb
import geopandas as gpd
import pandas as pd

from .candidate_finder import Candidatura
from .cep_lookup import bairros_por_ceps
from .uf_data_bootstrap import caminho_malha, garantir_malha_uf
from .utils import cache_key, crs_metrico_utm, data_sources, get_logger, read_cache, resolve_path, write_cache

_DISTANCIA_MAXIMA_FALLBACK_M = 2000  # limite para o fallback de poligono mais proximo

logger = get_logger(__name__)

# As 27 UFs do Brasil - usado apenas para validar a entrada (nao ha uma
# lista de "UFs com malha disponivel": a malha de qualquer UF e baixada sob
# demanda do IBGE via uf_data_bootstrap; se a UF nao existir ou o IBGE nao
# tiver publicado a malha, o bootstrap falha graciosamente e o sistema
# reporta a limitacao, sem simular dados (secao 19 do briefing).
_UFS_BRASIL = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}


def _normalizar_nome(texto: str) -> str:
    """Remove acentos e normaliza caixa - usado para casar nomes de
    municipio entre TSE e IBGE, que usam grafias/acentuacao diferentes."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return sem_acento.strip().upper()


def uf_tem_malha_completa(uf: str) -> bool:
    """Verifica se a UF e valida (a malha em si e baixada sob demanda - ver
    uf_data_bootstrap.garantir_malha_uf - nao ha mais uma lista fixa de UFs
    com malha "disponivel": qualquer UF real do Brasil pode ser buscada)."""
    return uf.upper() in _UFS_BRASIL


def _caminho(caminho: str) -> str:
    path = caminho if (len(caminho) > 1 and caminho[1] == ":") else str(resolve_path(caminho))
    return path.replace("\\", "/")


def carregar_coordenadas_locais(candidatura: Candidatura) -> pd.DataFrame:
    """Carrega lat/long + bairro (auto-declarado pelo TSE) de cada local de
    votacao do municipio da candidatura, a partir do arquivo nacional de
    eleitorado por local de votacao.

    O arquivo original tem uma linha por SECAO (varias secoes podem
    funcionar no mesmo predio/local, todas com a mesma coordenada) -
    agregamos aqui para uma linha por (zona, local de votacao), senao um
    local com N secoes apareceria N vezes nas etapas seguintes (inflando
    artificialmente contagens de votos por bairro/territorio).

    Tambem traz `cep` (NR_CEP, oficial do TSE) - usado como fallback para
    descobrir o bairro via consulta de CEP quando o municipio nao tem
    malha de bairro do IBGE (ver src/cep_lookup.py)."""
    key = cache_key("coordenadas_locais_v2", candidatura.codigo_municipio_tse)
    cached = read_cache("geographic_analysis", key)
    if cached is not None:
        return cached

    fonte = data_sources()["tse"]["eleitorado_local_votacao"]
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='2GB'")
    caminho = _caminho(fonte["arquivo_local"])
    origem = (
        f"read_parquet('{caminho}')"
        if caminho.lower().endswith(".parquet")
        else f"read_csv('{caminho}', delim='{fonte['separador']}', header=true, quote='\"', "
             f"encoding='{fonte['encoding']}', ignore_errors=true)"
    )
    sql = f"""
        SELECT
            NR_ZONA, NR_LOCAL_VOTACAO,
            ANY_VALUE(NM_LOCAL_VOTACAO) AS NM_LOCAL_VOTACAO,
            ANY_VALUE(NM_BAIRRO) AS NM_BAIRRO,
            ANY_VALUE(NR_CEP) AS cep,
            ANY_VALUE(TRY_CAST(NR_LATITUDE AS DOUBLE)) AS latitude,
            ANY_VALUE(TRY_CAST(NR_LONGITUDE AS DOUBLE)) AS longitude
        FROM {origem}
        WHERE CD_MUNICIPIO = {candidatura.codigo_municipio_tse}
        GROUP BY NR_ZONA, NR_LOCAL_VOTACAO
    """
    df = con.execute(sql).fetchdf()
    df = df.dropna(subset=["latitude", "longitude"])
    df = df[df["latitude"].between(-34, 6) & df["longitude"].between(-74, -28)]
    write_cache("geographic_analysis", key, df)
    return df


def juntar_votos_com_coordenadas(
    votos_candidatura: pd.DataFrame, coordenadas: pd.DataFrame
) -> pd.DataFrame:
    """Agrega votos do candidato por local de votacao (predio fisico) e
    junta com as coordenadas correspondentes (chave: NR_ZONA +
    NR_LOCAL_VOTACAO). Usado para os MAPAS (Geografia: pontos, coropletico,
    Voronoi) - a unidade certa ali e o predio (ponto no mapa), nao a secao
    (varias secoes de um mesmo predio tem a mesma coordenada, entao nao
    fariam sentido como pontos distintos no mapa).

    Cria `local_votacao_id`: identificador unico e legivel do local de
    votacao (nome + zona + numero do local). Para a unidade de observacao
    da regressao/clusterizacao/Maslow, ver juntar_votos_com_coordenadas_secao
    (mais granular - por secao, nao por predio)."""
    votos_local = (
        votos_candidatura.groupby(["NR_ZONA", "NR_LOCAL_VOTACAO"], as_index=False)["QT_VOTOS"]
        .sum()
        .rename(columns={"QT_VOTOS": "votos_candidato"})
    )
    out = votos_local.merge(coordenadas, on=["NR_ZONA", "NR_LOCAL_VOTACAO"], how="left")
    sem_coordenada = int(out["latitude"].isna().sum())
    if sem_coordenada:
        logger.warning(
            "%s de %s locais de votacao sem coordenada disponivel", sem_coordenada, len(out)
        )
    out["local_votacao_id"] = _local_votacao_id(out)
    return out


def _local_votacao_id(df: pd.DataFrame) -> pd.Series:
    nome_local = df["NM_LOCAL_VOTACAO"].fillna("LOCAL SEM NOME").astype(str)
    return nome_local + " (Zona " + df["NR_ZONA"].astype(str) + ", Local " + df["NR_LOCAL_VOTACAO"].astype(str) + ")"


def juntar_votos_com_coordenadas_secao(
    votos_candidatura: pd.DataFrame, coordenadas: pd.DataFrame
) -> pd.DataFrame:
    """Como juntar_votos_com_coordenadas, mas SEM agregar as secoes de um
    mesmo local de votacao - cada linha aqui e uma secao eleitoral (urna),
    nao um predio inteiro. Esta e a unidade de observacao da regressao/
    clusterizacao/Maslow: um local de votacao tem em media varias secoes,
    entao usar secao como unidade multiplica o numero de observacoes
    disponiveis para a analise estatistica - essencial em municipios
    pequenos, onde o numero de PREDIOS sozinho pode ficar abaixo do minimo
    recomendado pela regressao (ver src/regression_models.py).

    ATENCAO: todas as secoes de um mesmo predio compartilham a MESMA
    coordenada e portanto o MESMO perfil demografico do setor censitario -
    nao sao observacoes geograficas independentes, so o voto de cada secao
    e realmente distinto. Por isso a regressao usa erro-padrao robusto a
    cluster, agrupado por `local_votacao_id` (o predio fisico) - sem essa
    correcao, a precisao dos coeficientes seria superestimada."""
    votos_secao = (
        votos_candidatura.groupby(["NR_ZONA", "NR_LOCAL_VOTACAO", "NR_SECAO"], as_index=False)["QT_VOTOS"]
        .sum()
        .rename(columns={"QT_VOTOS": "votos_candidato"})
    )
    out = votos_secao.merge(coordenadas, on=["NR_ZONA", "NR_LOCAL_VOTACAO"], how="left")
    sem_coordenada = int(out["latitude"].isna().sum())
    if sem_coordenada:
        logger.warning(
            "%s de %s secoes sem coordenada disponivel (local de votacao correspondente sem coordenada)",
            sem_coordenada, len(out),
        )
    out["local_votacao_id"] = _local_votacao_id(out)
    out["secao_id"] = out["local_votacao_id"] + " - Secao " + out["NR_SECAO"].astype(str)
    return out


def carregar_malha(tipo: str, municipio: str, uf: str) -> gpd.GeoDataFrame | None:
    """Carrega a malha de 'setores' ou 'bairros' (CD2022) da UF informada,
    baixando/convertendo sob demanda (uf_data_bootstrap) na primeira vez que
    a UF for necessaria, e filtra para o municipio pedido."""
    garantir_malha_uf(uf)
    path = str(caminho_malha(tipo, uf))

    if not caminho_malha(tipo, uf).exists():
        logger.warning("Malha '%s' da UF '%s' nao encontrada em %s", tipo, uf, path)
        return None
    municipio_norm = _normalizar_nome(municipio)
    # Carrega tudo e filtra em pandas normalizando acento/caixa dos dois
    # lados (nome do TSE pode vir grafado de forma diferente do IBGE).
    gdf = gpd.read_parquet(path)
    gdf = gdf[gdf["NM_MUN"].apply(_normalizar_nome) == municipio_norm]
    if gdf.empty:
        logger.warning(
            "Nenhum poligono encontrado para o municipio '%s' (normalizado: '%s') em %s/%s",
            municipio, municipio_norm, uf, tipo,
        )
        return None
    return gdf


def carregar_fronteira_municipio(candidatura: Candidatura) -> gpd.GeoDataFrame | None:
    """Retorna uma malha poligonal cobrindo o municipio inteiro (bairros,
    ou setores censitarios como alternativa), usada para recortar o
    diagrama de Voronoi nos limites reais do municipio."""
    malha = carregar_malha("bairros", candidatura.municipio, candidatura.uf)
    if malha is None:
        malha = carregar_malha("setores", candidatura.municipio, candidatura.uf)
    return malha


def _sjoin_within_com_fallback_proximo(
    gdf_pontos: gpd.GeoDataFrame, malha: gpd.GeoDataFrame, colunas: list[str],
) -> gpd.GeoDataFrame:
    """Point-in-polygon (predicate=within); para pontos que nao caem em
    NENHUM poligono da malha (comum perto de bordas - imprecisao da propria
    coordenada do local de votacao ou do desenho da malha oficial do IBGE,
    nao necessariamente um erro), tenta o poligono mais proximo, contanto
    que a distancia seja pequena (ate `_DISTANCIA_MAXIMA_FALLBACK_M`) - para
    nao arriscar atribuir um bairro/setor errado a um ponto genuinamente
    fora do municipio. Retorna "nao identificado" (nao inventa) quando nem
    o poligono mais proximo estiver dentro dessa distancia."""
    malha_geo = malha.to_crs(gdf_pontos.crs)
    unido = gpd.sjoin(
        gdf_pontos, malha_geo[colunas + ["geometry"]], how="left", predicate="within",
    ).drop(columns=["index_right"], errors="ignore")

    sem_match = unido[colunas[0]].isna()
    if not sem_match.any():
        return unido

    crs_metros = crs_metrico_utm(gdf_pontos.geometry.x.mean())
    pontos_sem_match = gdf_pontos.loc[sem_match, ["geometry"]].to_crs(crs_metros)
    malha_metros = malha_geo.to_crs(crs_metros)
    proximo = gpd.sjoin_nearest(
        pontos_sem_match, malha_metros[colunas + ["geometry"]],
        how="left", max_distance=_DISTANCIA_MAXIMA_FALLBACK_M, distance_col="_dist_fallback",
    )
    proximo = proximo[~proximo.index.duplicated(keep="first")]  # empate de distancia (raro)

    for col in colunas:
        # .astype(object) evita erro de tipagem estrita de colunas com
        # dtype de string do Arrow (pandas >= 2 com backend pyarrow) ao
        # preencher com os valores recuperados via fallback.
        unido[col] = unido[col].astype(object)
        unido.loc[sem_match, col] = unido.loc[sem_match].index.map(proximo[col])

    recuperados = int(proximo[colunas[0]].notna().sum())
    if recuperados:
        logger.info(
            "%s de %s pontos sem match direto no join espacial recuperados via "
            "poligono mais proximo (ate %.0fm de distancia).",
            recuperados, int(sem_match.sum()), _DISTANCIA_MAXIMA_FALLBACK_M,
        )
    return unido


_MAX_CEPS_POR_CONSULTA = 300  # limite de consultas ViaCEP (servico externo, sequencial) por chamada
_MIN_DISTRITOS_PARA_PULAR_CEP = 10  # distritos suficientes para dispensar o fallback via CEP


def _preencher_bairro_via_cep(gdf_pontos: gpd.GeoDataFrame, sem_bairro: pd.Series) -> tuple[int, bool]:
    """Para locais sem bairro atribuido pelo join espacial, tenta resolver
    via CEP (oficial do TSE) consultando o ViaCEP - ver cep_lookup.py.
    Preenche NM_BAIRRO_IBGE in-place para os que forem resolvidos. Retorna
    (quantos locais foram recuperados, se algum CEP ficou de fora por
    exceder o limite de consultas NOVAS por chamada - CEPs ja cacheados de
    analises anteriores nao contam para esse limite, entao nao trava a
    analise so por o municipio ter muitos locais, apenas quando ha muitos
    CEPs REALMENTE novos de uma vez)."""
    ceps_a_consultar = gdf_pontos.loc[sem_bairro, "cep"].dropna().unique().tolist()
    if not ceps_a_consultar:
        return 0, False

    bairro_por_cep = bairros_por_ceps(ceps_a_consultar, max_novas_consultas=_MAX_CEPS_POR_CONSULTA)
    ceps_validos = [c for c in ceps_a_consultar if len("".join(ch for ch in str(c) if ch.isdigit())) == 8]
    limite_excedido = len(bairro_por_cep) < len(ceps_validos)
    if not any(bairro_por_cep.values()):
        return 0, limite_excedido

    gdf_pontos["NM_BAIRRO_IBGE"] = gdf_pontos["NM_BAIRRO_IBGE"].astype(object)
    mapeado = gdf_pontos.loc[sem_bairro, "cep"].map(bairro_por_cep)
    gdf_pontos.loc[sem_bairro, "NM_BAIRRO_IBGE"] = mapeado
    return int(mapeado.notna().sum()), limite_excedido


def atribuir_setor_e_bairro(
    pontos: pd.DataFrame, candidatura: Candidatura
) -> tuple[pd.DataFrame, list[str]]:
    """Faz o join espacial ponto-em-poligono dos locais de votacao com as
    malhas de setor censitario e bairro (CD2022). Retorna o dataframe
    enriquecido e uma lista de avisos/limitacoes encontradas."""
    avisos: list[str] = []
    if not uf_tem_malha_completa(candidatura.uf):
        avisos.append(
            f"Malha geografica (setor censitario/bairro) nao configurada para a UF "
            f"'{candidatura.uf}'. Analises espaciais nao serao geradas."
        )
        return pontos, avisos

    sem_coordenada = pontos[pontos["latitude"].isna() | pontos["longitude"].isna()]
    validos = pontos.dropna(subset=["latitude", "longitude"])
    if validos.empty:
        avisos.append("Nenhum local de votacao com coordenadas validas para join espacial.")
        return pontos, avisos

    gdf_pontos = gpd.GeoDataFrame(
        validos,
        geometry=gpd.points_from_xy(validos["longitude"], validos["latitude"]),
        crs="EPSG:4674",
    )

    setores = carregar_malha("setores", candidatura.municipio, candidatura.uf)
    if setores is not None:
        gdf_pontos = _sjoin_within_com_fallback_proximo(
            gdf_pontos, setores, ["CD_SETOR", "CD_BAIRRO", "NM_DIST"]
        )
    else:
        avisos.append(
            f"Malha de setores censitarios sem poligonos para o municipio "
            f"'{candidatura.municipio}' - setor censitario nao sera atribuido."
        )
        gdf_pontos["CD_SETOR"] = None
        gdf_pontos["NM_DIST"] = None

    bairros = carregar_malha("bairros", candidatura.municipio, candidatura.uf)
    if bairros is not None:
        bairros_renomeado = bairros.rename(columns={"NM_BAIRRO": "NM_BAIRRO_IBGE"})
        gdf_pontos = _sjoin_within_com_fallback_proximo(gdf_pontos, bairros_renomeado, ["NM_BAIRRO_IBGE"])
    else:
        gdf_pontos["NM_BAIRRO_IBGE"] = None

    # So vale a pena consultar CEP quando o distrito (fallback ja existente,
    # sem custo de rede) NAO da diferenciacao real - ex.: Goiania tem so 2
    # distritos para o municipio inteiro (praticamente tao inutil quanto 1
    # para fins de analise territorial), mas a capital de SP ja tem 96
    # distritos reais (nao precisa de CEP, e evita centenas/milhares de
    # consultas sequenciais a um servico externo so para reproduzir o que o
    # distrito ja da). _MIN_DISTRITOS_PARA_PULAR_CEP e uma regra pratica:
    # poucos distritos (ate 9) equivalem, na pratica, a nenhuma
    # diferenciacao territorial.
    distritos_distintos = gdf_pontos["NM_DIST"].nunique() if "NM_DIST" in gdf_pontos.columns else 0
    sem_bairro = gdf_pontos["NM_BAIRRO_IBGE"].isna()
    if sem_bairro.any() and "cep" in gdf_pontos.columns and distritos_distintos < _MIN_DISTRITOS_PARA_PULAR_CEP:
        recuperados_cep, limite_excedido = _preencher_bairro_via_cep(gdf_pontos, sem_bairro)
        if recuperados_cep:
            avisos.append(
                f"{recuperados_cep} locais de votacao sem bairro na malha oficial do IBGE tiveram "
                "o bairro resolvido via consulta de CEP (ViaCEP - servico de terceiros, nao e fonte "
                "oficial de governo como TSE/IBGE)."
            )
        if limite_excedido:
            avisos.append(
                "Numero de CEPs distintos sem bairro acima do limite por analise - fallback via CEP "
                "nao aplicado para todos os locais (usa apenas distrito/setor censitario)."
            )
        sem_bairro = gdf_pontos["NM_BAIRRO_IBGE"].isna()

    if bairros is None:
        # Alguns municipios (ex.: capital de SP) nao possuem "bairro" na
        # malha oficial CD2022 - usa "distrito" (NM_DIST, ja atribuido via
        # setores) como nivel territorial alternativo, mantendo o dado real
        # do IBGE em vez de reportar apenas uma limitacao. Locais ja
        # resolvidos via CEP acima nao entram neste aviso.
        avisos.append(
            f"Malha de bairros sem poligonos oficiais para o municipio "
            f"'{candidatura.municipio}' - usando 'distrito' (IBGE) como nivel "
            "territorial alternativo (ou bairro via CEP, quando disponivel), "
            "alem do bairro auto-declarado pelo TSE."
        )

    resultado = pd.DataFrame(gdf_pontos.drop(columns="geometry"))
    if not sem_coordenada.empty:
        # Locais sem coordenada nunca entram no join espacial, mas continuam
        # com votos reais - mantidos aqui (setor/bairro/distrito em branco)
        # para que nenhum voto desapareca silenciosamente dos totais
        # agregados por territorio (bairros_agg, regressao, clusterizacao
        # etc.), que meses depois passam a nao bater com o total oficial do
        # candidato.
        resultado = pd.concat([resultado, sem_coordenada], ignore_index=True, sort=False)
        votos_sem_coordenada = int(sem_coordenada["votos_candidato"].sum())
        avisos.append(
            f"{len(sem_coordenada)} locais de votacao ({votos_sem_coordenada} votos do candidato) "
            "sem coordenada geografica disponivel - aparecem nas analises por territorio como "
            "'nao identificado', nunca sao descartados dos totais."
        )

    faltantes = int(resultado["CD_SETOR"].isna().sum()) if "CD_SETOR" in resultado else len(resultado)
    faltantes_com_coordenada = faltantes - len(sem_coordenada)
    if faltantes_com_coordenada > 0:
        avisos.append(
            f"{faltantes_com_coordenada} de {len(resultado)} locais de votacao tinham coordenada "
            "mas nao caíram dentro de nenhum poligono de setor censitario (possivel erro de "
            "coordenada ou poligono desatualizado)."
        )
    return resultado, avisos


def total_votos_validos_por_territorio(
    votos_disputa: pd.DataFrame, pontos_com_territorio: pd.DataFrame, nivel: str
) -> pd.DataFrame:
    """Soma os votos validos de TODOS os candidatos da disputa por
    territorio (predio ou secao - ver `nivel`), reaproveitando o crosswalk
    ja calculado para o candidato-alvo (os mesmos locais de votacao fisicos
    servem todos os candidatos da disputa). Usado para calcular o
    percentual real de votos validos do candidato em cada territorio (nao
    apenas a participacao dentro dos proprios votos do candidato).

    A chave do crosswalk inclui NR_SECAO quando `pontos_com_territorio` tem
    essa coluna (nivel por secao/urna) - sem isso, o merge com `votos_disputa`
    (que tambem tem uma linha por secao) faria fan-out: uma secao do
    predio apareceria somada a todas as outras secoes do MESMO predio."""
    from .vote_filtering import votos_validos

    chave = ["NR_ZONA", "NR_LOCAL_VOTACAO"]
    if "NR_SECAO" in pontos_com_territorio.columns:
        chave = chave + ["NR_SECAO"]
    crosswalk = pontos_com_territorio[chave + [nivel]].drop_duplicates()
    validos = votos_validos(votos_disputa)
    com_territorio = validos.merge(crosswalk, on=chave, how="inner")
    return (
        com_territorio.groupby(nivel, as_index=False)["QT_VOTOS"]
        .sum()
        .rename(columns={"QT_VOTOS": "votos_validos_territorio"})
    )


def agregar_votos_por_bairro(pontos_com_bairro: pd.DataFrame, coluna_bairro: str = "NM_BAIRRO_IBGE") -> pd.DataFrame:
    """Agrega votos do candidato por territorio de bairro. Ordem de
    preferencia: bairro oficial IBGE (join espacial) -> distrito IBGE
    (quando o municipio nao tem malha de bairro, ex.: capital de SP) ->
    bairro auto-declarado pelo TSE (menos confiavel, mas melhor que nada)."""
    df = pontos_com_bairro.copy()
    if coluna_bairro not in df.columns:
        coluna_bairro = "NM_BAIRRO"
    candidatos_fallback = [coluna_bairro, "NM_DIST", "NM_BAIRRO"]
    df["_bairro_final"] = None
    for col in candidatos_fallback:
        if col in df.columns:
            df["_bairro_final"] = df["_bairro_final"].fillna(df[col])
    df["_bairro_final"] = df["_bairro_final"].fillna("BAIRRO NAO IDENTIFICADO")

    agregado = df.groupby("_bairro_final", as_index=False).agg(
        votos_candidato=("votos_candidato", "sum"),
        n_locais_votacao=("NR_LOCAL_VOTACAO", "nunique"),
    ).rename(columns={"_bairro_final": "bairro"})
    total = agregado["votos_candidato"].sum()
    agregado["pct_do_total_candidato"] = (
        100 * agregado["votos_candidato"] / total
    ).round(2) if total else 0.0
    return agregado.sort_values("votos_candidato", ascending=False).reset_index(drop=True)
