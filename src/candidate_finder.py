"""Localizacao automatica de candidaturas a partir do numero eleitoral, em
QUALQUER municipio/UF do Brasil.

Implementa o fluxo da secao 1 e 2 do briefing: o usuario informa apenas o
numero do candidato; o sistema cruza duas fontes oficiais do TSE via DuckDB:

- consulta_cand: identidade, partido, coligacao/federacao, situacao da
  candidatura e resultado final (eleito/nao eleito) - registro nacional,
  sem votos (arquivo leve, sempre disponivel - nao precisa de bootstrap
  por UF, ja cobre o Brasil inteiro);
- votacao_secao: votos por secao eleitoral - usado para o total de votos e
  como base de todas as demais analises. E' publicado pelo TSE por UF (um
  arquivo por estado, o maior deles com mais de 1GB) - por isso so e'
  baixado/convertido (ver uf_data_bootstrap.garantir_dados_uf) para as UFs
  onde o numero pesquisado realmente aparece no registro, nunca as 27 de
  uma vez.

Quando mais de uma candidatura e encontrada (mesmo numero em municipios,
cargos, UFs ou turnos diferentes), a decisao de qual usar cabe ao usuario -
este modulo apenas retorna as opcoes, nunca escolhe sozinho.

V2: as funcoes acima (Candidatura, buscar_candidaturas, votos_da_candidatura,
votos_da_disputa, registro_candidatos_disputa) permanecem EXATAMENTE como no
V1 - continuam cobrindo so a busca ampla por numero para cargos municipais
(2024), preservadas sem nenhuma mudanca de logica para nao arriscar
regressao. No final do arquivo foram ADICIONADAS funcoes generalizadas
(sufixo `_generalizado`/`buscar_candidatos_disputa`) que cobrem tambem
cargos estaduais/distritais (2022) via o novo fluxo guiado em cascata -
essas usam `src/rules/electoral_scope.py` como unica fonte de verdade sobre
abrangencia, em vez de literais SQL espalhados."""
from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pandas as pd

from .rules.electoral_scope import resolver_escopo
from .uf_data_bootstrap import caminho_votacao_secao, garantir_dados_uf
from .utils import cache_key, data_sources, get_logger, read_cache, resolve_path, write_cache

logger = get_logger(__name__)

# Rotulos usados pelo TSE para votos que nao correspondem a um candidato real.
_ROTULOS_VOTO_NAO_NOMINAL = ("VOTO NULO", "VOTO BRANCO", "VOTO EM LEGENDA")

# Prioridade de deferimento usada para ordenar candidaturas homonimas
# (secao 2 do briefing: priorizar deferidas/deferidas com recurso).
_PRIORIDADE_SITUACAO = {
    "DEFERIDO": 0,
    "DEFERIDO COM RECURSO": 1,
}

# Colunas realmente usadas pelas analises downstream. Evita "SELECT *" no
# arquivo de 2,7 GB (~40 colunas, muitas de texto repetido por linha), que
# em maquinas com pouca RAM livre pode estourar memoria ao materializar o
# resultado como DataFrame para municipios grandes (ex.: capital de SP).
_COLUNAS_VOTACAO = (
    "NR_VOTAVEL, NM_VOTAVEL, DS_CARGO, CD_MUNICIPIO, NM_MUNICIPIO, "
    "ANO_ELEICAO, NR_TURNO, NR_ZONA, NR_SECAO, NR_LOCAL_VOTACAO, "
    "NM_LOCAL_VOTACAO, QT_VOTOS"
)


@dataclass
class Candidatura:
    """Uma candidatura possivel encontrada para o numero informado."""

    numero: int
    nome_completo: str
    nome_urna: str
    cargo: str
    municipio: str
    codigo_municipio_tse: int | None
    uf: str
    ano_eleicao: int
    turno: int
    partido_sigla: str
    partido_nome: str
    coligacao_federacao: str
    situacao_candidatura: str
    resultado_final: str
    total_votos: int
    zonas_com_votos: int


def _fonte(nome: str) -> dict:
    return data_sources()["tse"][nome]


