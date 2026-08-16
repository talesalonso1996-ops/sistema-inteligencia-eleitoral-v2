"""Os 23 indices do candidato (secao 11 do briefing de expansao SIET, +3
adicionados no plano de melhoria do questionario: prontidao_juridico_partidaria,
capilaridade_institucional, estrutura_campanha).

Mesma familia metodologica de src/potential_index.py (normalizacao 0-100,
pesos configuraveis em YAML, redistribuicao de peso quando um componente
falta, classificacao por faixa) - aplicada aqui sobre RESPOSTAS DE
AUTOAVALIACAO (src/questionnaire/candidate_questionnaire.py) em vez de
dado eleitoral/censitario. Ver ETAPA1_ARQUITETURA.md secao 4: estes
indices sao rotulados como autoavaliacao em toda interface/relatorio,
nunca apresentados como medicao objetiva.

20 indices "diretos" (soma ponderada de respostas do questionario, os 17
originais da secao 11 + 3 novos do plano de melhoria) + 3 "derivados"
(recombinam os diretos sem pergunta nova): potencial de crescimento,
competitividade inicial e prontidao eleitoral (indice-sintese final do
modulo)."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..questionnaire.candidate_questionnaire import RespostaQuestionario
from ..utils import get_logger, load_yaml

logger = get_logger(__name__)

# Nomes exatos dos 17 indices "diretos" (secao 11, itens 1-17) - cada um
# tem uma entrada `pesos` correspondente em
# config/weights.yaml:indices_candidato.<nome>.
_INDICES_DIRETOS = [
    "conhecimento_publico",
    "capilaridade_territorial",
    "mobilizacao",
    "estrutura_politica",
    "estrutura_operacional",
    "capacidade_financeira_legal",
    "comunicacao",
    "presenca_digital",
    "autoridade_tematica",
    "experiencia_politica",
    "experiencia_administrativa",
    "relacionamento_institucional",
    "apoio_partidario",
    "disponibilidade",
    "resiliencia",
    "risco_reputacional",
    "rejeicao_potencial",
    "prontidao_juridico_partidaria",
    "capilaridade_institucional",
    "estrutura_campanha",
]

# Indices onde nota ALTA = PIOR (mesma convencao do IVE em sessoes
# anteriores desta sessao) - usado so para rotular a interpretacao, o
# calculo numerico e identico ao dos demais.
_INDICES_INVERTIDOS = {"risco_reputacional", "rejeicao_potencial"}


def weights_config() -> dict:
    return load_yaml("config/weights.yaml")


@dataclass
class ResultadoIndice:
    nome: str
    valor: float
    cobertura_pct: float
    classificacao: str
    pior_quando_alto: bool = False


@dataclass
class ResultadoIndicesCandidato:
    indices: dict[str, ResultadoIndice] = field(default_factory=dict)
    cobertura_geral_pct: float = 0.0

    def __getitem__(self, nome: str) -> ResultadoIndice:
        return self.indices[nome]

    def valores(self) -> dict[str, float]:
        return {nome: r.valor for nome, r in self.indices.items()}


def _classificar(valor: float, limites: dict[str, int]) -> str:
    ordenado = sorted(limites.items(), key=lambda kv: kv[1], reverse=True)
    for nome, minimo in ordenado:
        if valor >= minimo:
            return nome
    return ordenado[-1][0]


def _indice_direto(nome_indice: str, campos: dict[str, float | None], cfg: dict) -> ResultadoIndice:
    """Soma ponderada dos campos de resposta que compoem `nome_indice`,
    redistribuindo peso entre os componentes de fato respondidos (mesmo
    padrao de src/potential_index.py:calcular_indice_performance)."""
    pesos_originais = dict(cfg["indices_candidato"][nome_indice]["pesos"])

    pesos_disponiveis = {}
    for campo, peso in pesos_originais.items():
        if campos.get(campo) is not None:
            pesos_disponiveis[campo] = peso
        else:
            logger.warning(
                "Indice '%s': componente '%s' nao respondido - peso redistribuido.",
                nome_indice, campo,
            )

    soma_pesos = sum(pesos_disponiveis.values())
    cobertura_pct = round(100.0 * soma_pesos / sum(pesos_originais.values()), 1) if pesos_originais else 0.0

    if soma_pesos == 0:
        valor = 0.0
    else:
        valor = sum(campos[campo] * (peso / soma_pesos) for campo, peso in pesos_disponiveis.items())

    valor = round(max(0.0, min(100.0, valor)), 1)
    classificacao = _classificar(valor, cfg["limites_classificacao"])
    return ResultadoIndice(
        nome=nome_indice,
        valor=valor,
        cobertura_pct=cobertura_pct,
        classificacao=classificacao,
        pior_quando_alto=nome_indice in _INDICES_INVERTIDOS,
    )


def _indice_potencial_crescimento(diretos: dict[str, ResultadoIndice], cfg: dict) -> ResultadoIndice:
    """Indice DERIVADO (secao 5 da arquitetura): quanto espaco de
    crescimento existe entre a estrutura ja montada (politica + mobilizacao
    + operacional) e o conhecimento publico atual. Formula documentada:

        potencial = (100 - conhecimento_publico) * (media_estrutura / 100)

    Interpretacao: sem estrutura (media_estrutura baixa), potencial fica
    baixo mesmo com conhecimento publico baixo (nao ha "motor" para
    converter obscuridade em crescimento). Com estrutura alta e
    conhecimento ainda baixo, potencial e alto - ha capacidade instalada
    ainda nao convertida em reconhecimento."""
    componentes = ["estrutura_politica", "mobilizacao", "estrutura_operacional"]
    disponiveis = [diretos[c].valor for c in componentes if c in diretos]
    cobertura_estrutura = round(100.0 * len(disponiveis) / len(componentes), 1)

    if "conhecimento_publico" not in diretos or not disponiveis:
        return ResultadoIndice("potencial_crescimento", 0.0, 0.0, _classificar(0.0, cfg["limites_classificacao"]))

    media_estrutura = sum(disponiveis) / len(disponiveis)
    conhecimento = diretos["conhecimento_publico"].valor
    valor = round((100.0 - conhecimento) * (media_estrutura / 100.0), 1)
    cobertura_pct = round((diretos["conhecimento_publico"].cobertura_pct + cobertura_estrutura) / 2, 1)
    return ResultadoIndice(
        "potencial_crescimento", valor, cobertura_pct, _classificar(valor, cfg["limites_classificacao"])
    )


def _indice_composto(nome_indice: str, diretos_e_derivados: dict[str, ResultadoIndice], cfg: dict) -> ResultadoIndice:
    """Indices DERIVADOS que recombinam outros indices ja calculados
    (competitividade_inicial, prontidao_eleitoral) - mesma logica de
    redistribuicao de peso do `_indice_direto`, mas operando sobre
    ResultadoIndice em vez de resposta bruta."""
    pesos_originais = dict(cfg["indices_candidato"][nome_indice]["pesos"])
    pesos_disponiveis = {k: v for k, v in pesos_originais.items() if k in diretos_e_derivados}
    for k in pesos_originais:
        if k not in diretos_e_derivados:
            logger.warning("Indice '%s': componente '%s' indisponivel - peso redistribuido.", nome_indice, k)

    soma_pesos = sum(pesos_disponiveis.values())
    cobertura_pct = round(100.0 * soma_pesos / sum(pesos_originais.values()), 1) if pesos_originais else 0.0
    if soma_pesos == 0:
        valor = 0.0
    else:
        valor = sum(diretos_e_derivados[k].valor * (peso / soma_pesos) for k, peso in pesos_disponiveis.items())

    if nome_indice == "prontidao_eleitoral" and "risco_reputacional" in diretos_e_derivados:
        penalidade = cfg["indices_candidato"]["prontidao_eleitoral"]["penalidade_risco_reputacional"]
        valor -= diretos_e_derivados["risco_reputacional"].valor * penalidade

    valor = round(max(0.0, min(100.0, valor)), 1)
    return ResultadoIndice(nome_indice, valor, cobertura_pct, _classificar(valor, cfg["limites_classificacao"]))


def calcular_indices_candidato(resposta: RespostaQuestionario) -> ResultadoIndicesCandidato:
    """Calcula os 20 indices do candidato a partir de uma
    RespostaQuestionario. Nunca falha por dado faltante - redistribui peso
    e reporta cobertura_pct por indice (ver docstring do modulo)."""
    cfg = weights_config()
    campos = resposta.campos_numericos()

    diretos: dict[str, ResultadoIndice] = {}
    for nome in _INDICES_DIRETOS:
        diretos[nome] = _indice_direto(nome, campos, cfg)

    resultado_final = dict(diretos)
    resultado_final["potencial_crescimento"] = _indice_potencial_crescimento(diretos, cfg)
    resultado_final["competitividade_inicial"] = _indice_composto("competitividade_inicial", resultado_final, cfg)
    resultado_final["prontidao_eleitoral"] = _indice_composto("prontidao_eleitoral", resultado_final, cfg)

    cobertura_geral = round(
        sum(r.cobertura_pct for r in resultado_final.values()) / len(resultado_final), 1
    )

    return ResultadoIndicesCandidato(indices=resultado_final, cobertura_geral_pct=cobertura_geral)
