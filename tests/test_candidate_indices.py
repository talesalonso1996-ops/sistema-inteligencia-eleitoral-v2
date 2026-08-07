"""Testes dos 20 indices do candidato (secao 11) - dados ficticios."""
from src.indicators.candidate_indices import _INDICES_DIRETOS, calcular_indices_candidato, weights_config
from src.questionnaire.candidate_questionnaire import (
    BaseEleitoral,
    Comunicacao,
    IdentificacaoAnalise,
    NivelIntensidade,
    Posicionamento,
    Recursos,
    RespostaQuestionario,
    SimNao,
    Trajetoria,
)


def _identificacao() -> IdentificacaoAnalise:
    return IdentificacaoAnalise(cargo_pretendido="Vereador", uf="SP", municipio_base="Município Fictício")


def _resposta_alta() -> RespostaQuestionario:
    """Candidato ficticio com respostas altas em quase tudo, exceto
    rejeicao_percebida (baixa = bom)."""
    return RespostaQuestionario(
        identificacao=IdentificacaoAnalise(
            cargo_pretendido="Vereador", uf="SP", municipio_base="Município Fictício",
            partido_definido=SimNao.SIM,
        ),
        trajetoria=Trajetoria(
            tempo_atuacao_publica=NivelIntensidade.ALTA,
            mandato_anterior=SimNao.SIM,
            experiencia_politica_geral=NivelIntensidade.ALTA,
            atuacao_administrativa=NivelIntensidade.ALTA,
            projetos_realizados=NivelIntensidade.MUITO_ALTA,
            resultados_concretos=NivelIntensidade.MUITO_ALTA,
        ),
        base_eleitoral=BaseEleitoral(
            numero_territorios_presenca=15,
            estrutura_bairros=NivelIntensidade.ALTA,
            apoiadores_mobilizaveis=NivelIntensidade.ALTA,
            capacidade_eventos=NivelIntensidade.ALTA,
            relacionamento_liderancas=NivelIntensidade.ALTA,
            relacionamento_vereadores=NivelIntensidade.ALTA,
            relacionamento_prefeitos=NivelIntensidade.MODERADA,
            relacionamento_deputados=NivelIntensidade.MODERADA,
            relacionamento_entidades=NivelIntensidade.ALTA,
            liderancas_regionais=NivelIntensidade.MODERADA,
            apoio_do_partido=NivelIntensidade.ALTA,
        ),
        comunicacao=Comunicacao(
            conhecimento_espontaneo=NivelIntensidade.ALTA,
            oratoria=NivelIntensidade.ALTA,
            desempenho_videos=NivelIntensidade.ALTA,
            entrevistas=NivelIntensidade.ALTA,
            debates=NivelIntensidade.ALTA,
            resposta_criticas=NivelIntensidade.ALTA,
            seguidores_redes=NivelIntensidade.ALTA,
            engajamento=NivelIntensidade.ALTA,
            producao_conteudo=NivelIntensidade.ALTA,
            equipe_comunicacao=NivelIntensidade.MODERADA,
            rejeicao_percebida=NivelIntensidade.BAIXA,
        ),
        recursos=Recursos(
            disponibilidade_tempo=NivelIntensidade.ALTA,
            capacidade_investimento_legal=NivelIntensidade.ALTA,
            capacidade_arrecadacao=NivelIntensidade.MODERADA,
            equipe=NivelIntensidade.ALTA,
            transporte=NivelIntensidade.ALTA,
            locais_reuniao=NivelIntensidade.ALTA,
            audiovisual=NivelIntensidade.MODERADA,
            disponibilidade_viagens=NivelIntensidade.ALTA,
        ),
        posicionamento=Posicionamento(
            resistencia_ataques=NivelIntensidade.ALTA, disciplina=NivelIntensidade.ALTA
        ),
    )


def test_todos_os_20_indices_presentes():
    resultado = calcular_indices_candidato(_resposta_alta())
    nomes_esperados = {
        "conhecimento_publico", "capilaridade_territorial", "mobilizacao", "estrutura_politica",
        "estrutura_operacional", "capacidade_financeira_legal", "comunicacao", "presenca_digital",
        "autoridade_tematica", "experiencia_politica", "experiencia_administrativa",
        "relacionamento_institucional", "apoio_partidario", "disponibilidade", "resiliencia",
        "risco_reputacional", "rejeicao_potencial", "potencial_crescimento",
        "competitividade_inicial", "prontidao_eleitoral",
    }
    assert nomes_esperados == set(resultado.indices.keys())
    assert len(nomes_esperados) == 20


def test_valores_dentro_de_0_100():
    resultado = calcular_indices_candidato(_resposta_alta())
    for nome, indice in resultado.indices.items():
        assert 0.0 <= indice.valor <= 100.0, f"{nome} fora de faixa: {indice.valor}"
        assert 0.0 <= indice.cobertura_pct <= 100.0


def test_candidato_com_respostas_altas_tem_prontidao_alta():
    resultado = calcular_indices_candidato(_resposta_alta())
    assert resultado["prontidao_eleitoral"].valor >= 60.0
    assert resultado["prontidao_eleitoral"].classificacao in ("alto", "muito_alto")