def _conexao() -> duckdb.DuckDBPyConnection:
    """Conexao DuckDB com limite de memoria conservador (maquinas com pouca
    RAM livre): forca uso de disco para spill em vez de falhar por OOM."""
    con = duckdb.connect(database=":memory:")
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='2GB'")
    temp_dir = str(resolve_path("data/cache/duckdb_tmp")).replace("\\", "/")
    con.execute(f"PRAGMA temp_directory='{temp_dir}'")
    return con


def _scan_sql(fonte: dict) -> str:
    caminho = fonte["arquivo_local"]
    if not (len(caminho) > 1 and caminho[1] == ":"):
        caminho = str(resolve_path(caminho))
    caminho = caminho.replace("\\", "/")
    if caminho.lower().endswith(".parquet"):
        # Pacote reduzido (ver scripts/preparar_dados_cloud.py) - mesmas
        # colunas, ja filtrado, sem necessidade de delim/encoding.
        return f"read_parquet('{caminho}')"
    return (
        f"read_csv('{caminho}', delim='{fonte['separador']}', header=true, quote='\"', "
        f"encoding='{fonte['encoding']}', ignore_errors=true)"
    )


def _candidaturas_registro(numero_candidato: int) -> pd.DataFrame:
    """Consulta consulta_cand para identidade/partido/situacao/resultado."""
    fonte = _fonte("consulta_candidatos")
    con = _conexao()
    sql = f"""
        SELECT
            NR_CANDIDATO AS numero,
            NM_CANDIDATO AS nome_completo,
            NM_URNA_CANDIDATO AS nome_urna,
            DS_CARGO AS cargo,
            NM_UE AS municipio,
            TRY_CAST(SG_UE AS INTEGER) AS codigo_municipio_tse,
            SG_UF AS uf,
            ANO_ELEICAO AS ano_eleicao,
            NR_TURNO AS turno,
            SG_PARTIDO AS partido_sigla,
            NM_PARTIDO AS partido_nome,
            COALESCE(NULLIF(NM_COLIGACAO, '#NULO'), NM_FEDERACAO, '') AS coligacao_federacao,
            DS_SITUACAO_CANDIDATURA AS situacao_candidatura,
            DS_SIT_TOT_TURNO AS resultado_final
        FROM {_scan_sql(fonte)}
        WHERE NR_CANDIDATO = {int(numero_candidato)}
          AND DS_ELEICAO ILIKE '%Eleições Municipais%'
          AND TP_ABRANGENCIA = 'MUNICIPAL'
          AND DS_SIT_TOT_TURNO != '#NULO'
    """
    # DS_SIT_TOT_TURNO = '#NULO' marca uma candidatura cujo registro foi
    # anulado/substituido (2.200 casos em SP) - a pessoa nunca apareceu na
    # urna e nao recebeu voto real nenhum. Sem este filtro, quando o mesmo
    # numero teve substituicao (ex.: candidato titular anulado, suplente/
    # substituto assume o numero), consulta_cand mantem as DUAS linhas de
    # registro para o mesmo (numero, municipio, cargo, turno); o merge com
    # os votos (agregados 1x por essa chave) duplicava o MESMO total de
    # votos reais para as duas pessoas, como se ambas tivessem recebido a
    # votacao inteira (caso real verificado: Pitangueiras/SP, numero 30000,
    # vereador - "MARCELAO" #NULO e "MARIA FERNANDA" NAO ELEITO apareciam
    # ambos com 79 votos, sendo que so a segunda de fato concorreu).
    logger.info("Consultando registro de candidaturas (consulta_cand) para numero=%s", numero_candidato)
    return con.execute(sql).fetchdf()


def _scan_votacao_secao_ufs(ufs: list[str]) -> str:
    """read_parquet aceita uma lista de arquivos e faz a uniao automatica -
    varre apenas as UFs realmente encontradas no registro (consulta_cand)
    para este numero de candidato, nunca o Brasil inteiro."""
    caminhos = [caminho_votacao_secao(uf).as_posix() for uf in ufs]
    lista = ", ".join(f"'{c}'" for c in caminhos)
    return f"read_parquet([{lista}])"


