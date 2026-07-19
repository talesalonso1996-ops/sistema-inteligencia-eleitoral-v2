"""Filtragem de votos validos/nominais/legenda - usado por
electoral_metrics.py e competitor_analysis.py.

No arquivo de votacao por secao, o voto de legenda aparece com
NM_VOTAVEL = nome do PARTIDO e NR_VOTAVEL = numero do partido (nao de um
candidato). Se nao for excluido antes de agrupar por NR_VOTAVEL, ele
aparece como uma "candidatura fantasma" de votacao alta. E valido para o
total de votos validos e para o total do partido, mas nao para o ranking
individual de candidatos - por isso a exclusao usa o conjunto de numeros
de partido do registro (consulta_cand), nao um rotulo textual fixo.
"""
from __future__ import annotations

import pandas as pd

_ROTULOS_NAO_VALIDOS = ("VOTO NULO", "VOTO BRANCO")


def votos_validos(votos_disputa: pd.DataFrame) -> pd.DataFrame:
    """Remove votos brancos/nulos, mantendo nominais e de legenda (validos
    para fins de percentual, conforme definicao do TSE)."""
    mask = ~votos_disputa["NM_VOTAVEL"].str.upper().isin(_ROTULOS_NAO_VALIDOS)
    return votos_disputa[mask].copy()


def votos_nominais(votos_disputa: pd.DataFrame, registro_disputa: pd.DataFrame) -> pd.DataFrame:
    """Remove brancos/nulos/voto de legenda: mantem apenas votos em
    candidatos individuais. Uso obrigatorio antes de agrupar por
    NR_VOTAVEL para ranking/colocacao."""
    validos = votos_validos(votos_disputa)
    numeros_partido = set(registro_disputa["numero_partido"].dropna().unique())
    mask = ~validos["NR_VOTAVEL"].isin(numeros_partido)
    return validos[mask].copy()


def votos_legenda(votos_disputa: pd.DataFrame, registro_disputa: pd.DataFrame) -> pd.DataFrame:
    """Apenas os votos de legenda (complementar a `votos_nominais`)."""
    numeros_partido = set(registro_disputa["numero_partido"].dropna().unique())
    return votos_disputa[votos_disputa["NR_VOTAVEL"].isin(numeros_partido)].copy()


def secao_composta(votos: pd.DataFrame) -> pd.Series:
    """Identificador unico de secao eleitoral (NR_ZONA + NR_SECAO).

    NR_SECAO sozinho NAO identifica uma secao fisica dentro do municipio:
    a numeracao de secao reinicia a cada zona eleitoral, entao duas secoes
    fisicas de zonas diferentes podem ter o mesmo NR_SECAO (ex.: em Sao
    Paulo capital, 934 dos 1007 numeros de secao aparecem em mais de uma
    zona). Agrupar por NR_SECAO cru soma votos de secoes fisicas distintas
    e nao relacionadas sob um unico rotulo - usar sempre esta coluna
    composta como nivel territorial quando o usuario escolhe 'Secao
    eleitoral', nunca a coluna NR_SECAO isolada."""
    return "Zona " + votos["NR_ZONA"].astype(str) + " - Secao " + votos["NR_SECAO"].astype(str)
