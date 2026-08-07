"""Testes do schema de pauta/plataforma (secao 10) - dados ficticios."""
import pytest

from src.questionnaire.candidate_questionnaire import NivelIntensidade, SimNao
from src.questionnaire.policy_questionnaire import PropostaPauta, pautas_disponiveis, policy_areas_config


def test_pautas_disponiveis_tem_35_itens():
    assert len(pautas_disponiveis()) == 35


def test_area_le_metadados_reais_de_saude():
    proposta = PropostaPauta(pauta_id="saude", cargo_analisado="Prefeito")
    area = proposta.area()
    assert area["label"] == "Saude"
    assert "municipal" in area["niveis_competencia"]
    assert "base_legal" in area


def test_area_com_pauta_id_invalido_levanta_erro_claro():
    proposta = PropostaPauta(pauta_id="pauta_que_nao_existe", cargo_analisado="Prefeito")
    with pytest.raises(ValueError, match="nao existe em config/policy_areas.yaml"):
        proposta.area()


def test_campos_numericos_sem_resposta_fica_none():
    proposta = PropostaPauta(pauta_id="educacao", cargo_analisado="Vereador")
    campos = proposta.campos_numericos()
    assert campos["gravidade_problema"] is None
    assert campos["dados_comprovam_problema"] is None


def test_campos_derivados_inversos():
    proposta = PropostaPauta(
        pauta_id="educacao", cargo_analisado="Vereador",
        risco_juridico=NivelIntensidade.ALTA,
        exige_alteracao_legislativa=SimNao.SIM,
        depende_outro_ente=SimNao.NAO,
        saturacao_outros_candidatos=NivelIntensidade.BAIXA,
    )
    campos = proposta.campos_numericos()
    assert campos["risco_juridico"] == 75.0
    assert campos["baixo_risco_juridico"] == 25.0
    assert campos["exige_alteracao_legislativa"] == 100.0
    assert campos["nao_exige_alteracao_legislativa"] == 0.0
    assert campos["depende_outro_ente"] == 0.0
    assert campos["nao_depende_outro_ente"] == 100.0
    assert campos["saturacao_outros_candidatos"] == 25.0
    assert campos["baixa_saturacao"] == 75.0


def test_taxa_preenchimento_parcial():
    proposta = PropostaPauta(
        pauta_id="saneamento", cargo_analisado="Prefeito", gravidade_problema=NivelIntensidade.ALTA
    )
    taxa = proposta.taxa_preenchimento()
    assert 0 < taxa < 100


def test_todas_as_35_pautas_tem_niveis_competencia_e_orgaos():
    """Guarda de regressao: config/policy_areas.yaml e editado a mao -
    garante que nenhuma pauta ficou incompleta (sem isso, o gate de
    competencia falharia silenciosamente para essa pauta)."""
    cfg = policy_areas_config()["pautas"]
    for pauta_id, area in cfg.items():
        assert area.get("niveis_competencia"), f"{pauta_id} sem niveis_competencia"
        assert area.get("base_legal"), f"{pauta_id} sem base_legal"
        assert area.get("orgaos_por_nivel"), f"{pauta_id} sem orgaos_por_nivel"
        for nivel in area["niveis_competencia"]:
            assert nivel in area["orgaos_por_nivel"], (
                f"{pauta_id}: nivel '{nivel}' esta em niveis_competencia mas nao tem "
                f"entrada correspondente em orgaos_por_nivel"
            )
