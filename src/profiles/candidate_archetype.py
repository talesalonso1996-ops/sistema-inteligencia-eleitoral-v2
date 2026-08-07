"""Arquetipos politico-eleitorais (secao 12 do briefing de expansao SIET).

Cada arquetipo e definido em config/weights.yaml:arquetipos como uma
condicao booleana sobre os 20 indices ja calculados por
src/indicators/candidate_indices.py - nenhum arquetipo pede pergunta nova
ou dado adicional. As condicoes sao avaliadas com um `eval` restrito
(sem builtins, unico namespace = os valores dos indices) porque o arquivo
de config e mantido pelo proprio time do projeto, nao por entrada externa
- mesmo assim, o eval e propositalmente sandboxed."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..indicators.candidate_indices import ResultadoIndicesCandidato, weights_config


@dataclass
class ResultadoArquetipo:
    arquetipo_principal: str | None
    arquetipos_secundarios: list[str] = field(default_factory=list)
    evidencias: dict[str, str] = field(default_factory=dict)  # arquetipo -> condicao satisfeita
    cargos_compativeis: list[str] = field(default_factory=list)


def _avaliar_condicao(condicao: str, valores: dict[str, float]) -> bool:
    """Avalia uma condicao como 'capilaridade_territorial >= 60 and
    mobilizacao >= 60' usando somente os valores dos indices como
    variaveis disponiveis - sem builtins, sem acesso a qualquer outra
    funcao ou objeto do processo."""
    try:
        return bool(eval(condicao, {"__builtins__": {}}, dict(valores)))  # noqa: S307 - namespace restrito, config interna
    except Exception:  # config malformada nao deve derrubar a analise
        return False


def classificar_arquetipo(resultado_indices: ResultadoIndicesCandidato) -> ResultadoArquetipo:
    """Classifica o candidato em um ou mais arquetipos com base nos indices
    ja calculados. O 'principal' e o primeiro arquetipo satisfeito na
    ordem declarada em config/weights.yaml (ordem = prioridade normativa,
    do mais especifico/forte ao mais generico); os demais satisfeitos
    entram como secundarios."""
    cfg = weights_config()["arquetipos"]
    valores = resultado_indices.valores()

    satisfeitos: list[str] = []
    evidencias: dict[str, str] = {}
    for nome_arquetipo, regra in cfg.items():
        condicao = regra["condicao"]
        if _avaliar_condicao(condicao, valores):
            satisfeitos.append(nome_arquetipo)
            evidencias[nome_arquetipo] = condicao

    if not satisfeitos:
        return ResultadoArquetipo(arquetipo_principal=None, cargos_compativeis=[])

    principal = satisfeitos[0]
    secundarios = satisfeitos[1:]
    cargos = list(cfg[principal].get("cargos_compativeis", []))

    return ResultadoArquetipo(
        arquetipo_principal=principal,
        arquetipos_secundarios=secundarios,
        evidencias=evidencias,
        cargos_compativeis=cargos,
    )
