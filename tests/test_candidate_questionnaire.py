"""Testes do schema de questionario (secao 8) - dados ficticios, nenhuma
pessoa real (secao 34 do briefing de expansao)."""
from src.questionnaire.candidate_questionnaire import (
    BaseEleitoral,
    Comunicacao,
    IdentificacaoAnalise,
    NivelIntensidade,
    Recursos,
    RespostaQuestionario,
    SimNao,
    Trajetoria,
    valor_normalizado_numerico,
    valor_normativo,
)


def _identificacao_ficticia() -> IdentificacaoAnalise:
    return IdentificacaoAnalise(
        cargo_pretendido="Vereador",
        uf="SP",
        municipio_base="Município Fictício",
    )


def test_valor_normativo_categoria():
    assert valor_normativo(NivelIntensidade.NENHUMA) == 0.0
    assert valor_normativo(NivelIntensidade.MODERADA) == 50.0
    assert valor_normativo(NivelIntensidade.MUITO_ALTA) == 100.0


def test_valor_normativo_binario():
    assert valor_normativo(SimNao.NAO) == 0.0
    assert valor_normativo(SimNao.SIM) == 100.0


def test_valor_normativo_none_fica_none():
    assert valor_normativo(None) is None


def test_valor_normalizado_numerico_satura_no_teto():
    # teto_referencia = 15 (config/weights.yaml) - 20 bairros deve saturar em 100
    assert valor_normalizado_numerico("numero_territorios_presenca", 20) == 100.0
    assert valor_normalizado_numerico("numero_territorios_presenca", 0) == 0.0


def test_campos_numericos_sem_resposta_fica_none():
    resposta = RespostaQuestionario(identificacao=_identificacao_ficticia())
    campos = resposta.campos_numericos()
    assert campos["conhecimento_espontaneo"] is None
    assert campos["oratoria"] is None


def test_campos_numericos_com_resposta():
    resposta = RespostaQuestionario(
        identificacao=_identificacao_ficticia(),
        comunicacao=Comunicacao(conhecimento_espontaneo=NivelIntensidade.ALTA),
    )
    assert resposta.campos_numericos()["conhecimento_espontaneo"] == 75.0


def test_indisciplina_e_inverso_de_disciplina():
    from src.questionnaire.candidate_questionnaire import Posicionamento

    resposta = RespostaQuestionario(
        identificacao=_identificacao_ficticia(),
        posicionamento=Posicionamento(disciplina=NivelIntensidade.ALTA),
    )
    campos = resposta.campos_numericos()
    assert campos["disciplina"] == 75.0
    assert campos["indisciplina"] == 25.0


def test_seguidores_redes_e_capacidade_arrecadacao_sao_numero_real():
    """Item 2 das melhorias pos-Etapa 8: perguntas quantificaveis (volume
    de seguidores, meta de arrecadacao) viram numero real em vez de faixa
    categorica (Nenhuma/Baixa/.../Muito Alta) - mais precisas."""
    resposta = RespostaQuestionario(
        identificacao=_identificacao_ficticia(),
        comunicacao=Comunicacao(seguidores_redes=50000),
        recursos=Recursos(capacidade_arrecadacao=250000.0),
    )
    campos = resposta.campos_numericos()
    # teto_referencia de seguidores_redes = 100_000 (config/weights.yaml) -> 50% do teto
    assert campos["seguidores_redes"] == 50.0
    # teto_referencia de capacidade_arrecadacao = 500_000 -> 50% do teto
    assert campos["capacidade_arrecadacao"] == 50.0


def test_seguidores_redes_zero_e_diferente_de_nao_respondido():
    """0 seguidores e uma resposta real (nota 0), diferente de campo
    nao respondido (None) - mesma disciplina ja aplicada ao resto do
    questionario."""
    resposta_zero = RespostaQuestionario(
        identificacao=_identificacao_ficticia(), comunicacao=Comunicacao(seguidores_redes=0),
    )
    resposta_none = RespostaQuestionario(identificacao=_identificacao_ficticia())
    assert resposta_zero.campos_numericos()["seguidores_redes"] == 0.0
    assert resposta_none.campos_numericos()["seguidores_redes"] is None


def test_campos_texto_livre_complementares_existem_e_sao_opcionais():
    """Item 2: perguntas qualitativas ganham texto livre complementar -
    imagem_desejada/estilo_lideranca (Posicionamento) e
    contexto_relacionamento_liderancas (BaseEleitoral) sao opcionais,
    nunca entram em campos_numericos()."""
    from src.questionnaire.candidate_questionnaire import Posicionamento

    resposta = RespostaQuestionario(
        identificacao=_identificacao_ficticia(),
        base_eleitoral=BaseEleitoral(
            relacionamento_liderancas=NivelIntensidade.ALTA,
            contexto_relacionamento_liderancas="Prefeito da cidade vizinha e aliado historico.",
        ),
        posicionamento=Posicionamento(imagem_desejada="Renovador", estilo_lideranca="Colaborativo"),
    )
    assert resposta.base_eleitoral.contexto_relacionamento_liderancas == "Prefeito da cidade vizinha e aliado historico."
    assert resposta.posicionamento.imagem_desejada == "Renovador"
    assert resposta.posicionamento.estilo_lideranca == "Colaborativo"
    campos = resposta.campos_numericos()
    assert "contexto_relacionamento_liderancas" not in campos
    assert "imagem_desejada" not in campos
    assert "estilo_lideranca" not in campos
    # a faixa categorica continua alimentando o indice normalmente
    assert campos["relacionamento_liderancas"] == 75.0


