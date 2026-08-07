"""Os 20 indices de pauta/plataforma (secao 14.3 do briefing de expansao
SIET). Mesma familia metodologica de candidate_indices.py (que por sua vez
segue src/potential_index.py): normalizacao 0-100, pesos configuraveis em
YAML (config/policy_weights.yaml), redistribuicao de peso quando falta
resposta, classificacao por faixa.

19 indices "diretos" (itens 1-19 da secao 14.3) + 1 "derivado" (item 20,
Indice Geral de Prioridade da Pauta - recombina os diretos sem pergunta
nova)."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..questionnaire.policy_questionnaire import PropostaPauta, policy_weights_config
from ..utils import get_logger

logger = get_logger(__name__)

_INDICES_DIRETOS = [
    "relevancia_pauta",
    "urgencia_pauta",
    "demanda_territorial",
    "aderencia_ao_candidato",
    "credibilidade_do_candidato",
    "saturacao_politica",
    "espaco_programatico",
    "diferenciacao_pauta",
    "viabilidade_juridica",
    "viabilidade_fiscal",
    "viabilidade_operacional",
    "mensurabilidade",
    "impacto_social",
    "impacto_territorial",
    "risco_de_rejeicao",
    "dependencia_federativa",
    "potencial_de_comunicacao",
    "potencial_de_mobilizacao",
    "coerencia_da_plataforma",
]

# Indices onde nota ALTA = PIOR - mesma convencao de candidate_indices.py.
_INDICES_INVERTIDOS = {"saturacao_politica", "risco_de_rejeicao", "dependencia_federativa"}


@dataclass
class ResultadoIndicePauta:
    nome: str
    valor: float
    cobertura_pct: float
    classificacao: str
    pior_quando_alto: bool = False


@dataclass
class ResultadoIndicesPauta:
    indices: dict[str, ResultadoIndicePauta] = field(default_factory=dict)
    cobertura_geral_pct: float = 0.0

    def __getitem__(self, nome: str) -> ResultadoIndicePauta:
        return self.indices[nome]

    def valores(self) -> dict[str, float]:
        return {nome: r.valor for nome, r in self.indices.items()}


def _classificar(valor: float, limites: dict[str, int]) -> str:
    ordenado = sorted(limites.items(), key=lambda kv: kv[1], reverse=True)
    for nome, minimo in ordenado:
        if valor >= minimo:
            return nome
    return ordenado[-1][0]


def _indice_direto(nome_indice: str, campos: dict[str, float | None], cfg: dict) -> ResultadoIndicePauta:
    pesos_originais = dict(cfg["indices_pauta"][nome_indice]["pesos"])

    pesos_disponiveis = {}
    for campo, peso in pesos_originais.items():
        if campos.get(campo) is not None:
            pesos_disponiveis[campo] = peso
        else:
            logger.warning(
                "Indice de pauta '%s': componente '%s' nao respondido - peso redistribuido.",
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
    return ResultadoIndicePauta(
        nome=nome_indice,
        valor=valor,
        cobertura_pct=cobertura_pct,
        classificacao=classificacao,
        pior_quando_alto=nome_indice in _INDICES_INVERTIDOS,
    )


def _indice_geral_prioridade(diretos: dict[str, ResultadoIndicePauta], cfg: dict) -> ResultadoIndicePauta:
    """Indice DERIVADO (item 20, secao 14.3) - recombina os 19 diretos,
    penalizado pela saturacao politica (mesmo padrao de
    prontidao_eleitoral em candidate_indices.py)."""
    nome_indice = "indice_geral_prioridade"
    pesos_originais = dict(cfg["indices_pauta"][nome_indice]["pesos"])
    pesos_disponiveis = {k: v for k, v in pesos_originais.items() if k in diretos}
    for k in pesos_originais:
        if k not in diretos:
            logger.warning("Indice de pauta '%s': componente '%s' indisponivel.", nome_indice, k)

    soma_pesos = sum(pesos_disponiveis.values())
    cobertura_pct = round(100.0 * soma_pesos / sum(pesos_originais.values()), 1) if pesos_originais else 0.0
    if soma_pesos == 0:
        valor = 0.0
    else:
        valor = sum(diretos[k].valor * (peso / soma_pesos) for k, peso in pesos_disponiveis.items())

    if "saturacao_politica" in diretos:
        penalidade = cfg["indices_pauta"][nome_indice]["penalidade_saturacao_politica"]
        valor -= diretos["saturacao_politica"].valor * penalidade

    valor = round(max(0.0, min(100.0, valor)), 1)
    return ResultadoIndicePauta(nome_indice, valor, cobertura_pct, _classificar(valor, cfg["limites_classificacao"]))


def calcular_indices_pauta(proposta: PropostaPauta) -> ResultadoIndicesPauta:
    """Calcula os 20 indices de uma PropostaPauta. Nunca falha por dado
    faltante - redistribui peso e reporta cobertura_pct por indice."""
    cfg = policy_weights_config()
    campos = proposta.campos_numericos()

    diretos: dict[str, ResultadoIndicePauta] = {}
    for nome in _INDICES_DIRETOS:
        diretos[nome] = _indice_direto(nome, campos, cfg)

    resultado_final = dict(diretos)
    resultado_final["indice_geral_prioridade"] = _indice_geral_prioridade(diretos, cfg)

    cobertura_geral = round(
        sum(r.cobertura_pct for r in resultado_final.values()) / len(resultado_final), 1
    )
    return ResultadoIndicesPauta(indices=resultado_final, cobertura_geral_pct=cobertura_geral)
