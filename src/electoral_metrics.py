"""Metricas de resultado geral e desempenho territorial (secao 5 do briefing).

Todas as funcoes recebem DataFrames ja carregados (via candidate_finder) e
nao fazem I/O proprio, exceto pela leitura opcional do arquivo de detalhe
por secao (comparecimento/abstencao/brancos/nulos).
"""
from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pandas as pd

from .candidate_finder import Candidatura
from .utils import data_sources, get_logger, resolve_path
from .vote_filtering import secao_composta
from .vote_filtering import votos_nominais as _votos_nominais
from .vote_filtering import votos_validos as _votos_validos

logger = get_logger(__name__)


@dataclass
class ResultadoGeral:
    total_votos: int
    votos_validos_disputa: int
    pct_votos_validos: float
    colocacao_geral: int | None
    total_concorrentes: int
    votos_primeiro_colocado: int
    nome_primeiro_colocado: str
    distancia_para_primeiro_colocado: int
    votos_ultimo_eleito: int | None
    distancia_para_ultimo_eleito: int | None
    votos_concorrente_acima: int | None
    distancia_concorrente_acima: int | None
    votos_concorrente_abaixo: int | None
    distancia_concorrente_abaixo: int | None
    votos_partido_total: int
    pct_partido_sobre_validos: float
    pct_candidato_sobre_partido: float
    total_eleitos: int
    fonte: str = "TSE - votacao_secao + consulta_cand"


def resultado_geral(
    candidatura: Candidatura,
    votos_disputa: pd.DataFrame,
    registro_disputa: pd.DataFrame,
) -> ResultadoGeral:
    """Calcula o resultado geral do candidato frente a disputa completa
    (secao 5.1: total de votos, colocacao, distancias, participacao no
    partido)."""
    validos = _votos_validos(votos_disputa)
    votos_validos_total = int(validos["QT_VOTOS"].sum())
    nominais = _votos_nominais(votos_disputa, registro_disputa)

    ranking = (
        nominais[nominais["NR_VOTAVEL"] != -1]
        .groupby("NR_VOTAVEL", as_index=False)["QT_VOTOS"]
        .sum()
        .rename(columns={"QT_VOTOS": "total_votos"})
        .merge(
            registro_disputa[["numero", "nome_urna", "partido_sigla", "resultado_final"]],
            left_on="NR_VOTAVEL",
            right_on="numero",
            how="left",
        )
        .sort_values("total_votos", ascending=False)
        .reset_index(drop=True)
    )
    ranking["colocacao"] = ranking.index + 1

    linha_candidato = ranking[ranking["NR_VOTAVEL"] == candidatura.numero]
    colocacao = int(linha_candidato["colocacao"].iloc[0]) if not linha_candidato.empty else None

    primeiro = ranking.iloc[0]
    eleitos = ranking[ranking["resultado_final"].str.upper().str.startswith("ELEITO", na=False)]
    total_eleitos = len(eleitos)
    votos_ultimo_eleito = int(eleitos["total_votos"].min()) if total_eleitos else None

    acima = ranking[ranking["colocacao"] == (colocacao - 1)] if colocacao and colocacao > 1 else None
    abaixo = ranking[ranking["colocacao"] == (colocacao + 1)] if colocacao else None

    votos_partido_total = int(
        ranking[ranking["partido_sigla"] == candidatura.partido_sigla]["total_votos"].sum()
    )

    return ResultadoGeral(
        total_votos=candidatura.total_votos,
        votos_validos_disputa=votos_validos_total,
        pct_votos_validos=round(100 * candidatura.total_votos / votos_validos_total, 2)
        if votos_validos_total else 0.0,
        colocacao_geral=colocacao,
        total_concorrentes=len(ranking),
        votos_primeiro_colocado=int(primeiro["total_votos"]),
        nome_primeiro_colocado=str(primeiro["nome_urna"]),
        distancia_para_primeiro_colocado=int(primeiro["total_votos"]) - candidatura.total_votos,
        votos_ultimo_eleito=votos_ultimo_eleito,
        distancia_para_ultimo_eleito=(
            votos_ultimo_eleito - candidatura.total_votos if votos_ultimo_eleito is not None else None
        ),
        votos_concorrente_acima=int(acima["total_votos"].iloc[0]) if acima is not None and not acima.empty else None,
        distancia_concorrente_acima=(
            int(acima["total_votos"].iloc[0]) - candidatura.total_votos
            if acima is not None and not acima.empty else None
        ),
        votos_concorrente_abaixo=int(abaixo["total_votos"].iloc[0]) if abaixo is not None and not abaixo.empty else None,
        distancia_concorrente_abaixo=(
            candidatura.total_votos - int(abaixo["total_votos"].iloc[0])
            if abaixo is not None and not abaixo.empty else None
        ),
        votos_partido_total=votos_partido_total,
        pct_partido_sobre_validos=round(100 * votos_partido_total / votos_validos_total, 2)
        if votos_validos_total else 0.0,
        pct_candidato_sobre_partido=round(100 * candidatura.total_votos / votos_partido_total, 2)
        if votos_partido_total else 0.0,
        total_eleitos=total_eleitos,
    )