def _votos_totais_todas_candidaturas(numero_candidato: int, ufs: list[str]) -> pd.DataFrame:
    """Retorna, em uma unica varredura dos arquivos de votacao_secao das UFs
    informadas, o total de votos e zonas com votos para TODAS as
    candidaturas do numero informado, agrupado por municipio/cargo/ano/
    turno. `ufs` vem do registro (consulta_cand, nacional) - cada UF e
    baixada/convertida sob demanda (garantir_dados_uf) antes da varredura."""
    ufs_disponiveis = [uf for uf in ufs if garantir_dados_uf(uf)]
    if not ufs_disponiveis:
        return pd.DataFrame(
            columns=["codigo_municipio_tse", "cargo", "ano_eleicao", "turno",
                     "total_votos", "zonas_com_votos"]
        )

    con = _conexao()
    filtro_rotulos = " AND ".join(
        f"NM_VOTAVEL NOT ILIKE '{r}'" for r in _ROTULOS_VOTO_NAO_NOMINAL
    )
    sql = f"""
        SELECT
            CD_MUNICIPIO AS codigo_municipio_tse,
            DS_CARGO AS cargo,
            ANO_ELEICAO AS ano_eleicao,
            NR_TURNO AS turno,
            SUM(QT_VOTOS) AS total_votos,
            COUNT(DISTINCT NR_ZONA) AS zonas_com_votos
        FROM {_scan_votacao_secao_ufs(ufs_disponiveis)}
        WHERE NR_VOTAVEL = {int(numero_candidato)}
          AND {filtro_rotulos}
        GROUP BY 1, 2, 3, 4
    """
    logger.info(
        "Consultando votos totais (votacao_secao) para numero=%s nas UFs=%s",
        numero_candidato, ufs_disponiveis,
    )
    return con.execute(sql).fetchdf()


def buscar_candidaturas(numero_candidato: int) -> list[Candidatura]:
    """Retorna todas as candidaturas encontradas para o numero informado em
    QUALQUER UF do Brasil, cruzando o registro nacional (consulta_cand) com
    os votos (votacao_secao). O registro e' sempre nacional (arquivo leve,
    ja disponivel); os votos so sao baixados/convertidos (garantir_dados_uf)
    para as UFs onde o numero realmente foi registrado - nunca as 27 de
    uma vez. Usa cache em parquet para nao reprocessar a cada consulta."""
    key = cache_key("candidaturas_v4", numero_candidato)
    cached = read_cache("candidate_finder", key)
    if cached is not None:
        df = cached
    else:
        registro = _candidaturas_registro(numero_candidato)
        if registro.empty:
            write_cache("candidate_finder", key, registro)
            return []

        ufs = sorted(registro["uf"].dropna().unique().tolist())
        votos = _votos_totais_todas_candidaturas(numero_candidato, ufs)
        # DS_CARGO vem em caixas diferentes em cada arquivo do TSE
        # ("VEREADOR" no consulta_cand, "Vereador" no votacao_secao):
        # normaliza para a chave de merge sem alterar o cargo exibido.
        registro["_cargo_norm"] = registro["cargo"].str.upper()
        votos = votos.rename(columns={"cargo": "_cargo_votacao"})
        votos["_cargo_norm"] = votos["_cargo_votacao"].str.upper()
        df = registro.merge(
            votos.drop(columns=["_cargo_votacao"]),
            on=["codigo_municipio_tse", "_cargo_norm", "ano_eleicao", "turno"],
            how="left",
        ).drop(columns=["_cargo_norm"])
        df["total_votos"] = df["total_votos"].fillna(0).astype(int)
        df["zonas_com_votos"] = df["zonas_com_votos"].fillna(0).astype(int)
        df = df.sort_values(
            by=["ano_eleicao", "turno", "total_votos"], ascending=[False, False, False]
        )
        write_cache("candidate_finder", key, df)

    if df.empty:
        logger.warning("Nenhuma candidatura encontrada para o numero %s", numero_candidato)
        return []

    return [
        Candidatura(
            numero=int(row.numero),
            nome_completo=str(row.nome_completo).strip(),
            nome_urna=str(row.nome_urna).strip(),
            cargo=str(row.cargo).strip(),
            municipio=str(row.municipio).strip(),
            codigo_municipio_tse=int(row.codigo_municipio_tse),
            uf=str(row.uf).strip(),
            ano_eleicao=int(row.ano_eleicao),
            turno=int(row.turno),
            partido_sigla=str(row.partido_sigla).strip(),
            partido_nome=str(row.partido_nome).strip(),
            coligacao_federacao=str(row.coligacao_federacao).strip(),
            situacao_candidatura=str(row.situacao_candidatura).strip(),
            resultado_final=str(row.resultado_final).strip(),
            total_votos=int(row.total_votos),
            zonas_com_votos=int(row.zonas_com_votos),
        )
        for row in df.itertuples(index=False)
    ]