def test_padrinho_politico_nao_alimenta_campos_numericos():
    """Mesmo tratamento de partido_sigla: fato declarado, nao autoavaliacao
    categorica - nunca deve aparecer em campos_numericos() nem afetar
    nenhum indice/taxa_preenchimento."""
    identificacao = _identificacao_ficticia()
    identificacao.possui_padrinho_politico = SimNao.SIM
    identificacao.nome_padrinho_politico = "Fulano de Tal"
    resposta = RespostaQuestionario(identificacao=identificacao)
    assert "possui_padrinho_politico" not in resposta.campos_numericos()
    assert "nome_padrinho_politico" not in resposta.campos_numericos()


def test_padrinho_politico_default_none():
    resposta = RespostaQuestionario(identificacao=_identificacao_ficticia())
    assert resposta.identificacao.possui_padrinho_politico is None
    assert resposta.identificacao.nome_padrinho_politico is None


def test_patrimonio_pessoal_declarado_nao_alimenta_campos_numericos():
    """Campo novo (Recursos.patrimonio_pessoal_declarado) - so alimenta a
    comparacao direta contra o patrimonio real dos rivais projetados
    (app_candidatos.py), nunca entra em formula de indice - mesma logica
    de partido_sigla/nome_padrinho_politico (fato declarado, nao
    autoavaliacao categorica)."""
    resposta = RespostaQuestionario(
        identificacao=_identificacao_ficticia(),
        recursos=Recursos(patrimonio_pessoal_declarado=350000.0),
    )
    assert resposta.recursos.patrimonio_pessoal_declarado == 350000.0
    assert "patrimonio_pessoal_declarado" not in resposta.campos_numericos()


def test_patrimonio_pessoal_declarado_default_none():
    resposta = RespostaQuestionario(identificacao=_identificacao_ficticia())
    assert resposta.recursos.patrimonio_pessoal_declarado is None


def test_taxa_preenchimento_parcial():
    resposta = RespostaQuestionario(
        identificacao=_identificacao_ficticia(),
        trajetoria=Trajetoria(tempo_atuacao_publica=NivelIntensidade.ALTA),
    )
    taxa = resposta.taxa_preenchimento()
    assert 0 < taxa < 100


def test_taxa_preenchimento_completa_alta():
    resposta_completa = RespostaQuestionario(
        identificacao=_identificacao_ficticia(),
        trajetoria=Trajetoria(
            tempo_atuacao_publica=NivelIntensidade.ALTA,
            mandato_anterior=SimNao.SIM,
            experiencia_politica_geral=NivelIntensidade.ALTA,
            atuacao_administrativa=NivelIntensidade.MODERADA,
            projetos_realizados=NivelIntensidade.ALTA,
            resultados_concretos=NivelIntensidade.ALTA,
        ),
        base_eleitoral=BaseEleitoral(
            numero_territorios_presenca=10,
            estrutura_bairros=NivelIntensidade.MODERADA,
            apoiadores_mobilizaveis=NivelIntensidade.MODERADA,
            capacidade_eventos=NivelIntensidade.MODERADA,
            relacionamento_liderancas=NivelIntensidade.ALTA,
            relacionamento_vereadores=NivelIntensidade.MODERADA,
            relacionamento_prefeitos=NivelIntensidade.BAIXA,
            relacionamento_deputados=NivelIntensidade.BAIXA,
            relacionamento_entidades=NivelIntensidade.MODERADA,
            liderancas_regionais=NivelIntensidade.BAIXA,
            apoio_do_partido=NivelIntensidade.MODERADA,
        ),
        comunicacao=Comunicacao(
            conhecimento_espontaneo=NivelIntensidade.MODERADA,
            oratoria=NivelIntensidade.ALTA,
            desempenho_videos=NivelIntensidade.MODERADA,
            entrevistas=NivelIntensidade.MODERADA,
            debates=NivelIntensidade.MODERADA,
            resposta_criticas=NivelIntensidade.ALTA,
            seguidores_redes=8000,
            engajamento=NivelIntensidade.BAIXA,
            producao_conteudo=NivelIntensidade.MODERADA,
            equipe_comunicacao=NivelIntensidade.BAIXA,
            rejeicao_percebida=NivelIntensidade.BAIXA,
        ),
        recursos=Recursos(
            disponibilidade_tempo=NivelIntensidade.ALTA,
            capacidade_investimento_legal=NivelIntensidade.MODERADA,
            capacidade_arrecadacao=50000.0,
            equipe=NivelIntensidade.MODERADA,
            transporte=NivelIntensidade.ALTA,
            locais_reuniao=NivelIntensidade.MODERADA,
            audiovisual=NivelIntensidade.BAIXA,
            disponibilidade_viagens=NivelIntensidade.ALTA,
        ),
    )
    from src.questionnaire.candidate_questionnaire import Posicionamento

    resposta_completa.posicionamento = Posicionamento(
        resistencia_ataques=NivelIntensidade.ALTA, disciplina=NivelIntensidade.ALTA
    )
    resposta_completa.identificacao.partido_definido = SimNao.SIM
    assert resposta_completa.taxa_preenchimento() > 90.0
