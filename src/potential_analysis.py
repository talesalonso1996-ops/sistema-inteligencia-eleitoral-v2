"""Identificacao de territorios com maior potencial de crescimento para o
candidato (secao de "Estatistica Avancada" do produto).

Diferente de `potential_index.py` (que PONTUA o desempenho atual 0-100),
este modulo RANQUEIA onde vale a pena investir esforco de campanha,
combinando dois sinais estatisticos ja calculados em outros modulos:

1. O quanto o territorio esta abaixo da media dos territorios com perfil
   demografico semelhante (mesmo cluster de `clustering.py`) - territorios
   "atrasados" em relacao aos seus pares.
2. Quando disponivel, a probabilidade prevista de "boa votacao" pelo
   modelo de regressao logistica (`regression_models.py`) - territorios
   onde o perfil demografico sugere alta chance de bom desempenho, mas o
   candidato ainda nao capturou esses votos.

Nenhum numero e fabricado: os dois sinais vem diretamente dos modelos
estatisticos ja documentados; quando um dos dois nao esta disponivel
(amostra pequena, modelo nao convergiu), o score usa apenas o sinal
disponivel e isso fica registrado na justificativa de cada linha.
"""
from __future__ import annotations

import math

import pandas as pd

from .clustering import ResultadoClustering
from .regression_models import ResultadoRegressaoLogistica


def _probabilidade_logistica(row: pd.Series, modelo: ResultadoRegressaoLogistica) -> float | None:
    try:
        z = modelo.intercepto + sum(
            coef.coeficiente * row[coef.variavel] for coef in modelo.coeficientes.itertuples()
        )
    except (KeyError, TypeError):
        return None
    return 1 / (1 + math.exp(-z))


def identificar_bairros_potencial(
    resultado_clustering: ResultadoClustering,
    modelo_logistico: ResultadoRegressaoLogistica | None,
    coluna_territorio: str,
    coluna_votos: str = "votos_candidato",
    top_n: int = 10,
) -> pd.DataFrame:
    """Ranqueia os territorios com maior potencial de crescimento (top_n),
    combinando o gap vs. media do cluster e (se disponivel) a
    probabilidade prevista de boa votacao."""
    df = resultado_clustering.territorios_com_cluster.copy()
    media_cluster = df.groupby("cluster")[coluna_votos].transform("mean")
    df["media_do_cluster"] = media_cluster.round(1)
    df["gap_vs_cluster"] = (df["media_do_cluster"] - df[coluna_votos]).round(1)

    candidatos = df[df["gap_vs_cluster"] > 0].copy()
    if candidatos.empty:
        return pd.DataFrame(
            columns=[coluna_territorio, "cluster", coluna_votos, "media_do_cluster",
                     "gap_vs_cluster", "probabilidade_boa_votacao", "score_potencial", "justificativa"]
        )

    gap_max = candidatos["gap_vs_cluster"].max()
    candidatos["_score_gap"] = (
        100 * candidatos["gap_vs_cluster"] / gap_max if gap_max else 0.0
    )

    if modelo_logistico is not None:
        candidatos["probabilidade_boa_votacao"] = candidatos.apply(
            lambda row: _probabilidade_logistica(row, modelo_logistico), axis=1
        )
        candidatos["_score_prob"] = candidatos["probabilidade_boa_votacao"].fillna(0) * 100
        tem_prob = candidatos["probabilidade_boa_votacao"].notna()
        candidatos["score_potencial"] = candidatos["_score_gap"]
        candidatos.loc[tem_prob, "score_potencial"] = (
            candidatos.loc[tem_prob, "_score_gap"] + candidatos.loc[tem_prob, "_score_prob"]
        ) / 2
        candidatos["justificativa"] = candidatos.apply(
            lambda r: (
                f"{r['gap_vs_cluster']:.0f} votos abaixo da media de territorios com perfil "
                f"semelhante (cluster {r['cluster']})"
                + (
                    f"; modelo estatistico indica {r['probabilidade_boa_votacao']*100:.0f}% de chance "
                    "de boa votacao aqui" if pd.notna(r.get("probabilidade_boa_votacao")) else ""
                )
            ),
            axis=1,
        )
    else:
        candidatos["probabilidade_boa_votacao"] = None
        candidatos["score_potencial"] = candidatos["_score_gap"]
        candidatos["justificativa"] = candidatos["gap_vs_cluster"].apply(
            lambda g: f"{g:.0f} votos abaixo da media de territorios com perfil demografico semelhante."
        )

    candidatos["score_potencial"] = candidatos["score_potencial"].round(1)
    colunas = [coluna_territorio, "cluster", coluna_votos, "media_do_cluster",
               "gap_vs_cluster", "probabilidade_boa_votacao", "score_potencial", "justificativa"]
    return (
        candidatos[colunas]
        .sort_values("score_potencial", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
