"""Correlacao entre desempenho eleitoral e variaveis demograficas
(secao 10.1 do briefing).

Trabalha sobre uma tabela por territorio (bairro/distrito/setor) que ja
tenha colunas de votos e de perfil demografico (ver demographic_analysis).
"""
from __future__ import annotations

import pandas as pd
from scipy import stats

from .data_validation import validar_amostra_minima
from .utils import DataIssue, get_logger

logger = get_logger(__name__)

_AMOSTRA_MINIMA = 8


def correlacoes_com_votos(
    df: pd.DataFrame, coluna_votos: str, variaveis: list[str]
) -> tuple[pd.DataFrame, list[DataIssue]]:
    """Correlacao de Pearson entre percentual de votos do candidato e cada
    variavel demografica, por territorio. Retorna coeficiente, p-valor,
    numero de observacoes e classificacao de significancia (p<0.05)."""
    issues = validar_amostra_minima(len(df), _AMOSTRA_MINIMA, "correlacoes_com_votos")
    if issues:
        return pd.DataFrame(columns=["variavel", "correlacao", "p_valor", "n", "significativo"]), issues

    linhas = []
    for var in variaveis:
        if var not in df.columns:
            continue
        subset = df[[coluna_votos, var]].dropna()
        if len(subset) < _AMOSTRA_MINIMA:
            continue
        r, p = stats.pearsonr(subset[coluna_votos], subset[var])
        linhas.append(
            {
                "variavel": var,
                "correlacao": round(float(r), 3),
                "p_valor": round(float(p), 4),
                "n": len(subset),
                "significativo": p < 0.05,
                "forca": _classificar_forca(r),
            }
        )
    resultado = pd.DataFrame(linhas).sort_values("correlacao", key=lambda s: s.abs(), ascending=False)
    return resultado.reset_index(drop=True), []


def _classificar_forca(r: float) -> str:
    """Classificacao textual da forca da correlacao (regra pratica usual
    em ciencias sociais - Cohen, 1988: 0.1/0.3/0.5 como fraca/moderada/forte)."""
    a = abs(r)
    if a < 0.1:
        return "desprezivel"
    if a < 0.3:
        return "fraca"
    if a < 0.5:
        return "moderada"
    return "forte"


def matriz_correlacao(df: pd.DataFrame, variaveis: list[str]) -> pd.DataFrame:
    """Matriz de correlacao (Pearson) entre todas as variaveis informadas -
    util para identificar multicolinearidade antes da regressao."""
    cols = [v for v in variaveis if v in df.columns]
    return df[cols].corr(method="pearson").round(3)
