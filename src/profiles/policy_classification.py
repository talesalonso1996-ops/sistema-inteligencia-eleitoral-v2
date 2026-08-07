"""Matriz de priorizacao de pautas (secao 14.4 do briefing de expansao
SIET). Mesmo motor de regras de candidate_archetype.py: condicao booleana
por classificacao, declarada em config/policy_weights.yaml:matriz_priorizacao,
avaliada com `eval` restrito sobre os 20 indices ja calculados."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..indicators.policy_indices import ResultadoIndicesPauta
from ..questionnaire.policy_questionnaire import policy_weights_config


@dataclass
class ResultadoClassificacaoPauta:
    classificacao_principal: str | None
    tambem_aplicavel: list[str] = field(default_factory=list)
    evidencias: dict[str, str] = field(default_factory=dict)


def _avaliar_condicao(condicao: str, valores: dict[str, float]) -> bool:
    try:
        return bool(eval(condicao, {"__builtins__": {}}, dict(valores)))  # noqa: S307 - namespace restrito, config interna
    except Exception:
        return False


def classificar_pauta(resultado_indices: ResultadoIndicesPauta) -> ResultadoClassificacaoPauta:
    """Classifica a pauta na matriz de priorizacao (secao 14.4). A
    'principal' e a primeira regra satisfeita na ordem declarada em
    config/policy_weights.yaml:matriz_priorizacao (risco vem antes de
    prioridade, de proposito - ver comentario no YAML); as demais regras
    satisfeitas entram em `tambem_aplicavel`."""
    cfg = policy_weights_config()["matriz_priorizacao"]
    valores = resultado_indices.valores()

    satisfeitas: list[str] = []
    evidencias: dict[str, str] = {}
    for nome_classificacao, regra in cfg.items():
        condicao = regra["condicao"]
        if _avaliar_condicao(condicao, valores):
            satisfeitas.append(nome_classificacao)
            evidencias[nome_classificacao] = condicao

    if not satisfeitas:
        return ResultadoClassificacaoPauta(classificacao_principal=None)

    return ResultadoClassificacaoPauta(
        classificacao_principal=satisfeitas[0],
        tambem_aplicavel=satisfeitas[1:],
        evidencias=evidencias,
    )