def eleicao_mais_recente(candidaturas: list[Candidatura]) -> list[Candidatura]:
    """Filtra apenas as candidaturas do ano/turno mais recente entre as
    encontradas, seguindo a regra da secao 1: 'ultima eleicao' = mais
    recente em que o candidato efetivamente concorreu."""
    if not candidaturas:
        return []
    ano_max = max(c.ano_eleicao for c in candidaturas)
    turno_max = max(c.turno for c in candidaturas if c.ano_eleicao == ano_max)
    return [c for c in candidaturas if c.ano_eleicao == ano_max and c.turno == turno_max]


def ordenar_por_prioridade_deferimento(candidaturas: list[Candidatura]) -> list[Candidatura]:
    """Ordena priorizando candidaturas deferidas/deferidas com recurso
    (secao 2 do briefing), mantendo as demais ao final."""
    return sorted(
        candidaturas,
        key=lambda c: _PRIORIDADE_SITUACAO.get(c.situacao_candidatura.upper(), 99),
    )


def votos_da_candidatura(candidatura: Candidatura) -> pd.DataFrame:
    """Retorna o detalhamento por zona/secao/local de votacao para a
    candidatura selecionada - base para todas as demais analises."""
    key = cache_key(
        "votos_candidatura_v2",
        candidatura.uf,
        candidatura.numero,
        candidatura.codigo_municipio_tse,
        candidatura.cargo,
        candidatura.ano_eleicao,
        candidatura.turno,
    )
    cached = read_cache("candidate_finder", key)
    if cached is not None:
        return cached

    garantir_dados_uf(candidatura.uf)
    con = _conexao()
    sql = f"""
        SELECT {_COLUNAS_VOTACAO}
        FROM read_parquet('{caminho_votacao_secao(candidatura.uf).as_posix()}')
        WHERE NR_VOTAVEL = {candidatura.numero}
          AND CD_MUNICIPIO = {candidatura.codigo_municipio_tse}
          AND DS_CARGO ILIKE '{candidatura.cargo}'
          AND ANO_ELEICAO = {candidatura.ano_eleicao}
          AND NR_TURNO = {candidatura.turno}
    """
    df = con.execute(sql).fetchdf()
    write_cache("candidate_finder", key, df)
    return df


def votos_da_disputa(candidatura: Candidatura) -> pd.DataFrame:
    """Retorna o detalhamento por zona/secao de TODOS os candidatos que
    disputaram o mesmo cargo, no mesmo municipio, ano e turno - base
    para a analise de concorrentes (secao 7)."""
    key = cache_key(
        "votos_disputa_v2",
        candidatura.uf,
        candidatura.codigo_municipio_tse,
        candidatura.cargo,
        candidatura.ano_eleicao,
        candidatura.turno,
    )
    cached = read_cache("candidate_finder", key)
    if cached is not None:
        return cached

    garantir_dados_uf(candidatura.uf)
    con = _conexao()
    sql = f"""
        SELECT {_COLUNAS_VOTACAO}
        FROM read_parquet('{caminho_votacao_secao(candidatura.uf).as_posix()}')
        WHERE CD_MUNICIPIO = {candidatura.codigo_municipio_tse}
          AND DS_CARGO ILIKE '{candidatura.cargo}'
          AND ANO_ELEICAO = {candidatura.ano_eleicao}
          AND NR_TURNO = {candidatura.turno}
    """
    logger.info(
        "Consultando disputa completa: municipio=%s cargo=%s ano=%s turno=%s",
        candidatura.municipio, candidatura.cargo, candidatura.ano_eleicao, candidatura.turno,
    )
    df = con.execute(sql).fetchdf()
    write_cache("candidate_finder", key, df)
    return df


