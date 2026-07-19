"""Filtragem de votos validos/nominais/legenda - usado por
electoral_metrics.py e competitor_analysis.py.

No arquivo de votacao por secao, o voto de legenda aparece com
NM_VOTAVEL = nome do PARTIDO e NR_VOTAVEL = numero do partido (nao de um
candidato). Se nao for excluido antes de agrupar por NR_VOTAVEL, ele
aparece como uma "candidatura fantasma" de votacao alta. E valido para o
total de votos validos e para o total do partido, mas nao para o ranking
individual de candidatos.

CORRECAO (bug real de producao, encontrado no V1 e corrigido tambem aqui):
a exclusao NAO pode se basear so em NR_VOTAVEL bater com um numero de
partido do registro - em disputas MAJORITARIAS (Prefeito, Governador,
Senador, Presidente), a convencao do TSE e o numero de urna do candidato
SER o proprio numero do partido (ex.: Ricardo Nunes = 15 = MDB; Tarcisio
de Freitas = 10 = REPUBLICANOS, no piloto SP-Governador 2022 desta V2).
Usar so o numero removia TODOS os votos de qualquer candidato majoritario
cujo numero coincidisse com o do proprio partido, deixando o ranking vazio
e derrubando resultado_geral()/ranking_disputa() com dados reais. A
distincao correta usa TAMBEM o NM_VOTAVEL: um voto de legenda tem
NM_VOTAVEL = nome do PARTIDO; um voto nominal, mesmo quando NR_VOTAVEL
coincide com um numero de partido, tem NM_VOTAVEL = nome do CANDIDATO -
nunca os dois ao mesmo tempo. Verificado com dados reais que isso preserva
exatamente o mesmo resultado para cargos proporcionais (Vereador).
"""
from __future__ import annotations

import pandas as pd

_ROTULOS_NAO_VALIDOS = ("VOTO NULO", "VOTO BRANCO")


def votos_validos(votos_disputa: pd.DataFrame) -> pd.DataFrame:
    """Remove votos brancos/nulos, mantendo nominais e de legenda (validos
    para fins de percentual, conforme definicao do TSE)."""
    mask = ~votos_disputa["NM_VOTAVEL"].str.upper().isin(_ROTULOS_NAO_VALIDOS)
    return votos_disputa[mask].copy()


def votos_legenda(votos_disputa: pd.DataFrame, registro_disputa: pd.DataFrame) -> pd.DataFrame:
    """Apenas os votos de legenda: NR_VOTAVEL bate com um numero de
    partido do registro E NM_VOTAVEL e o nome desse partido (nao o nome de
    um candidato) - ver nota de correcao no docstring do modulo."""
    numeros_partido = set(registro_disputa["numero_partido"].dropna().unique())
    partidos_nomes = set(registro_disputa["partido_nome"].dropna().str.upper().unique())
    e_numero_de_partido = votos_disputa["NR_VOTAVEL"].isin(numeros_partido)
    e_nome_de_partido = votos_disputa["NM_VOTAVEL"].str.upper().isin(partidos_nomes)
    return votos_disputa[e_numero_de_partido & e_nome_de_partido].copy()


def votos_nominais(votos_disputa: pd.DataFrame, registro_disputa: pd.DataFrame) -> pd.DataFrame:
    """Remove brancos/nulos/voto de legenda: mantem apenas votos em
    candidatos individuais. Uso obrigatorio antes de agrupar por
    NR_VOTAVEL para ranking/colocacao."""
    validos = votos_validos(votos_disputa)
    legenda = votos_legenda(validos, registro_disputa)
    return validos.drop(legenda.index)


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
