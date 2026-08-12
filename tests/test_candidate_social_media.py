"""Testes de redes sociais declaradas por candidato (TSE - rede_social_candidato,
ver src/candidate_social_media.py). Usa Governador SP 2022 (candidato 10,
Tarcisio - mesmo piloto ja usado em test_candidate_assets.py) e Governador
CE 2026 (candidato 13, Elmano de Freitas - candidatura real EM REGISTRO,
ver config/data_sources.yaml: eleicoes.2026), ambos com redes sociais reais
conferidas manualmente (2026-08-11)."""
import pytest

from src.candidate_finder import buscar_candidatos_disputa
from src.candidate_social_media import carregar_redes_sociais_candidato


@pytest.fixture(scope="module")
def candidato_governador_sp_2022():
    return buscar_candidatos_disputa(2022, "GOVERNADOR", uf="SP", turno=1, numero=10)[0]


@pytest.fixture(scope="module")
def candidato_governador_ce_2026():
    return buscar_candidatos_disputa(2026, "GOVERNADOR", uf="CE", turno=1, numero=13)[0]


def test_redes_sociais_governador_sp_2022(candidato_governador_sp_2022):
    perfil = carregar_redes_sociais_candidato(candidato_governador_sp_2022)
    assert perfil.disponivel
    assert len(perfil.redes) > 0
    assert set(perfil.redes.columns) == {"plataforma", "url"}
    assert "Instagram" in perfil.redes["plataforma"].values


def test_redes_sociais_funciona_para_candidatura_2026_ainda_nao_ocorrida(candidato_governador_ce_2026):
    """rede_social_candidato_2026 ja existe (candidato declara redes no ato
    do registro, antes da eleicao) - precisa funcionar mesmo sem nenhum
    dado de votacao para este ano."""
    perfil = carregar_redes_sociais_candidato(candidato_governador_ce_2026)
    assert perfil.disponivel
    assert len(perfil.redes) > 0
    assert "Instagram" in perfil.redes["plataforma"].values
    assert "Facebook" in perfil.redes["plataforma"].values


def test_redes_sociais_numero_inexistente_degrada_graciosamente(candidato_governador_sp_2022):
    from dataclasses import replace

    falso = replace(candidato_governador_sp_2022, numero=999999)
    perfil = carregar_redes_sociais_candidato(falso)
    assert not perfil.disponivel
    assert perfil.redes.empty