def registro_candidatos_disputa(candidatura: Candidatura) -> pd.DataFrame:
    """Retorna o registro (consulta_cand) de todos os candidatos da mesma
    disputa - partido, situacao, resultado - para enriquecer a analise
    de concorrentes sem depender apenas do arquivo de votacao."""
    fonte = _fonte("consulta_candidatos")
    con = _conexao()
    sql = f"""
        SELECT
            NR_CANDIDATO AS numero,
            NM_CANDIDATO AS nome_completo,
            NM_URNA_CANDIDATO AS nome_urna,
            NR_PARTIDO AS numero_partido,
            SG_PARTIDO AS partido_sigla,
            NM_PARTIDO AS partido_nome,
            COALESCE(NULLIF(NM_COLIGACAO, '#NULO'), NM_FEDERACAO, '') AS coligacao_federacao,
            DS_SITUACAO_CANDIDATURA AS situacao_candidatura,
            DS_SIT_TOT_TURNO AS resultado_final
        FROM {_scan_sql(fonte)}
        WHERE TRY_CAST(SG_UE AS INTEGER) = {candidatura.codigo_municipio_tse}
          AND DS_CARGO = '{candidatura.cargo}'
          AND ANO_ELEICAO = {candidatura.ano_eleicao}
          AND NR_TURNO = {candidatura.turno}
          AND DS_ELEICAO ILIKE '%Eleições Municipais%'
          AND DS_SIT_TOT_TURNO != '#NULO'
    """
    # Mesmo filtro (e mesmo motivo) de _candidaturas_registro: sem isso, uma
    # candidatura substituida/anulada aparece com 2 linhas de registro para
    # o mesmo numero (a anulada + a substituta), duplicando a linha desse
    # candidato em ranking_disputa/ranking_partidos (merge how="left" contra
    # este registro) - caso real verificado: Pitangueiras/SP, numero 30000.
    return con.execute(sql).fetchdf()


# ---------------------------------------------------------------------------
# V2 - funcoes generalizadas (cargos estaduais/distritais + fluxo guiado).
# Nada acima desta linha foi alterado em relacao ao V1.
# ---------------------------------------------------------------------------


def _fonte_consulta_candidatos_ano(ano_eleicao: int) -> str:
    """Caminho do arquivo consulta_cand do ano informado. Para 2024, usa o
    arquivo_local ja configurado (identico ao V1); anos futuros seguem a
    mesma convencao de nome ja usada para 2024
    (data/raw/consulta_cand_{ano}_BR.parquet)."""
    if ano_eleicao == 2024:
        return _fonte("consulta_candidatos")["arquivo_local"]
    return f"data/raw/consulta_cand_{ano_eleicao}_BR.parquet"


def _scan_parquet(caminho: str) -> str:
    if not (len(caminho) > 1 and caminho[1] == ":"):
        caminho = str(resolve_path(caminho))
    return f"read_parquet('{caminho.replace(chr(92), '/')}')"


