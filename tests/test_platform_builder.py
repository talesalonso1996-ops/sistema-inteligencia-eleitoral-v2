"""Testes do construtor de plataforma (secao 14.5), com foco no gate de
competencia do cargo - dados ficticios."""
from src.indicators.policy_indices import calcular_indices_pauta
from src.platforms.platform_builder import (
    CARGO_NIVEL_GOVERNO,
    montar_plataforma,
    verificar_gate_competencia,
)
from src.profiles.policy_classification import classificar_pauta
from src.questionnaire.candidate_questionnaire import NivelIntensidade as N
from src.questionnaire.candidate_questionnaire import SimNao
from src.questionnaire.policy_questionnaire import PropostaPauta, pautas_disponiveis


def test_gate_aprova_combinacao_valida():
    gate = verificar_gate_competencia("saude", "Prefeito")
    assert gate.aprovado is True
    assert gate.nivel_governo_cargo == "municipal"


def test_gate_reprova_pauta_inexistente():
    gate = verificar_gate_competencia("pauta_inventada_para_teste", "Prefeito")
    assert gate.aprovado is False
    assert "nao existe" in gate.motivo


def test_gate_reprova_cargo_nao_reconhecido():
    gate = verificar_gate_competencia("saude", "Cargo Que Nao Existe")
    assert gate.aprovado is False
    assert "nao reconhecido" in gate.motivo


def test_todos_os_cargos_do_modulo_candidato_estao_mapeados():
    """Guarda de regressao: se um cargo novo for adicionado a
    app.py:_CARGOS_MODO1 sem entrar em CARGO_NIVEL_GOVERNO, o gate de
    competencia reprovaria silenciosamente toda pauta para esse cargo."""
    cargos_modo1 = [
        "Vereador", "Prefeito", "Deputado Estadual", "Deputado Distrital",
        "Deputado Federal", "Senador", "Governador", "Presidente",
    ]
    for cargo in cargos_modo1:
        assert cargo in CARGO_NIVEL_GOVERNO, f"cargo '{cargo}' sem nivel de governo mapeado"


def test_todas_as_pautas_aprovam_pelo_menos_um_cargo():
    """Cada uma das 35 pautas deve ter competencia real documentada para
    pelo menos um cargo - senao a pauta nunca poderia virar plataforma
    para ninguem, o que indicaria erro de cadastro em policy_areas.yaml."""
    for pauta_id in pautas_disponiveis():
        aprovados = [
            cargo for cargo in CARGO_NIVEL_GOVERNO
            if verificar_gate_competencia(pauta_id, cargo).aprovado
        ]
        assert aprovados, f"pauta '{pauta_id}' nao aprova nenhum cargo"


def test_montar_plataforma_com_gate_aprovado_preenche_orgao_responsavel():
    proposta = PropostaPauta(
        pauta_id="saude", cargo_analisado="Prefeito",
        problema_central="Fila de espera na UBS central do municipio ficticio",
        proposta_principal="Ampliar horario de atendimento da UBS central",
    )
    indices = calcular_indices_pauta(proposta)
    classificacao = classificar_pauta(indices)
    plataforma = montar_plataforma(proposta, indices, classificacao)

    assert plataforma.gate.aprovado is True
    assert "Secretaria Municipal de Saude" in plataforma.orgao_responsavel
    assert plataforma.problema_central == "Fila de espera na UBS central do municipio ficticio"
    assert plataforma.proposta_principal == "Ampliar horario de atendimento da UBS central"


def test_montar_plataforma_com_gate_reprovado_nao_inventa_orgao():
    proposta = PropostaPauta(pauta_id="saude", cargo_analisado="Cargo Que Nao Existe")
    indices = calcular_indices_pauta(proposta)
    classificacao = classificar_pauta(indices)
    plataforma = montar_plataforma(proposta, indices, classificacao)

    assert plataforma.gate.aprovado is False
    assert "NAO GERADO" in plataforma.orgao_responsavel


def test_montar_plataforma_nao_fabrica_causas_e_consequencias():
    """Campos que exigiriam elaboracao qualitativa nao coletada devem
    ficar marcados como pendentes, nunca preenchidos com texto inventado
    sobre um problema real que o sistema nao conhece."""
    proposta = PropostaPauta(pauta_id="educacao", cargo_analisado="Vereador")
    indices = calcular_indices_pauta(proposta)
    classificacao = classificar_pauta(indices)
    plataforma = montar_plataforma(proposta, indices, classificacao)

    assert "requer elaboracao qualitativa adicional" in plataforma.causas
    assert "requer elaboracao qualitativa adicional" in plataforma.consequencias
    assert "requer elaboracao qualitativa adicional" in plataforma.etapas


def test_montar_plataforma_reflete_prioridade_calculada():
    proposta = PropostaPauta(
        pauta_id="educacao", cargo_analisado="Prefeito",
        gravidade_problema=N.MUITO_ALTA, urgencia=N.ALTA, abrangencia_territorial=N.ALTA,
        aderencia_candidato=N.MUITO_ALTA, credibilidade_candidato=N.ALTA,
        diferenciacao=N.ALTA, saturacao_outros_candidatos=N.BAIXA,
        risco_juridico=N.BAIXA, risco_fiscal=N.BAIXA, risco_rejeicao=N.BAIXA,
        exige_alteracao_legislativa=SimNao.NAO, existe_fonte_financiamento=SimNao.SIM,
        depende_outro_ente=SimNao.NAO, existe_prazo_definido=SimNao.SIM,
        potencial_comunicacao=N.ALTA,
    )
    indices = calcular_indices_pauta(proposta)
    classificacao = classificar_pauta(indices)
    plataforma = montar_plataforma(proposta, indices, classificacao)
    assert plataforma.prioridade is not None
