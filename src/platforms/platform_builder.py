"""Monta o bloco de plataforma de uma pauta (secao 14.5 do briefing de
expansao SIET) a partir de uma PropostaPauta ja respondida, seus indices
(src/indicators/policy_indices.py) e sua classificacao de prioridade
(src/profiles/policy_classification.py).

GATE DE COMPETENCIA (secao 14.5: "Nenhuma proposta devera ser incluida
sem verificar a competencia do cargo analisado") - implementado aqui,
nao em cada chamador: `montar_plataforma()` sempre calcula
`GateCompetencia` primeiro; quando o cargo nao tem competencia real sobre
a pauta (nivel de governo do cargo fora de
config/policy_areas.yaml:pautas.<id>.niveis_competencia), a plataforma
ainda e retornada, mas com `gate.aprovado=False` e um aviso explicito no
lugar do "orgao responsavel" - a decisao de bloquear ou nao a exibicao
fica com quem chama (mesmo padrao de DataIssue em src/data_validation.py:
o sistema nao trava, mas nunca esconde o problema).

Campos que exigiriam elaboracao qualitativa nao coletada no questionario
(causas, consequencias, objetivos especificos, etapas) sao marcados
explicitamente como pendentes - NUNCA gerados por inferencia sobre um
problema real que este sistema nao conhece (ver ETAPA1_ARQUITETURA.md
secao 4 e o mesmo principio ja aplicado ao Modulo Candidato)."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..indicators.policy_indices import ResultadoIndicesPauta
from ..profiles.policy_classification import ResultadoClassificacaoPauta
from ..questionnaire.policy_questionnaire import PropostaPauta, SimNao, policy_areas_config

# Nivel de governo real de cada cargo (secao 5 do briefing - escopo
# eleitoral). "Deputado Distrital" e "distrital" porque o DF acumula
# competencias municipais e estaduais (Art. 32, CF/88) - ver nota em
# config/policy_areas.yaml.
CARGO_NIVEL_GOVERNO = {
    "Vereador": "municipal",
    "Prefeito": "municipal",
    "Deputado Estadual": "estadual",
    "Deputado Distrital": "distrital",
    "Deputado Federal": "federal",
    "Senador": "federal",
    "Governador": "estadual",
    "Presidente": "federal",
}

_PENDENTE = "Nao coletado no questionario - requer elaboracao qualitativa adicional (nao gerado automaticamente para evitar conteudo fabricado sobre um problema real que o sistema nao conhece)."


@dataclass
class GateCompetencia:
    aprovado: bool
    nivel_governo_cargo: str | None
    niveis_competencia_pauta: list[str]
    motivo: str


@dataclass
class PlataformaGerada:
    pauta_id: str
    cargo_analisado: str
    gate: GateCompetencia

    diagnostico: str
    problema_central: str
    causas: str
    consequencias: str
    objetivo_geral: str
    objetivos_especificos: str
    proposta_principal: str
    propostas_complementares: list[str]
    publico_beneficiado: str
    territorio: str
    orgao_responsavel: str
    parceiros: str
    custo_estimado: str
    fonte_recursos: str
    prazo: str
    etapas: str
    metas: str
    indicadores: str
    riscos: str
    forma_monitoramento: str
    competencia_do_cargo: str
    justificativa_tecnica: str
    resumo_comunicacao_publica: str

    prioridade: str | None = None
    tambem_aplicavel: list[str] = field(default_factory=list)


def verificar_gate_competencia(pauta_id: str, cargo_analisado: str) -> GateCompetencia:
    """Verifica se o cargo analisado tem competencia federativa real sobre
    a pauta, segundo config/policy_areas.yaml. Ver nota metodologica no
    fim daquele arquivo: para a maioria das ~35 pautas (competencia comum,
    Art. 23 CF/88), isto aprova quase todas as combinacoes - o valor real
    do gate esta em nunca deixar isso silencioso, e em alimentar o orgao
    responsavel certo (ver `_orgao_responsavel`)."""
    area = policy_areas_config()["pautas"].get(pauta_id)
    if area is None:
        return GateCompetencia(
            aprovado=False, nivel_governo_cargo=None, niveis_competencia_pauta=[],
            motivo=f"pauta_id '{pauta_id}' nao existe em config/policy_areas.yaml.",
        )

    nivel_cargo = CARGO_NIVEL_GOVERNO.get(cargo_analisado)
    niveis_pauta = list(area["niveis_competencia"])

    if nivel_cargo is None:
        return GateCompetencia(
            aprovado=False, nivel_governo_cargo=None, niveis_competencia_pauta=niveis_pauta,
            motivo=f"Cargo '{cargo_analisado}' nao reconhecido (ver CARGO_NIVEL_GOVERNO).",
        )

    if nivel_cargo not in niveis_pauta:
        return GateCompetencia(
            aprovado=False, nivel_governo_cargo=nivel_cargo, niveis_competencia_pauta=niveis_pauta,
            motivo=(
                f"'{cargo_analisado}' atua no nivel '{nivel_cargo}', que nao consta entre os "
                f"niveis de competencia real desta pauta ({', '.join(niveis_pauta)}). Base legal: "
                f"{area.get('base_legal', 'nao documentada')}."
            ),
        )

    return GateCompetencia(
        aprovado=True, nivel_governo_cargo=nivel_cargo, niveis_competencia_pauta=niveis_pauta,
        motivo=f"'{cargo_analisado}' (nivel '{nivel_cargo}') tem competencia real documentada sobre esta pauta.",
    )


def _orgao_responsavel(pauta_id: str, nivel_cargo: str | None) -> str:
    if nivel_cargo is None:
        return "Nao aplicavel - cargo sem nivel de governo reconhecido."
    area = policy_areas_config()["pautas"][pauta_id]
    orgao = area["orgaos_por_nivel"].get(nivel_cargo, "Nao documentado para este nivel.")
    return orgao


def _texto_binario(resposta: SimNao | None, se_sim: str, se_nao: str) -> str:
    if resposta is None:
        return "Nao respondido no questionario."
    return se_sim if resposta == SimNao.SIM else se_nao


def montar_plataforma(
    proposta: PropostaPauta,
    indices: ResultadoIndicesPauta,
    classificacao: ResultadoClassificacaoPauta,
) -> PlataformaGerada:
    """Monta o bloco de plataforma completo (secao 14.5). Sempre roda o
    gate de competencia primeiro - ver docstring do modulo."""
    gate = verificar_gate_competencia(proposta.pauta_id, proposta.cargo_analisado)
    area = policy_areas_config()["pautas"].get(proposta.pauta_id, {})

    orgao = (
        _orgao_responsavel(proposta.pauta_id, gate.nivel_governo_cargo)
        if gate.aprovado
        else f"NAO GERADO - gate de competencia reprovado: {gate.motivo}"
    )

    custo_estimado = _texto_binario(
        proposta.existe_estimativa_custo,
        "Estimativa de custo informada como existente no questionario - valor especifico nao coletado nesta etapa.",
        "Sem estimativa de custo declarada - pendente antes de comunicar a proposta publicamente.",
    )
    fonte_recursos = _texto_binario(
        proposta.existe_fonte_financiamento,
        "Fonte de financiamento informada como existente no questionario - detalhamento nao coletado nesta etapa.",
        "Sem fonte de financiamento declarada - risco fiscal real ate ser definida.",
    )
    prazo = _texto_binario(
        proposta.existe_prazo_definido,
        "Prazo informado como definido no questionario - cronograma detalhado nao coletado nesta etapa.",
        "Sem prazo definido.",
    )
    indicadores = _texto_binario(
        proposta.existe_indicador_resultado,
        "Indicador de resultado informado como existente - detalhamento nao coletado nesta etapa.",
        "Sem indicador de resultado definido - indice de Mensurabilidade reflete essa lacuna.",
    )
    metas = _texto_binario(
        proposta.existe_meta_definida,
        "Meta informada como definida no questionario - valor numerico nao coletado nesta etapa.",
        "Sem meta definida.",
    )
    parceiros = _texto_binario(
        proposta.exige_parceria,
        "Proposta declarada como dependente de parceria (privada, terceiro setor ou outro ente) - identificar parceiro concreto e proximo passo.",
        "Sem dependencia de parceria declarada.",
    )

    r_geral = indices["indice_geral_prioridade"]
    riscos = (
        f"Viabilidade juridica: nivel {indices['viabilidade_juridica'].classificacao} "
        f"(nota {indices['viabilidade_juridica'].valor}/100, nota alta = melhor). "
        f"Viabilidade fiscal: nivel {indices['viabilidade_fiscal'].classificacao} "
        f"(nota {indices['viabilidade_fiscal'].valor}/100, nota alta = melhor). "
        f"Risco de rejeicao publica: nivel {indices['risco_de_rejeicao'].classificacao} "
        f"(nota {indices['risco_de_rejeicao'].valor}/100, nota alta = pior). "
        f"Todos autoavaliacao do questionario - ver aviso metodologico."
    )

    competencia_do_cargo = (
        f"APROVADO - {gate.motivo}" if gate.aprovado else f"REPROVADO - {gate.motivo}"
    )

    justificativa_tecnica = (
        f"Base legal da pauta: {area.get('base_legal', 'nao documentada')}. "
        f"Indice Geral de Prioridade: {r_geral.valor}/100 ({r_geral.classificacao}, "
        f"cobertura {r_geral.cobertura_pct}% das respostas do questionario)."
    )

    resumo_comunicacao_publica = (
        proposta.proposta_principal
        if proposta.proposta_principal
        else "Proposta principal nao preenchida no questionario - obrigatoria antes de comunicar publicamente."
    )

    return PlataformaGerada(
        pauta_id=proposta.pauta_id,
        cargo_analisado=proposta.cargo_analisado,
        gate=gate,
        diagnostico=proposta.problema_central or _PENDENTE,
        problema_central=proposta.problema_central or _PENDENTE,
        causas=_PENDENTE,
        consequencias=_PENDENTE,
        objetivo_geral=proposta.proposta_principal or _PENDENTE,
        objetivos_especificos=_PENDENTE,
        proposta_principal=proposta.proposta_principal or _PENDENTE,
        propostas_complementares=list(proposta.propostas_complementares),
        publico_beneficiado=proposta.publico_afetado or _PENDENTE,
        territorio=proposta.territorio_afetado or _PENDENTE,
        orgao_responsavel=orgao,
        parceiros=parceiros,
        custo_estimado=custo_estimado,
        fonte_recursos=fonte_recursos,
        prazo=prazo,
        etapas=_PENDENTE,
        metas=metas,
        indicadores=indicadores,
        riscos=riscos,
        forma_monitoramento=indicadores,
        competencia_do_cargo=competencia_do_cargo,
        justificativa_tecnica=justificativa_tecnica,
        resumo_comunicacao_publica=resumo_comunicacao_publica,
        prioridade=classificacao.classificacao_principal,
        tambem_aplicavel=list(classificacao.tambem_aplicavel),
    )