def buscar_candidatos_disputa(
    ano_eleicao: int,
    cargo: str,
    uf: str,
    municipio_codigo: int | None = None,
    turno: int = 1,
    numero: int | None = None,
) -> list[Candidatura]:
    """Busca candidatos de uma disputa JA CONHECIDA (ano/cargo/UF e, quando
    municipal, municipio) - usada pelo novo fluxo guiado em cascata
    (Eleicao->UF->[Municipio]->Cargo->Candidato), ao contrario de
    `buscar_candidaturas` (busca ampla por numero, so cargos municipais).

    Cobre tambem cargos estaduais/distritais (municipio_codigo=None agrega
    o estado/DF inteiro - vota-se e apura-se em todos os municipios da UF).
    Usa `resolver_escopo` (src/rules/electoral_scope.py) como unica fonte de
    verdade sobre abrangencia - nenhum literal de TP_ABRANGENCIA/DS_ELEICAO
    e escrito aqui."""
    escopo = resolver_escopo(
        ano_eleicao, cargo, uf=uf,
        municipio=(str(municipio_codigo) if municipio_codigo is not None else None),
        turno=turno,
    )

    con = _conexao()
    filtros = [
        f"DS_CARGO ILIKE '{escopo.cargo}'",
        f"ANO_ELEICAO = {ano_eleicao}",
        f"NR_TURNO = {turno}",
        "DS_SIT_TOT_TURNO != '#NULO'",
        f"DS_ELEICAO ILIKE '{escopo.filtro_sql_ds_eleicao}'",
    ]
    if escopo.filtro_sql_tp_abrangencia:
        filtros.append(f"TP_ABRANGENCIA = '{escopo.filtro_sql_tp_abrangencia}'")
    if escopo.tipo_abrangencia == "MUNICIPAL":
        if municipio_codigo is None:
            raise ValueError(f"{escopo.cargo} exige municipio_codigo")
        filtros.append(f"TRY_CAST(SG_UE AS INTEGER) = {int(municipio_codigo)}")
    else:
        filtros.append(f"SG_UF = '{uf.upper()}'")
    if numero is not None:
        filtros.append(f"NR_CANDIDATO = {int(numero)}")

    sql = f"""
        SELECT
            NR_CANDIDATO AS numero,
            NM_CANDIDATO AS nome_completo,
            NM_URNA_CANDIDATO AS nome_urna,
            DS_CARGO AS cargo,
            NM_UE AS municipio,
            TRY_CAST(SG_UE AS INTEGER) AS codigo_municipio_tse_bruto,
            SG_UF AS uf,
            ANO_ELEICAO AS ano_eleicao,
            NR_TURNO AS turno,
            SG_PARTIDO AS partido_sigla,
            NM_PARTIDO AS partido_nome,
            COALESCE(NULLIF(NM_COLIGACAO, '#NULO'), NM_FEDERACAO, '') AS coligacao_federacao,
            DS_SITUACAO_CANDIDATURA AS situacao_candidatura,
            DS_SIT_TOT_TURNO AS resultado_final
        FROM {_scan_parquet(_fonte_consulta_candidatos_ano(ano_eleicao))}
        WHERE {" AND ".join(filtros)}
    """
    logger.info(
        "Consultando candidatos da disputa: ano=%s cargo=%s uf=%s municipio=%s turno=%s",
        ano_eleicao, escopo.cargo, uf, municipio_codigo, turno,
    )
    registro = con.execute(sql).fetchdf()
    if registro.empty:
        return []

    ok = garantir_dados_uf(uf, ano_eleicao)
    if not ok:
        logger.warning("Dados de votacao_secao indisponiveis para UF=%s ano=%s", uf, ano_eleicao)
        registro["total_votos"] = 0
        registro["zonas_com_votos"] = 0
        votos = registro[["numero"]].assign(total_votos=0, zonas_com_votos=0)
    else:
        con2 = _conexao()
        filtros_votos = [
            f"DS_CARGO ILIKE '{escopo.cargo}'",
            f"ANO_ELEICAO = {ano_eleicao}",
            f"NR_TURNO = {turno}",
        ]
        if escopo.tipo_abrangencia == "MUNICIPAL":
            filtros_votos.append(f"CD_MUNICIPIO = {int(municipio_codigo)}")
        sql_votos = f"""
            SELECT
                NR_VOTAVEL AS numero,
                SUM(QT_VOTOS) AS total_votos,
                COUNT(DISTINCT NR_ZONA) AS zonas_com_votos
            FROM read_parquet('{caminho_votacao_secao(uf, ano_eleicao).as_posix()}')
            WHERE {" AND ".join(filtros_votos)}
            GROUP BY 1
        """
        votos = con2.execute(sql_votos).fetchdf()

    df = registro.merge(votos, on="numero", how="left", suffixes=("", "_y"))
    if "total_votos_y" in df.columns:
        df["total_votos"] = df["total_votos_y"]
        df["zonas_com_votos"] = df["zonas_com_votos_y"]
    df["total_votos"] = df["total_votos"].fillna(0).astype(int)
    df["zonas_com_votos"] = df["zonas_com_votos"].fillna(0).astype(int)
    df = df.sort_values("total_votos", ascending=False)

    resultado = []
    for row in df.itertuples(index=False):
        bruto = getattr(row, "codigo_municipio_tse_bruto", None)
        codigo_mun = int(bruto) if (escopo.tipo_abrangencia == "MUNICIPAL" and pd.notna(bruto)) else None
        resultado.append(
            Candidatura(
                numero=int(row.numero),
                nome_completo=str(row.nome_completo).strip(),
                nome_urna=str(row.nome_urna).strip(),
                cargo=str(row.cargo).strip(),
                municipio=str(row.municipio).strip(),
                codigo_municipio_tse=codigo_mun,
                uf=str(row.uf).strip(),
                ano_eleicao=int(row.ano_eleicao),
                turno=int(row.turno),
                partido_sigla=str(row.partido_sigla).strip(),
                partido_nome=str(row.partido_nome).strip(),
                coligacao_federacao=str(row.coligacao_federacao).strip(),
                situacao_candidatura=str(row.situacao_candidatura).strip(),
                resultado_final=str(row.resultado_final).strip(),
                total_votos=int(row.total_votos),
                zonas_com_votos=int(row.zonas_com_votos),
            )
        )
    return resultado