def _carregar_detalhe_secao() -> pd.DataFrame | None:
    """Carrega comparecimento/abstencao/brancos/nulos por secao (arquivo
    detalhe_votacao_secao). Retorna None se o arquivo nao estiver disponivel
    (secao 17: sistema deve seguir sem essa informacao, nao inventar)."""
    fonte = data_sources()["tse"].get("detalhe_votacao_secao")
    if fonte is None:
        return None
    caminho = fonte["arquivo_local"]
    path = resolve_path(caminho) if not (len(caminho) > 1 and caminho[1] == ":") else caminho
    from pathlib import Path

    if not Path(path).exists():
        logger.warning("Arquivo de detalhe por secao nao encontrado: %s", path)
        return None
    con = duckdb.connect()
    caminho_posix = str(path).replace(chr(92), "/")
    origem = (
        f"read_parquet('{caminho_posix}')"
        if caminho_posix.lower().endswith(".parquet")
        else f"read_csv('{caminho_posix}', delim=';', header=true, quote='\"', "
             f"encoding='{fonte['encoding']}', ignore_errors=true)"
    )
    sql = (
        f"SELECT CD_MUNICIPIO, NR_ZONA, NR_SECAO, DS_CARGO, QT_APTOS, "
        f"QT_COMPARECIMENTO, QT_ABSTENCOES, QT_VOTOS_BRANCOS, QT_VOTOS_NULOS "
        f"FROM {origem}"
    )
    return con.execute(sql).fetchdf()


def desempenho_territorial(
    candidatura: Candidatura,
    votos_candidatura: pd.DataFrame,
    votos_disputa: pd.DataFrame,
    registro_disputa: pd.DataFrame,
    nivel: str,
) -> pd.DataFrame:
    """Desempenho do candidato por territorio (secao 5.2). `nivel` deve ser
    uma coluna presente no dataframe: 'NR_ZONA', 'NR_LOCAL_VOTACAO',
    'NR_SECAO' (cargos municipais - a candidatura ja e de um unico
    municipio, o municipio E o nivel superior, calculado em
    resultado_geral) - ou 'CD_MUNICIPIO' (V2, cargos estaduais/distritais:
    votos_candidatura/votos_disputa vem de
    candidate_finder.votos_da_candidatura_generalizado/
    votos_da_disputa_generalizado, que cobrem o estado/DF inteiro e ja
    trazem CD_MUNICIPIO - nenhuma mudanca de logica foi necessaria aqui,
    a funcao ja agrupava por qualquer coluna informada em `nivel`)."""
    validos = _votos_validos(votos_disputa)
    nominais = _votos_nominais(votos_disputa, registro_disputa)

    votos_cand_terr = (
        votos_candidatura.groupby(nivel, as_index=False)["QT_VOTOS"].sum()
        .rename(columns={"QT_VOTOS": "votos_candidato"})
    )
    votos_validos_terr = (
        validos.groupby(nivel, as_index=False)["QT_VOTOS"].sum()
        .rename(columns={"QT_VOTOS": "votos_validos_territorio"})
    )
    # colocacao do candidato em cada territorio (exclui legenda: senao o
    # voto de legenda do partido aparece como candidatura fantasma)
    votos_todos_terr = nominais.groupby([nivel, "NR_VOTAVEL"], as_index=False)["QT_VOTOS"].sum()
    votos_todos_terr["colocacao"] = votos_todos_terr.groupby(nivel)["QT_VOTOS"].rank(
        ascending=False, method="min"
    )
    colocacao_cand = votos_todos_terr[votos_todos_terr["NR_VOTAVEL"] == candidatura.numero][
        [nivel, "colocacao"]
    ]

    out = votos_cand_terr.merge(votos_validos_terr, on=nivel, how="left").merge(
        colocacao_cand, on=nivel, how="left"
    )
    out["pct_votos_validos_territorio"] = (
        100 * out["votos_candidato"] / out["votos_validos_territorio"]
    ).round(2)
    total_candidato = out["votos_candidato"].sum()
    out["participacao_no_total_candidato"] = (
        100 * out["votos_candidato"] / total_candidato
    ).round(2) if total_candidato else 0.0

    media_geral = out["votos_candidato"].mean()
    out["desvio_vs_media"] = (out["votos_candidato"] - media_geral).round(2)
    out["media_votos_territorio"] = round(media_geral, 2)

    return out.sort_values("votos_candidato", ascending=False).reset_index(drop=True)


