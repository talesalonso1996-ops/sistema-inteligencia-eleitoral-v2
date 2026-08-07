from src.indicators.candidate_indices import calcular_indices_candidato
from src.indicators.policy_indices import calcular_indices_pauta
from src.integration.candidate_territory_policy_matrix import (
    compatibilidade_candidato_pauta,
    integration_weights_config,
    montar_matriz_candidato_territorio_pauta,
    perfil_territorial_municipio,
)
from src.platforms.platform_builder import verificar_gate_competencia
from src.questionnaire.candidate_questionnaire import (
    IdentificacaoAnalise,
    NivelIntensidade,
    Posicionamento,
    RespostaQuestionario,
)
from src.questionnaire.policy_questionnaire import PropostaPauta

_UF_TESTE = "SP"
_MUNICIPIO_TESTE = "Pitangueiras"  # cidade pequena do interior de SP, dado ja usado por outros testes do projeto


def test_pesos_de_compatibilidade_candidato_pauta_somam_1():
    pesos = integration_weights_config()["indice_compatibilidade_candidato_pauta"]["pesos"]
    assert abs(sum(pesos.values()) - 1.0) < 1e-9


def test_perfil_territorial_municipio_real_traz_dado_real_do_censo_e_rais():
    perfil = perfil_territorial_municipio(_UF_TESTE, _MUNICIPIO_TESTE)
    assert perfil.municipio == "PITANGUEIRAS"
    assert perfil.codigo_municipio_tse is not None
    assert perfil.n_setores_censitarios > 0
    assert not perfil.avisos

    percentuais = {"pct_agua_encanada", "pct_esgoto_adequado", "pct_coleta_lixo", "pct_alfabetizado_15mais", "pct_preta_parda"}
    for var in percentuais:
        assert var in perfil.indicadores_piramide_maslow
        valor = perfil.indicadores_piramide_maslow[var]
        assert valor is not None and 0.0 <= valor <= 100.0

    assert "renda_media_responsavel" in perfil.indicadores_piramide_maslow
    assert perfil.indicadores_piramide_maslow["renda_media_responsavel"] > 0

    assert perfil.perfil_economico is not None


def test_perfil_territorial_municipio_inexistente_reporta_aviso_sem_fabricar():
    perfil = perfil_territorial_municipio(_UF_TESTE, "MUNICIPIO_QUE_NAO_EXISTE_TESTE_XYZ")
    assert perfil.codigo_municipio_tse is None
    assert perfil.n_setores_censitarios == 0
    assert perfil.indicadores_piramide_maslow == {}
    assert perfil.avisos


def _identificacao_e_indices_candidato(temas=None):
    identificacao = IdentificacaoAnalise(cargo_pretendido="Prefeito", uf=_UF_TESTE, municipio_base=_MUNICIPIO_TESTE)
    resposta = RespostaQuestionario(
        identificacao=identificacao,
        posicionamento=Posicionamento(temas_identificacao=temas or []),
    )
    return identificacao, calcular_indices_candidato(resposta)


def test_compatibilidade_zera_quando_gate_reprova_mesmo_com_boa_autoavaliacao():
    """A unica forma real de reprovar o gate neste dataset (todas as 35
    pautas tem competencia comum aos 4 niveis - achado ja documentado em
    ETAPA1_ARQUITETURA.md) e um cargo nao reconhecido. Serve para provar
    que uma boa autoavaliacao NUNCA maquia uma pauta fora da competencia
    real do cargo."""
    identificacao, indices_candidato = _identificacao_e_indices_candidato()
    proposta = PropostaPauta(
        pauta_id="saneamento", cargo_analisado="Cargo Nao Reconhecido",
        aderencia_candidato=NivelIntensidade.MUITO_ALTA,
    )
    indices_pauta = calcular_indices_pauta(proposta)
    gate = verificar_gate_competencia(proposta.pauta_id, proposta.cargo_analisado)
    assert not gate.aprovado

    resultado = compatibilidade_candidato_pauta(identificacao, indices_candidato, proposta, indices_pauta, gate)
    assert resultado.elegivel_pelo_cargo is False
    assert resultado.indice_compatibilidade == 0.0


def test_compatibilidade_real_com_gate_aprovado_e_autoavaliacao_alta():
    identificacao, indices_candidato = _identificacao_e_indices_candidato(temas=["saneamento basico"])
    proposta = PropostaPauta(
        pauta_id="saneamento", cargo_analisado="Prefeito", territorio_afetado="Pitangueiras",
        aderencia_candidato=NivelIntensidade.MUITO_ALTA,
    )
    indices_pauta = calcular_indices_pauta(proposta)
    gate = verificar_gate_competencia(proposta.pauta_id, proposta.cargo_analisado)
    assert gate.aprovado

    resultado = compatibilidade_candidato_pauta(identificacao, indices_candidato, proposta, indices_pauta, gate)
    assert resultado.elegivel_pelo_cargo is True
    assert 0.0 <= resultado.indice_compatibilidade <= 100.0
    assert resultado.aderencia_candidato_pauta == 100.0  # NivelIntensidade.MUITO_ALTA
    assert resultado.classificacao in {"muito_alto", "alto", "moderado", "baixo", "critico"}
    assert resultado.mesmo_territorio_declarado is True


def test_mesmo_territorio_declarado_e_none_quando_campo_da_pauta_fica_vazio():
    identificacao, indices_candidato = _identificacao_e_indices_candidato()
    proposta = PropostaPauta(pauta_id="saneamento", cargo_analisado="Prefeito")  # territorio_afetado vazio
    indices_pauta = calcular_indices_pauta(proposta)
    gate = verificar_gate_competencia(proposta.pauta_id, proposta.cargo_analisado)

    resultado = compatibilidade_candidato_pauta(identificacao, indices_candidato, proposta, indices_pauta, gate)
    assert resultado.mesmo_territorio_declarado is None


def test_montar_matriz_ordena_pautas_da_mais_para_a_menos_compativel():
    identificacao, indices_candidato = _identificacao_e_indices_candidato()

    proposta_forte = PropostaPauta(
        pauta_id="saneamento", cargo_analisado="Prefeito", aderencia_candidato=NivelIntensidade.MUITO_ALTA,
    )
    proposta_fraca = PropostaPauta(
        pauta_id="cultura", cargo_analisado="Prefeito", aderencia_candidato=NivelIntensidade.NENHUMA,
    )
    pautas = []
    for proposta in (proposta_fraca, proposta_forte):  # ordem de entrada propositalmente invertida
        indices_pauta = calcular_indices_pauta(proposta)
        gate = verificar_gate_competencia(proposta.pauta_id, proposta.cargo_analisado)
        pautas.append((proposta, indices_pauta, gate))

    resultado = montar_matriz_candidato_territorio_pauta(identificacao, indices_candidato, pautas)
    assert resultado.perfil_territorial.municipio == "PITANGUEIRAS"
    assert [c.pauta_id for c in resultado.compatibilidades] == ["saneamento", "cultura"]
    assert resultado.compatibilidades[0].indice_compatibilidade >= resultado.compatibilidades[1].indice_compatibilidade