def votos_da_candidatura_generalizado(candidatura: Candidatura) -> pd.DataFrame:
    """Equivalente generalizado de votos_da_candidatura: identico para
    cargos municipais; para estaduais/distritais (codigo_municipio_tse is
    None) agrega o estado/DF inteiro, sem filtro de CD_MUNICIPIO."""
    key = cache_key(
        "votos_candidatura_escopo_v1", candidatura.uf, candidatura.numero,
        candidatura.codigo_municipio_tse, candidatura.cargo,
        candidatura.ano_eleicao, candidatura.turno,
    )
    cached = read_cache("candidate_finder", key)
    if cached is not None:
        return cached

    garantir_dados_uf(candidatura.uf, candidatura.ano_eleicao)
    con = _conexao()
    filtros = [
        f"NR_VOTAVEL = {candidatura.numero}",
        f"DS_CARGO ILIKE '{candidatura.cargo}'",
        f"ANO_ELEICAO = {candidatura.ano_eleicao}",
        f"NR_TURNO = {candidatura.turno}",
    ]
    if candidatura.codigo_municipio_tse is not None:
        filtros.append(f"CD_MUNICIPIO = {candidatura.codigo_municipio_tse}")
    sql = f"""
        SELECT {_COLUNAS_VOTACAO}
        FROM read_parquet('{caminho_votacao_secao(candidatura.uf, candidatura.ano_eleicao).as_posix()}')
        WHERE {" AND ".join(filtros)}
    """
    df = con.execute(sql).fetchdf()
    write_cache("candidate_finder", key, df)
    return df


def votos_da_disputa_generalizado(candidatura: Candidatura) -> pd.DataFrame:
    """Equivalente generalizado de votos_da_disputa: identico para cargos
    municipais; para estaduais/distritais agrega o estado/DF inteiro (sem
    filtro de CD_MUNICIPIO) - a base para ranking_disputa/ranking_partidos
    passa a cobrir todos os municipios da UF."""
    key = cache_key(
        "votos_disputa_escopo_v1", candidatura.uf, candidatura.codigo_municipio_tse,
        candidatura.cargo, candidatura.ano_eleicao, candidatura.turno,
    )
    cached = read_cache("candidate_finder", key)
    if cached is not None:
        return cached

    garantir_dados_uf(candidatura.uf, candidatura.ano_eleicao)
    con = _conexao()
    filtros = [
        f"DS_CARGO ILIKE '{candidatura.cargo}'",
        f"ANO_ELEICAO = {candidatura.ano_eleicao}",
        f"NR_TURNO = {candidatura.turno}",
    ]
    if candidatura.codigo_municipio_tse is not None:
        filtros.append(f"CD_MUNICIPIO = {candidatura.codigo_municipio_tse}")
    sql = f"""
        SELECT {_COLUNAS_VOTACAO}
        FROM read_parquet('{caminho_votacao_secao(candidatura.uf, candidatura.ano_eleicao).as_posix()}')
        WHERE {" AND ".join(filtros)}
    """
    logger.info(
        "Consultando disputa completa (generalizado): uf=%s cargo=%s ano=%s turno=%s municipio=%s",
        candidatura.uf, candidatura.cargo, candidatura.ano_eleicao, candidatura.turno,
        candidatura.codigo_municipio_tse,
    )
    df = con.execute(sql).fetchdf()
    write_cache("candidate_finder", key, df)
    return df


