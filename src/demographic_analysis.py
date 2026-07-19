"""Cruzamento com o Censo Demografico 2022 (IBGE) por setor censitario
(secao 9 e 10 do briefing).

Cada variavel usada aqui tem origem, arquivo e ano documentados em
config/data_sources.yaml, e o significado de cada codigo (V0nnnn) foi
verificado contra o dicionario oficial do IBGE (ver
data/raw/dicionario_ibge_20260520.xlsx e dicionario_renda_responsavel.xlsx)
- nao ha variavel usada sem essa verificacao (secao 4 do briefing).

Aproximacao metodologica: o perfil demografico de cada LOCAL DE VOTACAO e
o do setor censitario em que seu ponto (endereco) esta localizado. Isso
assume que o publico de um local de votacao reflete o setor onde ele fica
fisicamente - uma simplificacao razoavel, mas que nao captura eleitores que
se deslocam de outros setores para votar naquele local.
"""
from __future__ import annotations

import pandas as pd

from .utils import cache_key, data_sources, get_logger, read_cache, resolve_path, write_cache

logger = get_logger(__name__)

# Faixas etarias do arquivo de demografia (V01031-V01041) e seus pontos
# medios, usados apenas para uma idade media APROXIMADA por setor.
_FAIXAS_ETARIAS_MEIO = {
    "V01031": 2, "V01032": 7, "V01033": 12, "V01034": 17, "V01035": 22,
    "V01036": 27, "V01037": 34.5, "V01038": 44.5, "V01039": 54.5,
    "V01040": 64.5, "V01041": 75,
}

_COLUNAS_ALFABETIZACAO_TOTAL = [
    "V00644", "V00645", "V00646", "V00647", "V00648", "V00649", "V00650",
    "V00651", "V00652", "V00653", "V00654", "V00655", "V00656",
]
_COLUNAS_ALFABETIZACAO_ALFABETIZADOS = [
    "V00748", "V00749", "V00750", "V00751", "V00752", "V00753", "V00754",
    "V00755", "V00756", "V00757", "V00758", "V00759", "V00760",
]


def _ler_zip_csv(caminho: str, colunas: list[str], dtype: dict) -> pd.DataFrame:
    """Le os dados do IBGE apenas com as colunas de interesse - do CSV
    original (dentro do zip) ou do pacote reduzido em Parquet (ver
    scripts/preparar_dados_cloud.py), ja pre-filtrado para SP. Le tudo como
    string (dtype=str evita um bug conhecido do parser C do pandas ao
    combinar usecols+dtype parcial) e a conversao numerica fica a cargo de
    `_to_numeric`."""
    path = caminho if (len(caminho) > 1 and caminho[1] == ":") else str(resolve_path(caminho))
    if path.lower().endswith(".parquet"):
        # O parquet ja foi escrito a partir de um dataframe dtype=str
        # (ver scripts/preparar_dados_cloud.py), entao os nulos ja vem
        # como NaN reais, nao a string "nan".
        return pd.read_parquet(path, columns=colunas)
    return pd.read_csv(path, sep=";", usecols=colunas, dtype=str, encoding="latin-1")


