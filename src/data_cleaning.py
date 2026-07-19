"""Limpeza e padronizacao de dados brutos (secao 4/17 do briefing)."""
from __future__ import annotations

import pandas as pd

from .utils import get_logger

logger = get_logger(__name__)


def padronizar_colunas_texto(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Remove espacos extras e normaliza caixa alta em colunas de texto
    (nomes de municipio, candidato, bairro etc.), evitando divergencias
    de agrupamento por diferencas triviais de formatacao."""
    out = df.copy()
    for col in colunas:
        if col in out.columns:
            out[col] = out[col].astype(str).str.strip().str.upper()
    return out


def remover_linhas_sem_secao_ou_zona(df: pd.DataFrame) -> pd.DataFrame:
    """Remove registros sem identificacao valida de zona/secao - nao ha
    como agregar territorialmente esses casos (secao 17: nao inventar
    valores ausentes)."""
    antes = len(df)
    out = df.dropna(subset=["NR_ZONA", "NR_SECAO"])
    removidas = antes - len(out)
    if removidas:
        logger.warning("%s linhas removidas por falta de NR_ZONA/NR_SECAO", removidas)
    return out


def coagir_numericos(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in colunas:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out
