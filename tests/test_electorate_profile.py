"""Testes do perfil do eleitorado por secao (TSE, dataset "Eleitorado
Atual") - Fase 5. Usa o Acre real (UF pequena, rapido de baixar/converter)
para validar a agregacao contra dados reais."""
import pandas as pd
import pytest

from src.candidate_finder import buscar_candidatos_disputa, votos_da_disputa_generalizado
from src.electoral_metrics import desempenho_territorial
from src.electorate_profile import (
    LIMITACAO_VINTAGE,
    carregar_perfil_eleitorado_secao,
    comparar_eleitorado_vs_votos_candidato,
    perfil_eleitorado_por_territorio,
)


@pytest.fixture(scope="module")
def perfil_eleitorado_ac():
    return carregar_perfil_eleitorado_secao("AC")


def test_limitacao_vintage_menciona_nao_historico():
    """A ressalva de vintage precisa deixar explicito que o dado NAO e um
    retrato historico na data da eleicao - regra do projeto (nunca esconder
    limitacoes metodologicas)."""
    assert "hoje" in LIMITACAO_VINTAGE.lower() or "atual" in LIMITACAO_VINTAGE.lower()
    assert "aproximad" in LIMITACAO_VINTAGE.lower()


def test_carregar_perfil_eleitorado_secao_ac_tem_dados_reais(perfil_eleitorado_ac):
    assert not perfil_eleitorado_ac.empty
    assert perfil_eleitorado_ac["qt_eleitores_total"].sum() > 500_000  # Acre tem ~600 mil eleitores
    for col in ("pct_eleitores_jovens", "pct_eleitores_60mais", "pct_eleitores_superior", "pct_eleitores_feminino"):
        assert col in perfil_eleitorado_ac.columns
        assert perfil_eleitorado_ac[col].dropna().between(0, 100).all()


def test_perfil_eleitorado_por_territorio_municipio_cobre_todo_acre(perfil_eleitorado_ac):
    """Sem filtro de municipio (candidatura estadual) - deve cobrir os 22
    municipios do Acre."""
    agregado = perfil_eleitorado_por_territorio(perfil_eleitorado_ac, None, "CD_MUNICIPIO")
    assert agregado["CD_MUNICIPIO"].nunique() == 22
    # a soma dos totais por municipio deve bater com o total da UF
    assert agregado["qt_eleitores_total"].sum() == pytest.approx(
        perfil_eleitorado_ac["qt_eleitores_total"].sum()
    )


def test_perfil_eleitorado_por_territorio_filtra_por_municipio(perfil_eleitorado_ac):
    algum_municipio = int(perfil_eleitorado_ac["CD_MUNICIPIO"].iloc[0])
    agregado = perfil_eleitorado_por_territorio(perfil_eleitorado_ac, algum_municipio, "NR_ZONA")
    assert not agregado.empty
    # todo eleitor agregado deve vir so daquele municipio
    esperado = perfil_eleitorado_ac[perfil_eleitorado_ac["CD_MUNICIPIO"] == algum_municipio]["qt_eleitores_total"].sum()
    assert agregado["qt_eleitores_total"].sum() == esperado


def test_perfil_eleitorado_por_territorio_nivel_invalido_retorna_vazio(perfil_eleitorado_ac):
    assert perfil_eleitorado_por_territorio(perfil_eleitorado_ac, None, "secao_id").empty


def test_comparar_eleitorado_vs_votos_candidato_governador_acre(perfil_eleitorado_ac):
    cand = buscar_candidatos_disputa(2022, "GOVERNADOR", uf="AC", turno=1, numero=11)[0]
    vd = votos_da_disputa_generalizado(cand)
    from src.candidate_finder import registro_candidatos_disputa_generalizado, votos_da_candidatura_generalizado

    vc = votos_da_candidatura_generalizado(cand)
    rd = registro_candidatos_disputa_generalizado(cand)
    terr_mun = desempenho_territorial(cand, vc, vd, rd, "CD_MUNICIPIO")

    perfil_mun = perfil_eleitorado_por_territorio(perfil_eleitorado_ac, None, "CD_MUNICIPIO")
    comparativo = comparar_eleitorado_vs_votos_candidato(perfil_mun, terr_mun, "CD_MUNICIPIO")

    assert not comparativo.empty
    assert len(comparativo) == len(terr_mun)
    assert "pct_eleitores_jovens" in comparativo.columns
    assert comparativo["pct_eleitores_jovens"].notna().all()


def test_comparar_eleitorado_vs_votos_candidato_vazio_sem_dados():
    assert comparar_eleitorado_vs_votos_candidato(pd.DataFrame(), pd.DataFrame(), "CD_MUNICIPIO").empty