def registro_candidatos_disputa_generalizado(candidatura: Candidatura) -> pd.DataFrame:
    """Equivalente generalizado de registro_candidatos_disputa: filtra por
    municipio (SG_UE) quando a candidatura e municipal, ou por UF (SG_UF)
    quando e estadual/distrital - o registro de um candidato a Governador/
    Senador/Dep. Federal/Estadual nao tem um municipio unico associado."""
    con = _conexao()
    escopo = resolver_escopo(
        candidatura.ano_eleicao, candidatura.cargo, uf=candidatura.uf,
        municipio=candidatura.municipio, turno=candidatura.turno,
    )
    filtros = [
        f"DS_CARGO = '{candidatura.cargo}'",
        f"ANO_ELEICAO = {candidatura.ano_eleicao}",
        f"NR_TURNO = {candidatura.turno}",
        "DS_SIT_TOT_TURNO != '#NULO'",
        f"DS_ELEICAO ILIKE '{escopo.filtro_sql_ds_eleicao}'",
    ]
    if escopo.filtro_sql_tp_abrangencia:
        filtros.append(f"TP_ABRANGENCIA = '{escopo.filtro_sql_tp_abrangencia}'")
    if candidatura.codigo_municipio_tse is not None:
        filtros.append(f"TRY_CAST(SG_UE AS INTEGER) = {candidatura.codigo_municipio_tse}")
    else:
        filtros.append(f"SG_UF = '{candidatura.uf.upper()}'")

    sql = f"""
        SELECT
            NR_CANDIDATO AS numero,
            NM_CANDIDATO AS nome_completo,
            NM_URNA_CANDIDATO AS nome_urna,
            NR_PARTIDO AS numero_partido,
            SG_PARTIDO AS partido_sigla,
            NM_PARTIDO AS partido_nome,
            COALESCE(NULLIF(NM_COLIGACAO, '#NULO'), NM_FEDERACAO, '') AS coligacao_federacao,
            DS_SITUACAO_CANDIDATURA AS situacao_candidatura,
            DS_SIT_TOT_TURNO AS resultado_final
        FROM {_scan_parquet(_fonte_consulta_candidatos_ano(candidatura.ano_eleicao))}
        WHERE {" AND ".join(filtros)}
    """
    return con.execute(sql).fetchdf()


def listar_municipios_uf(ano_eleicao: int, uf: str) -> pd.DataFrame:
    """Lista (codigo, nome) dos municipios da UF com candidaturas municipais
    registradas no ano informado - usada pelo fluxo guiado em cascata
    (Eleicao->UF->Municipio->Cargo->Candidato) para popular o seletor de
    municipio. So faz sentido para anos/cargos de abrangencia MUNICIPAL
    (2024 Prefeito/Vereador) - cargos estaduais/nacionais nao tem um
    municipio para selecionar (o proprio fluxo guiado pula essa etapa)."""
    con = _conexao()
    sql = f"""
        SELECT DISTINCT TRY_CAST(SG_UE AS INTEGER) AS codigo_municipio_tse, NM_UE AS municipio
        FROM {_scan_parquet(_fonte_consulta_candidatos_ano(ano_eleicao))}
        WHERE SG_UF = '{uf.upper()}' AND TRY_CAST(SG_UE AS INTEGER) IS NOT NULL
        ORDER BY 2
    """
    return con.execute(sql).fetchdf()