def _to_numeric(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Converte para numerico, tratando 'X' (valor sigiloso, poucos casos
    no setor) como ausente - conforme convencao do IBGE para o Censo 2022 -
    e a virgula decimal brasileira (ex.: renda "3174,71") como ponto."""
    out = df.copy()
    for col in colunas:
        serie = out[col].replace("X", None)
        if serie.dropna().astype(str).str.contains(",").any():
            serie = serie.astype(str).str.replace(",", ".", regex=False)
        out[col] = pd.to_numeric(serie, errors="coerce")
    return out


def variaveis_demografia(setores_de_interesse: set[str]) -> pd.DataFrame:
    """Populacao total, % por sexo e idade media aproximada por setor
    (fonte: Agregados_por_setores_demografia_BR, variaveis V01006-V01041)."""
    key = cache_key("demografia", tuple(sorted(setores_de_interesse)))
    cached = read_cache("demographic_analysis", key)
    if cached is not None:
        return cached

    fonte = data_sources()["ibge"]["agregados_demografia"]["arquivo_local"]
    colunas = ["CD_setor", "V01006", "V01007", "V01008"] + list(_FAIXAS_ETARIAS_MEIO.keys())
    df = _ler_zip_csv(fonte, colunas, {"CD_setor": str})
    df = df[df["CD_setor"].isin(setores_de_interesse)]
    df = _to_numeric(df, colunas[1:])

    df["populacao_total"] = df["V01006"]
    df["pct_masculino"] = (100 * df["V01007"] / df["V01006"]).round(2)
    df["pct_feminino"] = (100 * df["V01008"] / df["V01006"]).round(2)

    soma_ponderada = sum(df[col] * meio for col, meio in _FAIXAS_ETARIAS_MEIO.items())
    soma_faixas = df[list(_FAIXAS_ETARIAS_MEIO.keys())].sum(axis=1)
    df["idade_media_aprox"] = (soma_ponderada / soma_faixas).round(1)

    resultado = df[["CD_setor", "populacao_total", "pct_masculino", "pct_feminino", "idade_media_aprox"]].rename(
        columns={"CD_setor": "CD_SETOR"}
    )
    write_cache("demographic_analysis", key, resultado)
    return resultado


def variaveis_cor_raca(setores_de_interesse: set[str]) -> pd.DataFrame:
    """% por cor/raca (branca, preta, amarela, parda, indigena) por setor
    (fonte: Agregados_por_setores_cor_ou_raca_BR, V01317-V01321)."""
    key = cache_key("cor_raca", tuple(sorted(setores_de_interesse)))
    cached = read_cache("demographic_analysis", key)
    if cached is not None:
        return cached

    fonte = data_sources()["ibge"]["agregados_cor_raca"]["arquivo_local"]
    colunas = ["CD_SETOR", "V01317", "V01318", "V01319", "V01320", "V01321"]
    df = _ler_zip_csv(fonte, colunas, {"CD_SETOR": str})
    df = df[df["CD_SETOR"].isin(setores_de_interesse)]
    df = _to_numeric(df, colunas[1:])

    total = df[colunas[1:]].sum(axis=1)
    df["pct_branca"] = (100 * df["V01317"] / total).round(2)
    df["pct_preta"] = (100 * df["V01318"] / total).round(2)
    df["pct_amarela"] = (100 * df["V01319"] / total).round(2)
    df["pct_parda"] = (100 * df["V01320"] / total).round(2)
    df["pct_indigena"] = (100 * df["V01321"] / total).round(2)
    df["pct_preta_parda"] = (df["pct_preta"] + df["pct_parda"]).round(2)

    resultado = df[
        ["CD_SETOR", "pct_branca", "pct_preta", "pct_amarela", "pct_parda", "pct_indigena", "pct_preta_parda"]
    ]
    write_cache("demographic_analysis", key, resultado)
    return resultado


def variaveis_alfabetizacao(setores_de_interesse: set[str]) -> pd.DataFrame:
    """% de alfabetizacao (15 anos ou mais) por setor (fonte:
    Agregados_por_setores_alfabetizacao_BR, V00644-656 total / V00748-760
    alfabetizados, por faixa etaria - razao calculada com faixas casadas)."""
    key = cache_key("alfabetizacao", tuple(sorted(setores_de_interesse)))
    cached = read_cache("demographic_analysis", key)
    if cached is not None:
        return cached

    fonte = data_sources()["ibge"]["agregados_alfabetizacao"]["arquivo_local"]
    colunas = ["CD_setor"] + _COLUNAS_ALFABETIZACAO_TOTAL + _COLUNAS_ALFABETIZACAO_ALFABETIZADOS
    df = _ler_zip_csv(fonte, colunas, {"CD_setor": str})
    df = df[df["CD_setor"].isin(setores_de_interesse)]
    df = _to_numeric(df, colunas[1:])

    total_15mais = df[_COLUNAS_ALFABETIZACAO_TOTAL].sum(axis=1)
    total_alfabetizados = df[_COLUNAS_ALFABETIZACAO_ALFABETIZADOS].sum(axis=1)
    df["pct_alfabetizado_15mais"] = (100 * total_alfabetizados / total_15mais).round(2)

    resultado = df[["CD_setor", "pct_alfabetizado_15mais"]].rename(columns={"CD_setor": "CD_SETOR"})
    write_cache("demographic_analysis", key, resultado)
    return resultado


def variaveis_renda(setores_de_interesse: set[str]) -> pd.DataFrame:
    """Renda media mensal do responsavel pelo domicilio, por setor (fonte:
    Agregados_por_setores_renda_responsavel_BR, V06001 pessoas responsaveis
    com rendimento, V06004 rendimento nominal medio mensal)."""
    key = cache_key("renda", tuple(sorted(setores_de_interesse)))
    cached = read_cache("demographic_analysis", key)
    if cached is not None:
        return cached

    fonte = data_sources()["ibge"]["agregados_renda"]["arquivo_local"]
    colunas = ["CD_SETOR", "V06001", "V06002", "V06004"]
    df = _ler_zip_csv(fonte, colunas, {"CD_SETOR": str})
    df = df[df["CD_SETOR"].isin(setores_de_interesse)]
    df = _to_numeric(df, colunas[1:])

    resultado = df.rename(
        columns={
            "V06001": "n_responsaveis_com_rendimento",
            "V06002": "n_moradores",
            "V06004": "renda_media_responsavel",
        }
    )
    write_cache("demographic_analysis", key, resultado)
    return resultado


def variaveis_parentesco(setores_de_interesse: set[str]) -> pd.DataFrame:
    """% de domicilios com responsavel do sexo feminino, por setor (fonte:
    Agregados_por_setores_parentesco_BR, V01042 total de responsaveis pelo
    domicilio / V01063 responsaveis do sexo feminino)."""
    key = cache_key("parentesco", tuple(sorted(setores_de_interesse)))
    cached = read_cache("demographic_analysis", key)
    if cached is not None:
        return cached

    fonte = data_sources()["ibge"]["agregados_parentesco"]["arquivo_local"]
    colunas = ["CD_SETOR", "V01042", "V01062", "V01063"]
    df = _ler_zip_csv(fonte, colunas, {"CD_SETOR": str})
    df = df[df["CD_SETOR"].isin(setores_de_interesse)]
    df = _to_numeric(df, colunas[1:])

    df["pct_domicilios_chefia_feminina"] = (100 * df["V01063"] / df["V01042"]).round(2)

    resultado = df[["CD_SETOR", "pct_domicilios_chefia_feminina"]]
    write_cache("demographic_analysis", key, resultado)
    return resultado


def variaveis_domicilio(setores_de_interesse: set[str]) -> pd.DataFrame:
    """% de domicilios com agua encanada, esgotamento sanitario adequado e
    coleta de lixo, por setor (fonte:
    Agregados_por_setores_caracteristicas_domicilio2_BR - variaveis com
    denominador e descricao inequivocos no dicionario oficial do IBGE,
    diferente de caracteristicas_domicilio1, ja excluido em
    config/data_sources.yaml por falta de identificacao clara):

    - agua encanada: V00199 (ate dentro de casa) + V00200 (so ate o
      terreno) vs V00201 (nao chega encanada).
    - esgoto adequado: V00309 (rede geral/pluvial) + V00310 (fossa septica
      ligada a rede) vs total de destinacoes (V00309 a V00316, incluindo
      V00311 fossa nao ligada, V00312 fossa rudimentar, V00313 vala, V00314
      rio/lago/corrego/mar, V00315 outra forma, V00316 sem banheiro/
      sanitario).
    - coleta de lixo: V00397 (coletado por servico de limpeza) + V00398
      (deposito em cacamba) vs total de destinacoes (V00397 a V00402)."""
    key = cache_key("domicilio2", tuple(sorted(setores_de_interesse)))
    cached = read_cache("demographic_analysis", key)
    if cached is not None:
        return cached

    fonte = data_sources()["ibge"]["agregados_domicilio2"]["arquivo_local"]
    colunas_agua = ["V00199", "V00200", "V00201"]
    colunas_esgoto = ["V00309", "V00310", "V00311", "V00312", "V00313", "V00314", "V00315", "V00316"]
    colunas_lixo = ["V00397", "V00398", "V00399", "V00400", "V00401", "V00402"]
    colunas = ["setor"] + colunas_agua + colunas_esgoto + colunas_lixo
    df = _ler_zip_csv(fonte, colunas, {"setor": str}).rename(columns={"setor": "CD_SETOR"})
    df = df[df["CD_SETOR"].isin(setores_de_interesse)]
    df = _to_numeric(df, colunas_agua + colunas_esgoto + colunas_lixo)

    total_agua = df[colunas_agua].sum(axis=1)
    df["pct_agua_encanada"] = (100 * (df["V00199"] + df["V00200"]) / total_agua).round(2)

    total_esgoto = df[colunas_esgoto].sum(axis=1)
    df["pct_esgoto_adequado"] = (100 * (df["V00309"] + df["V00310"]) / total_esgoto).round(2)

    total_lixo = df[colunas_lixo].sum(axis=1)
    df["pct_coleta_lixo"] = (100 * (df["V00397"] + df["V00398"]) / total_lixo).round(2)

    resultado = df[["CD_SETOR", "pct_agua_encanada", "pct_esgoto_adequado", "pct_coleta_lixo"]]
    write_cache("demographic_analysis", key, resultado)
    return resultado


def perfil_demografico_por_setor(setores_de_interesse: set[str]) -> pd.DataFrame:
    """Junta todas as variaveis demograficas verificadas em uma unica
    tabela por setor censitario."""
    setores_de_interesse = {s for s in setores_de_interesse if s and s != "None"}
    if not setores_de_interesse:
        return pd.DataFrame(columns=["CD_SETOR"])

    demografia = variaveis_demografia(setores_de_interesse)
    cor_raca = variaveis_cor_raca(setores_de_interesse)
    alfabetizacao = variaveis_alfabetizacao(setores_de_interesse)
    renda = variaveis_renda(setores_de_interesse)
    parentesco = variaveis_parentesco(setores_de_interesse)
    domicilio = variaveis_domicilio(setores_de_interesse)

    perfil = (
        demografia.merge(cor_raca, on="CD_SETOR", how="outer")
        .merge(alfabetizacao, on="CD_SETOR", how="outer")
        .merge(renda, on="CD_SETOR", how="outer")
        .merge(parentesco, on="CD_SETOR", how="outer")
        .merge(domicilio, on="CD_SETOR", how="outer")
    )
    return perfil


def agregados_populacionais_municipio(
    pontos_com_setor: pd.DataFrame, perfil_por_setor: pd.DataFrame
) -> pd.DataFrame:
    """Soma populacao_total por MUNICIPIO (nao por territorio fino), a
    partir dos setores censitarios cobertos pelos locais de votacao do
    municipio - usada pela "Regressao Geral" de cargos estaduais (V2) como
    covariavel opcional de "porte do municipio", mesclada (merge/broadcast)
    de volta em cada linha fina (zona/secao) do mesmo municipio.

    Dedup por `local_votacao_id` ANTES de somar: varias secoes/zonas
    compartilham o mesmo local de votacao (mesmo predio/setor), somar por
    linha inflaria o total por N linhas do mesmo predio. Deliberadamente
    uma funcao NOVA, nao uma extensao de perfil_demografico_do_territorio
    (aquela calcula MEDIA ponderada por votos por territorio - somar
    populacao bruta por municipio e uma semantica diferente, por isso
    populacao_total ja e excluida da lista de variaveis dela)."""
    unicos = pontos_com_setor.drop_duplicates(subset=["local_votacao_id"])
    base = unicos.merge(perfil_por_setor[["CD_SETOR", "populacao_total"]], on="CD_SETOR", how="left")
    return (
        base.groupby("CD_MUNICIPIO", as_index=False)["populacao_total"]
        .sum()
        .rename(columns={"populacao_total": "populacao_total_municipio"})
    )


def perfil_demografico_do_territorio(
    pontos_com_setor: pd.DataFrame, perfil_por_setor: pd.DataFrame, nivel: str
) -> pd.DataFrame:
    """Perfil demografico medio (ponderado pelos votos do candidato) de
    cada territorio (bairro/distrito/zona), a partir do perfil por setor
    dos locais de votacao que caem naquele territorio."""
    base = pontos_com_setor.merge(perfil_por_setor, on="CD_SETOR", how="left")
    variaveis = [
        "pct_masculino", "pct_feminino", "idade_media_aprox", "pct_branca",
        "pct_preta", "pct_parda", "pct_preta_parda", "pct_amarela", "pct_indigena",
        "pct_alfabetizado_15mais", "renda_media_responsavel",
        "pct_domicilios_chefia_feminina", "pct_agua_encanada",
        "pct_esgoto_adequado", "pct_coleta_lixo",
    ]
    variaveis = [v for v in variaveis if v in base.columns]

    def _media_ponderada(grupo: pd.DataFrame) -> pd.Series:
        pesos = grupo["votos_candidato"]
        out = {}
        for var in variaveis:
            valido = grupo[var].notna() & (pesos > 0)
            if valido.sum() == 0:
                out[var] = None
            else:
                out[var] = (grupo.loc[valido, var] * pesos[valido]).sum() / pesos[valido].sum()
        return pd.Series(out)

    return base.groupby(nivel).apply(_media_ponderada, include_groups=False).reset_index()
