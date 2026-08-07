"""Testes de classificacao de arquetipo (secao 12) - dados ficticios."""
import re

from src.indicators.candidate_indices import ResultadoIndice, ResultadoIndicesCandidato, weights_config
from src.profiles.candidate_archetype import classificar_arquetipo

_TODOS_INDICES = [
    "conhecimento_publico", "capilaridade_territorial", "mobilizacao", "estrutura_politica",
    "estrutura_operacional", "capacidade_financeira_legal", "comunicacao", "presenca_digital",
    "autoridade_tematica", "experiencia_politica", "experiencia_administrativa",
    "relacionamento_institucional", "apoio_partidario", "disponibilidade", "resiliencia",
    "risco_reputacional", "rejeicao_potencial", "potencial_crescimento",
    "competitividade_inicial", "prontidao_eleitoral",
]


def _resultado_com(**valores: float) -> ResultadoIndicesCandidato:
    """Monta um ResultadoIndicesCandidato ficticio - indices nao
    informados em `valores` ficam em 50 (neutro), para nao acionar regras
    de arquetipo por acidente."""
    indices = {
        nome: ResultadoIndice(nome, valores.get(nome, 50.0), 100.0, "moderado")
        for nome in _TODOS_INDICES
    }
    return ResultadoIndicesCandidato(indices=indices, cobertura_geral_pct=100.0)


def test_lideranca_comunitaria():
    resultado = _resultado_com(capilaridade_territorial=80, mobilizacao=75, presenca_digital=20)
    arquetipo = classificar_arquetipo(resultado)
    assert arquetipo.arquetipo_principal == "lideranca_comunitaria"
    assert "Vereador" in arquetipo.cargos_compativeis


def test_especialista_tecnico():
    resultado = _resultado_com(autoridade_tematica=85, experiencia_administrativa=60)
    arquetipo = classificar_arquetipo(resultado)
    assert "especialista_tecnico" in ([arquetipo.arquetipo_principal] + arquetipo.arquetipos_secundarios)


def test_candidatura_em_construcao_quando_prontidao_baixa():
    resultado = _resultado_com(prontidao_eleitoral=15)
    arquetipo = classificar_arquetipo(resultado)
    assert "candidatura_em_construcao" in ([arquetipo.arquetipo_principal] + arquetipo.arquetipos_secundarios)
    assert arquetipo.cargos_compativeis == [] if arquetipo.arquetipo_principal == "candidatura_em_construcao" else True


def test_candidatura_de_alto_risco_quando_risco_reputacional_alto():
    resultado = _resultado_com(risco_reputacional=75)
    arquetipo = classificar_arquetipo(resultado)
    assert "candidatura_de_alto_risco" in ([arquetipo.arquetipo_principal] + arquetipo.arquetipos_secundarios)


def test_nenhum_arquetipo_satisfeito_retorna_none():
    # todos os indices em 50 (neutro) nao deve acionar nenhuma regra >=60/>=70/<40/<60
    resultado = _resultado_com()
    arquetipo = classificar_arquetipo(resultado)
    assert arquetipo.arquetipo_principal is None
    assert arquetipo.arquetipos_secundarios == []


def test_condicoes_de_arquetipo_so_referenciam_indices_reais():
    """Guarda de regressao: a condicao de um arquetipo em
    config/weights.yaml e avaliada com `eval` (ver
    src/profiles/candidate_archetype.py:_avaliar_condicao), que engole
    qualquer excecao e retorna False - um nome de indice digitado errado
    nunca levantaria erro, so faria a regra nunca disparar, silenciosamente.
    Este teste falha alto se isso acontecer, em vez de deixar o bug
    invisivel dentro do try/except em producao."""
    cfg = weights_config()
    nomes_validos = set(cfg["indices_candidato"].keys())
    for nome_arquetipo, regra in cfg["arquetipos"].items():
        tokens = set(re.findall(r"[a-z_]+", regra["condicao"])) - {"and", "or", "not"}
        invalidos = tokens - nomes_validos
        assert not invalidos, f"arquetipo '{nome_arquetipo}' referencia indice(s) inexistente(s): {invalidos}"


def test_multiplos_arquetipos_principal_e_secundarios():
    resultado = _resultado_com(
        comunicacao=80, presenca_digital=80,  # comunicador
        apoio_partidario=80, estrutura_politica=70,  # candidato_partidario
    )
    arquetipo = classificar_arquetipo(resultado)
    assert arquetipo.arquetipo_principal is not None
    todos_satisfeitos = [arquetipo.arquetipo_principal] + arquetipo.arquetipos_secundarios
    assert "comunicador" in todos_satisfeitos
    assert "candidato_partidario" in todos_satisfeitos
