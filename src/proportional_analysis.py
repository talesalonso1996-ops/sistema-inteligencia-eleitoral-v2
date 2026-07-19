"""Detalhamento de cargos PROPORCIONAIS (Vereador, Deputado Federal/
Estadual/Distrital) - posicao do candidato dentro do partido/federacao,
comparacao com o ultimo eleito e com suplentes do mesmo partido.

O resultado oficial do TSE (`resultado_final`/coluna `eleito` ja calculada
em competitor_analysis.ranking_disputa, a partir de DS_SIT_TOT_TURNO -
"ELEITO"/"ELEITO POR QP"/"ELEITO POR MEDIA"/"SUPLENTE"/"NAO ELEITO") e
considerado DEFINITIVO para saber quem foi eleito. Este modulo NAO
reimplementa o calculo de quociente eleitoral/partidario nem a
distribuicao de sobras (metodo de maiores medias) - esse calculo ja foi
feito pelo TSE; reimplementa-lo arriscaria divergir da fonte oficial,
contrariando a regra do projeto de nunca fabricar/estimar um dado que ja
existe, verificado, na fonte oficial (confirmado com dados reais: SP 2022
teve exatamente 70 "ELEITO POR QP/MEDIA" para Deputado Federal e 94 para
Deputado Estadual, batendo com o numero oficial de cadeiras de cada casa).

Reaproveita ranking_disputa e ranking_partidos (competitor_analysis.py) ja
calculados - nao recomputa nenhum total do zero.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class ResumoProporcional:
    numero: int
    total_votos: int
    colocacao_geral: int
    situacao_final_oficial: str

    partido_sigla: str
    votos_partido_total: int
    n_candidatos_partido: int
    n_eleitos_partido: int
    colocacao_dentro_partido: int
    pct_participacao_partido: float
    votos_ultimo_eleito_partido: int | None
    diferenca_para_ultimo_eleito_partido: int | None
    votos_primeiro_suplente_partido: int | None
    diferenca_para_primeiro_suplente_partido: int | None

    federacao: str | None
    votos_federacao_total: int | None
    n_candidatos_federacao: int | None
    n_eleitos_federacao: int | None
    colocacao_dentro_federacao: int | None
    pct_participacao_federacao: float | None


def ranking_federacoes(ranking_partidos_df: pd.DataFrame, registro_disputa: pd.DataFrame) -> pd.DataFrame:
    """Reagrupa ranking_partidos (ja com votos nominais+legenda por
    partido) por federacao/coligacao - soma os partidos que compartilham a
    mesma federacao/coligacao nesta disputa."""
    mapa_federacao = (
        registro_disputa[["partido_sigla", "coligacao_federacao"]]
        .dropna(subset=["partido_sigla"])
        .drop_duplicates(subset=["partido_sigla"])
    )
    com_federacao = ranking_partidos_df.merge(mapa_federacao, on="partido_sigla", how="left")
    com_federacao["coligacao_federacao"] = com_federacao["coligacao_federacao"].replace("", pd.NA)
    agregado = com_federacao.dropna(subset=["coligacao_federacao"]).groupby(
        "coligacao_federacao", as_index=False
    ).agg(
        votos_totais=("votos_totais", "sum"),
        n_candidatos=("n_candidatos", "sum"),
        n_eleitos=("n_eleitos", "sum"),
        n_partidos=("partido_sigla", "nunique"),
    )
    return agregado.sort_values("votos_totais", ascending=False).reset_index(drop=True)


def resumo_proporcional(
    numero_candidato: int,
    ranking_disputa_df: pd.DataFrame,
    registro_disputa: pd.DataFrame,
    ranking_partidos_df: pd.DataFrame,
) -> ResumoProporcional:
    """Monta o resumo proporcional de um candidato especifico dentro da
    disputa - posicao/participacao dentro do partido e da federacao,
    comparacao com o ultimo eleito e o primeiro suplente do MESMO
    partido."""
    federacoes_por_numero = registro_disputa[["numero", "coligacao_federacao"]].drop_duplicates()
    ranking = ranking_disputa_df.merge(
        federacoes_por_numero, left_on="NR_VOTAVEL", right_on="numero", how="left"
    ).drop(columns=["numero"])

    linha = ranking[ranking["NR_VOTAVEL"] == numero_candidato]
    if linha.empty:
        raise ValueError(f"Candidato {numero_candidato} nao encontrado no ranking da disputa")
    linha = linha.iloc[0]

    partido = linha["partido_sigla"]
    grupo_partido = ranking[ranking["partido_sigla"] == partido].sort_values("total_votos", ascending=False)
    linha_ranking_partido = ranking_partidos_df[ranking_partidos_df["partido_sigla"] == partido]
    votos_partido_total = int(linha_ranking_partido["votos_totais"].iloc[0]) if len(linha_ranking_partido) else 0
    n_eleitos_partido = int(linha_ranking_partido["n_eleitos"].iloc[0]) if len(linha_ranking_partido) else 0

    colocacao_partido = int((grupo_partido["total_votos"] > linha["total_votos"]).sum() + 1)
    eleitos_partido = grupo_partido[grupo_partido["eleito"]]
    votos_ultimo_eleito = int(eleitos_partido["total_votos"].min()) if len(eleitos_partido) else None
    nao_eleitos_partido = grupo_partido[~grupo_partido["eleito"]].sort_values("total_votos", ascending=False)
    votos_primeiro_suplente = int(nao_eleitos_partido["total_votos"].iloc[0]) if len(nao_eleitos_partido) else None

    federacao_raw = linha["coligacao_federacao"]
    tem_federacao = pd.notna(federacao_raw) and str(federacao_raw).strip() != ""
    votos_federacao_total = n_candidatos_federacao = n_eleitos_federacao = None
    colocacao_federacao = pct_participacao_federacao = None
    if tem_federacao:
        ranking_federacoes_df = ranking_federacoes(ranking_partidos_df, registro_disputa)
        linha_federacao = ranking_federacoes_df[ranking_federacoes_df["coligacao_federacao"] == federacao_raw]
        if len(linha_federacao):
            votos_federacao_total = int(linha_federacao["votos_totais"].iloc[0])
            n_candidatos_federacao = int(linha_federacao["n_candidatos"].iloc[0])
            n_eleitos_federacao = int(linha_federacao["n_eleitos"].iloc[0])
            grupo_federacao = ranking[ranking["coligacao_federacao"] == federacao_raw]
            colocacao_federacao = int((grupo_federacao["total_votos"] > linha["total_votos"]).sum() + 1)
            pct_participacao_federacao = (
                round(100 * linha["total_votos"] / votos_federacao_total, 2) if votos_federacao_total else 0.0
            )

    return ResumoProporcional(
        numero=int(linha["NR_VOTAVEL"]),
        total_votos=int(linha["total_votos"]),
        colocacao_geral=int(linha["colocacao"]),
        situacao_final_oficial=str(linha["resultado_final"]),
        partido_sigla=partido,
        votos_partido_total=votos_partido_total,
        n_candidatos_partido=len(grupo_partido),
        n_eleitos_partido=n_eleitos_partido,
        colocacao_dentro_partido=colocacao_partido,
        pct_participacao_partido=(
            round(100 * linha["total_votos"] / votos_partido_total, 2) if votos_partido_total else 0.0
        ),
        votos_ultimo_eleito_partido=votos_ultimo_eleito,
        diferenca_para_ultimo_eleito_partido=(
            int(linha["total_votos"]) - votos_ultimo_eleito if votos_ultimo_eleito is not None else None
        ),
        votos_primeiro_suplente_partido=votos_primeiro_suplente,
        diferenca_para_primeiro_suplente_partido=(
            int(linha["total_votos"]) - votos_primeiro_suplente if votos_primeiro_suplente is not None else None
        ),
        federacao=str(federacao_raw) if tem_federacao else None,
        votos_federacao_total=votos_federacao_total,
        n_candidatos_federacao=n_candidatos_federacao,
        n_eleitos_federacao=n_eleitos_federacao,
        colocacao_dentro_federacao=colocacao_federacao,
        pct_participacao_federacao=pct_participacao_federacao,
    )
