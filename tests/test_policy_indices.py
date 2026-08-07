"""Testes dos 20 indices de pauta (secao 14.3) - dados ficticios."""
from src.indicators.policy_indices import _INDICES_DIRETOS, calcular_indices_pauta
from src.questionnaire.candidate_questionnaire import NivelIntensidade as N
from src.questionnaire.candidate_questionnaire import SimNao
from src.questionnaire.policy_questionnaire import PropostaPauta, policy_weights_config


def _proposta_forte() -> PropostaPauta:
    """Pauta ficticia com respostas favoraveis em quase tudo, exceto
    saturacao/riscos (baixos = bom)."""
    return PropostaPauta(
        pauta_id="educacao",
        cargo_analisado="Prefeito",
        problema_central="Fila de espera em creches no municipio ficticio.",
        publico_afetado="Familias com criancas de 0 a 3 anos",
        territorio_afetado="Zona leste do municipio ficticio",
        proposta_principal="Construir 3 novos CEIs na zona leste",
        propostas_complementares=["Ampliar vagas em CEIs existentes"],
        gravidade_problema=N.ALTA,
        urgencia=N.ALTA,
        abrangencia_territorial=N.ALTA,
        aderencia_candidato=N.MUITO_ALTA,
        credibilidade_candidato=N.ALTA,
        experiencia_anterior_candidato=N.ALTA,
        saturacao_outros_candidatos=N.BAIXA,
        diferenciacao=N.ALTA,
        risco_juridico=N.BAIXA,
        risco_fiscal=N.MODERADA,
        risco_rejeicao=N.BAIXA,
        potencial_comunicacao=N.ALTA,
        potencial_mobilizacao=N.ALTA,
        coerencia_com_outras_pautas=N.ALTA,
        dados_comprovam_problema=SimNao.SIM,
        existe_estimativa_custo=SimNao.SIM,
        existe_fonte_financiamento=SimNao.SIM,
        existe_prazo_definido=SimNao.SIM,
        existe_indicador_resultado=SimNao.SIM,
        existe_meta_definida=SimNao.SIM,
        depende_outro_ente=SimNao.NAO,
        exige_alteracao_legislativa=SimNao.NAO,
        exige_parceria=SimNao.NAO,
    )


def test_todos_os_20_indices_presentes():
    resultado = calcular_indices_pauta(_proposta_forte())
    nomes_esperados = set(_INDICES_DIRETOS) | {"indice_geral_prioridade"}
    assert nomes_esperados == set(resultado.indices.keys())
    assert len(nomes_esperados) == 20


def test_valores_dentro_de_0_100():
    resultado = calcular_indices_pauta(_proposta_forte())
    for nome, r in resultado.indices.items():
        assert 0.0 <= r.valor <= 100.0, f"{nome} fora de faixa: {r.valor}"
        assert 0.0 <= r.cobertura_pct <= 100.0


def test_proposta_forte_tem_indice_geral_alto():
    resultado = calcular_indices_pauta(_proposta_forte())
    assert resultado["indice_geral_prioridade"].valor >= 60.0


def test_proposta_vazia_gera_indices_diretos_zerados():
    proposta_vazia = PropostaPauta(pauta_id="educacao", cargo_analisado="Prefeito")
    resultado = calcular_indices_pauta(proposta_vazia)
    for nome in _INDICES_DIRETOS:
        assert resultado[nome].valor == 0.0
        assert resultado[nome].cobertura_pct == 0.0


def test_saturacao_alta_penaliza_indice_geral():
    proposta_saturada = _proposta_forte()
    proposta_saturada.saturacao_outros_candidatos = N.MUITO_ALTA
    resultado_normal = calcular_indices_pauta(_proposta_forte())
    resultado_saturado = calcular_indices_pauta(proposta_saturada)
    assert resultado_saturado["indice_geral_prioridade"].valor < resultado_normal["indice_geral_prioridade"].valor


def test_indices_invertidos_marcados_corretamente():
    resultado = calcular_indices_pauta(_proposta_forte())
    assert resultado["saturacao_politica"].pior_quando_alto is True
    assert resultado["risco_de_rejeicao"].pior_quando_alto is True
    assert resultado["dependencia_federativa"].pior_quando_alto is True
    assert resultado["relevancia_pauta"].pior_quando_alto is False


def test_pesos_dos_indices_diretos_batem_com_campos_da_proposta():
    """Guarda de regressao (mesmo tipo de bug ja pego uma vez no Modulo
    Candidato): nome de campo digitado errado em config/policy_weights.yaml
    seria silenciosamente redistribuido como 'nao respondido'."""
    proposta_vazia = PropostaPauta(pauta_id="educacao", cargo_analisado="Prefeito")
    chaves_reais = set(proposta_vazia.campos_numericos().keys())
    cfg = policy_weights_config()

    for nome_indice in _INDICES_DIRETOS:
        for campo in cfg["indices_pauta"][nome_indice]["pesos"]:
            assert campo in chaves_reais, (
                f"indice '{nome_indice}' pesa o campo '{campo}', que nao existe em "
                f"PropostaPauta.campos_numericos()"
            )


def test_pesos_do_indice_geral_referenciam_indices_validos():
    cfg = policy_weights_config()
    nomes_de_indices = set(cfg["indices_pauta"].keys())
    for campo in cfg["indices_pauta"]["indice_geral_prioridade"]["pesos"]:
        assert campo in nomes_de_indices
