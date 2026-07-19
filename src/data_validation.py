"""Validacoes de qualidade dos dados (secao 17 do briefing).

Cada funcao retorna uma lista de DataIssue. Nenhuma funcao interrompe o
pipeline: quem chama decide se continua ou nao, e o app sempre continua
produzindo as demais analises, registrando a limitacao no log.
"""
from __future__ import annotations

import pandas as pd

from .utils import DataIssue


def validar_totais_votos(
    votos_secao: pd.DataFrame, total_oficial: int | None, coluna_votos: str = "QT_VOTOS"
) -> list[DataIssue]:
    issues: list[DataIssue] = []
    soma = int(votos_secao[coluna_votos].sum())
    if total_oficial is not None and soma != total_oficial:
        issues.append(
            DataIssue(
                etapa="validar_totais_votos",
                severidade="aviso",
                mensagem=(
                    f"Soma agregada por secao ({soma}) difere do total oficial "
                    f"informado ({total_oficial}). Diferenca: {soma - total_oficial}."
                ),
            )
        )
    return issues


def validar_secoes_duplicadas(
    votos_secao: pd.DataFrame, chaves: list[str]
) -> list[DataIssue]:
    issues: list[DataIssue] = []
    duplicadas = votos_secao.duplicated(subset=chaves, keep=False)
    n = int(duplicadas.sum())
    if n > 0:
        issues.append(
            DataIssue(
                etapa="validar_secoes_duplicadas",
                severidade="erro",
                mensagem=f"{n} linhas duplicadas encontradas para as chaves {chaves}.",
            )
        )
    return issues


def validar_coordenadas(df: pd.DataFrame, lat_col: str, lon_col: str) -> list[DataIssue]:
    issues: list[DataIssue] = []
    invalidas = df[
        df[lat_col].isna()
        | df[lon_col].isna()
        | ~df[lat_col].between(-34, 6)
        | ~df[lon_col].between(-74, -28)
    ]
    if len(invalidas) > 0:
        issues.append(
            DataIssue(
                etapa="validar_coordenadas",
                severidade="aviso",
                mensagem=(
                    f"{len(invalidas)} de {len(df)} registros com coordenadas "
                    "ausentes ou fora do territorio brasileiro."
                ),
            )
        )
    return issues


def validar_valores_ausentes(df: pd.DataFrame, colunas_obrigatorias: list[str]) -> list[DataIssue]:
    issues: list[DataIssue] = []
    for col in colunas_obrigatorias:
        if col not in df.columns:
            issues.append(
                DataIssue(
                    etapa="validar_valores_ausentes",
                    severidade="erro",
                    mensagem=f"Coluna obrigatoria '{col}' ausente no dataframe.",
                )
            )
            continue
        n_na = int(df[col].isna().sum())
        if n_na > 0:
            issues.append(
                DataIssue(
                    etapa="validar_valores_ausentes",
                    severidade="aviso",
                    mensagem=f"Coluna '{col}' possui {n_na} valores ausentes.",
                )
            )
    return issues


def validar_percentuais(percentuais: pd.Series, tolerancia: float = 0.5) -> list[DataIssue]:
    issues: list[DataIssue] = []
    soma = float(percentuais.sum())
    if abs(soma - 100.0) > tolerancia:
        issues.append(
            DataIssue(
                etapa="validar_percentuais",
                severidade="aviso",
                mensagem=f"Percentuais somam {soma:.2f}% (esperado ~100%).",
            )
        )
    return issues


def validar_amostra_minima(n_observacoes: int, minimo: int, nome_analise: str) -> list[DataIssue]:
    issues: list[DataIssue] = []
    if n_observacoes < minimo:
        issues.append(
            DataIssue(
                etapa=nome_analise,
                severidade="erro",
                mensagem=(
                    f"Apenas {n_observacoes} observacoes disponiveis (minimo "
                    f"recomendado: {minimo}). Analise '{nome_analise}' nao sera executada."
                ),
            )
        )
    return issues