def enriquecer_com_comparecimento_abstencao(
    territorial: pd.DataFrame, candidatura: Candidatura, nivel: str
) -> pd.DataFrame:
    """Adiciona comparecimento/abstencao/brancos/nulos ao dataframe
    territorial, quando o arquivo de detalhe por secao estiver disponivel."""
    detalhe = _carregar_detalhe_secao()
    if detalhe is None:
        territorial["comparecimento"] = None
        territorial["abstencoes"] = None
        territorial["votos_brancos"] = None
        territorial["votos_nulos"] = None
        return territorial

    detalhe_mun = detalhe[
        (detalhe["CD_MUNICIPIO"] == candidatura.codigo_municipio_tse)
        & (detalhe["DS_CARGO"].str.upper() == candidatura.cargo.upper())
    ]
    coluna_origem = None
    if nivel == "NR_ZONA":
        coluna_origem = "NR_ZONA"
    elif nivel == "NR_SECAO_COMPOSTA":
        # NR_SECAO sozinho reinicia a numeracao a cada zona - usa a mesma
        # coluna composta (zona+secao) do lado do candidato, senao o merge
        # abaixo (left_on=nivel) nunca encontraria correspondencia.
        detalhe_mun = detalhe_mun.assign(NR_SECAO_COMPOSTA=secao_composta(detalhe_mun))
        coluna_origem = "NR_SECAO_COMPOSTA"
    if coluna_origem is None or coluna_origem not in detalhe_mun.columns:
        territorial["comparecimento"] = None
        territorial["abstencoes"] = None
        territorial["votos_brancos"] = None
        territorial["votos_nulos"] = None
        return territorial

    agregado = detalhe_mun.groupby(coluna_origem, as_index=False).agg(
        comparecimento=("QT_COMPARECIMENTO", "sum"),
        abstencoes=("QT_ABSTENCOES", "sum"),
        votos_brancos=("QT_VOTOS_BRANCOS", "sum"),
        votos_nulos=("QT_VOTOS_NULOS", "sum"),
    )
    return territorial.merge(agregado, left_on=nivel, right_on=coluna_origem, how="left")


def indice_concentracao_hhi(territorial: pd.DataFrame, coluna_votos: str = "votos_candidato") -> float:
    """Indice Herfindahl-Hirschman da distribuicao dos votos do candidato
    entre territorios (secao 5.1: taxa de concentracao territorial dos
    votos). Varia de ~0 (disperso) a 1 (concentrado em um unico territorio)."""
    total = territorial[coluna_votos].sum()
    if not total:
        return 0.0
    shares = territorial[coluna_votos] / total
    return round(float((shares**2).sum()), 4)