def test_resposta_vazia_gera_indices_diretos_zerados_com_cobertura_zero():
    """Sem nenhuma resposta, os 17 indices DIRETOS ficam em 0 com
    cobertura 0% (nunca preenchidos com estimativa). Os 3 indices
    DERIVADOS (potencial_crescimento, competitividade_inicial,
    prontidao_eleitoral) tem cobertura estrutural propria - eles sempre
    "existem" porque recombinam indices ja calculados (mesmo que == 0),
    entao cobertura_geral_pct nao precisa ser 0 (ver _indice_composto)."""
    from src.indicators.candidate_indices import _INDICES_DIRETOS

    resposta_vazia = RespostaQuestionario(identificacao=_identificacao())
    resultado = calcular_indices_candidato(resposta_vazia)

    for nome in _INDICES_DIRETOS:
        assert resultado[nome].valor == 0.0, nome
        assert resultado[nome].cobertura_pct == 0.0, nome

    assert resultado["prontidao_eleitoral"].valor == 0.0
    # media geral fica bem abaixo de uma resposta completa (>90), mas nao
    # necessariamente 0 - os compostos tem cobertura estrutural propria.
    resultado_completo = calcular_indices_candidato(_resposta_alta())
    assert resultado.cobertura_geral_pct < resultado_completo.cobertura_geral_pct


def test_cobertura_parcial_fica_entre_0_e_100():
    resposta_parcial = RespostaQuestionario(
        identificacao=_identificacao(),
        comunicacao=Comunicacao(conhecimento_espontaneo=NivelIntensidade.ALTA),
    )
    resultado = calcular_indices_candidato(resposta_parcial)
    # conhecimento_publico tem 2 componentes (conhecimento_espontaneo 0.7,
    # seguidores_redes 0.3) - so 1 respondido -> cobertura ~70%
    assert 0.0 < resultado["conhecimento_publico"].cobertura_pct < 100.0
    assert resultado["conhecimento_publico"].valor == 75.0  # unico componente disponivel = ALTA


def test_risco_reputacional_alto_penaliza_prontidao():
    resposta_boa = _resposta_alta()
    resposta_com_rejeicao = _resposta_alta()
    resposta_com_rejeicao.comunicacao.rejeicao_percebida = NivelIntensidade.MUITO_ALTA
    resposta_com_rejeicao.posicionamento.disciplina = NivelIntensidade.NENHUMA

    prontidao_boa = calcular_indices_candidato(resposta_boa)["prontidao_eleitoral"].valor
    prontidao_com_rejeicao = calcular_indices_candidato(resposta_com_rejeicao)["prontidao_eleitoral"].valor
    assert prontidao_com_rejeicao < prontidao_boa


def test_risco_reputacional_e_rejeicao_marcados_como_pior_quando_alto():
    resultado = calcular_indices_candidato(_resposta_alta())
    assert resultado["risco_reputacional"].pior_quando_alto is True
    assert resultado["rejeicao_potencial"].pior_quando_alto is True
    assert resultado["conhecimento_publico"].pior_quando_alto is False


def test_pesos_dos_indices_diretos_batem_com_campos_do_questionario():
    """Guarda de regressao: um nome de campo digitado errado em
    config/weights.yaml (indices_candidato.<indice>.pesos) nao levanta
    erro nenhum - RespostaQuestionario.campos_numericos().get(campo)
    simplesmente retorna None, e o peso e silenciosamente redistribuido
    como se a pergunta nunca tivesse sido respondida. Este teste falha
    alto se isso acontecer."""
    resposta_vazia = RespostaQuestionario(identificacao=_identificacao())
    chaves_reais = set(resposta_vazia.campos_numericos().keys())
    cfg = weights_config()

    for nome_indice in _INDICES_DIRETOS:
        for campo in cfg["indices_candidato"][nome_indice]["pesos"]:
            assert campo in chaves_reais, (
                f"indice '{nome_indice}' pesa o campo '{campo}', "
                f"que nao existe em RespostaQuestionario.campos_numericos()"
            )


def test_pesos_dos_indices_compostos_referenciam_indices_validos():
    cfg = weights_config()
    nomes_de_indices = set(cfg["indices_candidato"].keys())
    for nome_composto in ("competitividade_inicial", "prontidao_eleitoral"):
        for campo in cfg["indices_candidato"][nome_composto]["pesos"]:
            assert campo in nomes_de_indices, (
                f"indice composto '{nome_composto}' referencia '{campo}', "
                f"que nao e nome de indice valido"
            )


def test_potencial_crescimento_baixo_sem_estrutura():
    # muita autoavaliacao de conhecimento, mas zero estrutura -> potencial de
    # crescimento deve ficar baixo (sem "motor" para crescer)
    resposta = RespostaQuestionario(
        identificacao=_identificacao(),
        comunicacao=Comunicacao(conhecimento_espontaneo=NivelIntensidade.BAIXA, seguidores_redes=NivelIntensidade.BAIXA),
    )
    resultado = calcular_indices_candidato(resposta)
    assert resultado["potencial_crescimento"].valor == 0.0  # sem nenhum componente de estrutura respondido
