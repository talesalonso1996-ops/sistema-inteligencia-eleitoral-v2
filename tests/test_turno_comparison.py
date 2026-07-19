"""Testes da comparacao 1o vs 2o turno (Governador SP 2022, Tarcisio de
Freitas - caso real, 2o turno confirmado contra o resultado publico)."""
import pytest

from src.candidate_finder import (
    buscar_candidatos_disputa,
    registro_candidatos_disputa_generalizado,
    votos_da_candidatura_generalizado,
    votos_da_disputa_generalizado,
)
from src.electoral_metrics import desempenho_territorial
from src.turno_comparison import comparar_turnos


@pytest.fixture(scope="module")
def territorios_turno1_turno2():
    t1 = buscar_candidatos_disputa(2022, "GOVERNADOR", uf="SP", turno=1, numero=10)[0]
    t2 = buscar_candidatos_disputa(2022, "GOVERNADOR", uf="SP", turno=2, numero=10)[0]

    vc1 = votos_da_candidatura_generalizado(t1)
    vd1 = votos_da_disputa_generalizado(t1)
    rd1 = registro_candidatos_disputa_generalizado(t1)
    terr1 = desempenho_territorial(t1, vc1, vd1, rd1, "CD_MUNICIPIO")

    vc2 = votos_da_candidatura_generalizado(t2)
    vd2 = votos_da_disputa_generalizado(t2)
    rd2 = registro_candidatos_disputa_generalizado(t2)
    terr2 = desempenho_territorial(t2, vc2, vd2, rd2, "CD_MUNICIPIO")
    return terr1, terr2


def test_variacao_absoluta_bate_com_diferenca_real(territorios_turno1_turno2):
    """Resultado publico conhecido: Tarcisio T1 = 9.881.995 votos, T2 =
    13.480.643 votos."""
    terr1, terr2 = territorios_turno1_turno2
    comp = comparar_turnos(terr1, terr2, "CD_MUNICIPIO")
    assert comp.votos_turno1 == 9_881_995
    assert comp.votos_turno2 == 13_480_643
    assert comp.variacao_absoluta == 13_480_643 - 9_881_995
    assert comp.variacao_percentual == pytest.approx(36.42, abs=0.01)


def test_municipios_comuns_cobre_toda_sp(territorios_turno1_turno2):
    terr1, terr2 = territorios_turno1_turno2
    comp = comparar_turnos(terr1, terr2, "CD_MUNICIPIO")
    assert comp.n_territorios_comuns == 645


def test_territorios_conquistados_e_perdidos_sao_disjuntos(territorios_turno1_turno2):
    terr1, terr2 = territorios_turno1_turno2
    comp = comparar_turnos(terr1, terr2, "CD_MUNICIPIO")
    assert set(comp.territorios_conquistados).isdisjoint(comp.territorios_perdidos)
    # Tarcisio ampliou vantagem no 2o turno - ganhou municipios, nao perdeu nenhum
    assert len(comp.territorios_conquistados) > 0
    assert len(comp.territorios_perdidos) == 0


def test_detalhe_territorial_tem_uma_linha_por_municipio(territorios_turno1_turno2):
    terr1, terr2 = territorios_turno1_turno2
    comp = comparar_turnos(terr1, terr2, "CD_MUNICIPIO")
    assert len(comp.detalhe_territorial) == 645
    assert "delta_votos" in comp.detalhe_territorial.columns
