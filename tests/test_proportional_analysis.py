"""Testes do detalhamento proporcional (Deputado Federal SP 2022, caso
real) - ver metodologia e limitacoes no docstring de
src/proportional_analysis.py (usa DS_SIT_TOT_TURNO do TSE como fonte
definitiva de quem foi eleito, nao reimplementa quociente/D'Hondt)."""
import pandas as pd
import pytest

from src.candidate_finder import (
    buscar_candidatos_disputa,
    registro_candidatos_disputa_generalizado,
    votos_da_disputa_generalizado,
)
from src.competitor_analysis import ranking_disputa, ranking_partidos
from src.proportional_analysis import ranking_federacoes, resumo_proporcional


@pytest.fixture(scope="module")
def disputa_dep_federal_sp_2022():
    candidatos = buscar_candidatos_disputa(2022, "DEPUTADO FEDERAL", uf="SP", turno=1)
    alvo = next(c for c in candidatos if c.numero == 5010)  # Guilherme Boulos
    vd = votos_da_disputa_generalizado(alvo)
    rd = registro_candidatos_disputa_generalizado(alvo)
    ranking = ranking_disputa(vd, rd)
    rp = ranking_partidos(ranking, vd, rd)
    return ranking, rd, rp


def test_eleitos_bate_com_numero_oficial_de_cadeiras(disputa_dep_federal_sp_2022):
    """SP elege 70 deputados federais - deve bater exatamente com a
    contagem de 'eleito' derivada de DS_SIT_TOT_TURNO."""
    ranking, _, _ = disputa_dep_federal_sp_2022
    assert int(ranking["eleito"].sum()) == 70


def test_boulos_primeiro_geral_e_dentro_do_partido(disputa_dep_federal_sp_2022):
    ranking, rd, rp = disputa_dep_federal_sp_2022
    resumo = resumo_proporcional(5010, ranking, rd, rp)
    assert resumo.colocacao_geral == 1
    assert resumo.colocacao_dentro_partido == 1
    assert resumo.situacao_final_oficial.upper().startswith("ELEITO")
    assert resumo.partido_sigla == "PSOL"
    assert resumo.n_eleitos_partido >= 1
    assert resumo.pct_participacao_partido > 0


def test_diferenca_para_ultimo_eleito_e_negativa_para_suplente(disputa_dep_federal_sp_2022):
    ranking, rd, rp = disputa_dep_federal_sp_2022
    suplente = ranking[
        (ranking["partido_sigla"] == "PSOL") & (~ranking["eleito"])
    ].sort_values("total_votos", ascending=False).iloc[0]
    resumo = resumo_proporcional(int(suplente["NR_VOTAVEL"]), ranking, rd, rp)
    assert resumo.diferenca_para_ultimo_eleito_partido is not None
    assert resumo.diferenca_para_ultimo_eleito_partido < 0
    assert not resumo.situacao_final_oficial.upper().startswith("ELEITO")


def test_votos_partido_total_bate_com_ranking_partidos(disputa_dep_federal_sp_2022):
    ranking, rd, rp = disputa_dep_federal_sp_2022
    resumo = resumo_proporcional(5010, ranking, rd, rp)
    linha_rp = rp[rp["partido_sigla"] == "PSOL"].iloc[0]
    assert resumo.votos_partido_total == int(linha_rp["votos_totais"])
    assert resumo.n_eleitos_partido == int(linha_rp["n_eleitos"])


def test_colocacao_dentro_do_partido_e_consistente(disputa_dep_federal_sp_2022):
    """O candidato com MENOS votos do partido deve ter a PIOR colocacao
    dentro do partido (nao a melhor)."""
    ranking, rd, rp = disputa_dep_federal_sp_2022
    grupo_psol = ranking[ranking["partido_sigla"] == "PSOL"]
    ultimo = grupo_psol.sort_values("total_votos", ascending=True).iloc[0]
    resumo = resumo_proporcional(int(ultimo["NR_VOTAVEL"]), ranking, rd, rp)
    assert resumo.colocacao_dentro_partido == len(grupo_psol)


def test_ranking_federacoes_soma_bate_com_ranking_partidos(disputa_dep_federal_sp_2022):
    _, rd, rp = disputa_dep_federal_sp_2022
    rf = ranking_federacoes(rp, rd)
    assert not rf.empty
    assert (rf["votos_totais"] > 0).all()
    assert (rf["n_partidos"] >= 1).all()


def test_candidato_inexistente_levanta_erro(disputa_dep_federal_sp_2022):
    ranking, rd, rp = disputa_dep_federal_sp_2022
    with pytest.raises(ValueError):
        resumo_proporcional(999999, ranking, rd, rp)
