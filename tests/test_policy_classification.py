"""Testes da matriz de priorizacao de pautas (secao 14.4) - dados ficticios."""
import re

from src.indicators.policy_indices import ResultadoIndicePauta, ResultadoIndicesPauta
from src.profiles.policy_classification import classificar_pauta
from src.questionnaire.policy_questionnaire import policy_weights_config

_TODOS_INDICES = [
    "relevancia_pauta", "urgencia_pauta", "demanda_territorial", "aderencia_ao_candidato",
    "credibilidade_do_candidato", "saturacao_politica", "espaco_programatico", "diferenciacao_pauta",
    "viabilidade_juridica", "viabilidade_fiscal", "viabilidade_operacional", "mensurabilidade",
    "impacto_social", "impacto_territorial", "risco_de_rejeicao", "dependencia_federativa",
    "potencial_de_comunicacao", "potencial_de_mobilizacao", "coerencia_da_plataforma",
    "indice_geral_prioridade",
]


def _resultado_com(**valores: float) -> ResultadoIndicesPauta:
    indices = {
        nome: ResultadoIndicePauta(nome, valores.get(nome, 50.0), 100.0, "moderado")
        for nome in _TODOS_INDICES
    }
    return ResultadoIndicesPauta(indices=indices, cobertura_geral_pct=100.0)


def test_prioridade_maxima():
    resultado = _resultado_com(indice_geral_prioridade=80, aderencia_ao_candidato=70)
    classificacao = classificar_pauta(resultado)
    assert classificacao.classificacao_principal == "prioridade_maxima"


def test_pauta_nao_recomendada_tem_prioridade_sobre_prioridade_maxima():
    """Uma pauta com risco de rejeicao alto NAO deve ser chamada de
    prioridade maxima so por ter nota alta em outros eixos - risco vem
    primeiro na ordem de config/policy_weights.yaml:matriz_priorizacao."""
    resultado = _resultado_com(
        indice_geral_prioridade=80, aderencia_ao_candidato=70, risco_de_rejeicao=75,
    )
    classificacao = classificar_pauta(resultado)
    assert classificacao.classificacao_principal == "pauta_nao_recomendada"


def test_pauta_saturada():
    resultado = _resultado_com(saturacao_politica=80, espaco_programatico=20)
    classificacao = classificar_pauta(resultado)
    assert "pauta_saturada" in ([classificacao.classificacao_principal] + classificacao.tambem_aplicavel)


def test_pauta_neutra_no_meio_da_faixa_vira_complementar():
    """Todos os indices em 50 (neutro) cai dentro da faixa 40-60 de
    'pauta_complementar' por desenho (config/policy_weights.yaml:
    matriz_priorizacao) - comportamento correto, nao um "sem classificacao"."""
    resultado = _resultado_com()
    classificacao = classificar_pauta(resultado)
    assert classificacao.classificacao_principal == "pauta_complementar"


def test_nenhuma_classificacao_satisfeita_retorna_none():
    # indice_geral_prioridade=65 com todo o resto em 50 (neutro) nao entra
    # em nenhuma faixa: alto demais para "complementar" (<60), baixo demais
    # para "prioridade_maxima"/"estrategica" (exigem aderencia/diferenciacao
    # >=60, aqui em 50) - caso real de "fica de fora de toda regra".
    resultado = _resultado_com(indice_geral_prioridade=65)
    classificacao = classificar_pauta(resultado)
    assert classificacao.classificacao_principal is None


def test_condicoes_da_matriz_so_referenciam_indices_reais():
    """Mesma guarda de regressao do Modulo Candidato, agora para a matriz
    de priorizacao de pautas."""
    cfg = policy_weights_config()
    nomes_validos = set(cfg["indices_pauta"].keys())
    for nome_classificacao, regra in cfg["matriz_priorizacao"].items():
        tokens = set(re.findall(r"[a-z_]+", regra["condicao"])) - {"and", "or", "not"}
        invalidos = tokens - nomes_validos
        assert not invalidos, f"classificacao '{nome_classificacao}' referencia indice(s) inexistente(s): {invalidos}"
