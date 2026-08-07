"""Matriz Candidato x Territorio x Pauta (Modo 4 - Integracao, secao 15 do
briefing de expansao SIET).

Cruza a saida JA CALCULADA dos tres modulos anteriores - nunca recalcula um
indice a partir de resposta bruta, so combina resultados ja validados:
- Modo 1 (Candidato): `src/indicators/candidate_indices.py`
- Modo 3 (Pauta): `src/indicators/policy_indices.py` + `src/platforms/platform_builder.py`
- Territorio: perfil REAL do municipio informado no questionario do Modo 1.

NOTA METODOLOGICA (achado real desta etapa, nao uma limitacao escondida):
o perfil demografico por TERRITORIO FINO (bairro/zona) usado no resto do
SIET e ponderado pelos VOTOS REAIS de uma candidatura ja disputada
(`src/demographic_analysis.py:perfil_demografico_do_territorio`, peso =
`votos_candidato`) - isso nao existe para uma candidatura hipotetica do
Modo 1 (ainda sem nenhum voto). Por isso o perfil territorial aqui e no
nivel de MUNICIPIO INTEIRO, ponderado por POPULACAO REAL do setor
censitario (Censo IBGE 2022) em vez de voto - mais grosso que o resto do
sistema, mas real, e as mesmas variaveis com o mesmo rationale de
literatura ja documentado em `config/indicators.yaml:piramide_maslow`
(reaproveitadas, nao um mapeamento novo inventado).

O cruzamento Candidato x Pauta vira um indice numerico unico
(`config/integration_weights.yaml`) porque os tres componentes sao da
MESMA familia metodologica (autoavaliacao estruturada, ja 0-100). O
cruzamento Territorio x Pauta deliberadamente NAO vira um escore -
misturar dado real (Censo/RAIS-CAGED) com autoavaliacao (Candidato/Pauta)
num unico numero fabricaria uma equivalencia que os dados nao sustentam;
o modulo mostra o perfil territorial real ao lado de cada pauta e deixa a
leitura de relevancia para quem usa o sistema."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..demographic_analysis import perfil_demografico_por_setor
from ..economic_analysis import PerfilEconomicoMunicipio, carregar_perfil_economico_por_municipio
from ..geographic_analysis import carregar_malha
from ..indicators.candidate_indices import ResultadoIndicesCandidato
from ..indicators.policy_indices import ResultadoIndicesPauta
from ..platforms.platform_builder import GateCompetencia
from ..questionnaire.candidate_questionnaire import IdentificacaoAnalise
from ..questionnaire.policy_questionnaire import PropostaPauta
from ..rivals.hypothetical_rivals import resolver_municipio
from ..utils import get_logger, indicators_config, load_yaml

logger = get_logger(__name__)

# Ano de referencia so para resolver nome->codigo de municipio (nao muda de
# um ano eleitoral para outro) - mesma funcao generica ja usada por
# src/rivals/hypothetical_rivals.py, sem duplicar logica de resolucao.
_ANO_REFERENCIA_MUNICIPIO = 2024


def integration_weights_config() -> dict:
    return load_yaml("config/integration_weights.yaml")


def _classificar(valor: float, limites: dict[str, int]) -> str:
    ordenado = sorted(limites.items(), key=lambda kv: kv[1], reverse=True)
    for nome, minimo in ordenado:
        if valor >= minimo:
            return nome
    return ordenado[-1][0]


@dataclass
class PerfilTerritorialMunicipio:
    uf: str
    municipio: str
    codigo_municipio_tse: int | None
    n_setores_censitarios: int
    indicadores_piramide_maslow: dict[str, float | None] = field(default_factory=dict)
    perfil_economico: PerfilEconomicoMunicipio | None = None
    avisos: list[str] = field(default_factory=list)


def _variaveis_piramide_maslow() -> list[str]:
    """Reaproveita as MESMAS variaveis (e o MESMO rationale de literatura,
    ja documentado) de config/indicators.yaml:piramide_maslow - nao inventa
    um mapeamento pauta->variavel novo para esta etapa."""
    cfg = indicators_config()["piramide_maslow"]
    nomes: set[str] = set()
    for tier in cfg["tiers"].values():
        for var in tier.get("variaveis", []):
            nomes.add(var["nome"])
    return sorted(nomes)


def _media_ponderada_por_populacao(perfil_setores: pd.DataFrame, variavel: str) -> float | None:
    if variavel not in perfil_setores.columns or "populacao_total" not in perfil_setores.columns:
        return None
    validos = perfil_setores[
        perfil_setores[variavel].notna()
        & perfil_setores["populacao_total"].notna()
        & (perfil_setores["populacao_total"] > 0)
    ]
    if validos.empty:
        return None
    return round(float((validos[variavel] * validos["populacao_total"]).sum() / validos["populacao_total"].sum()), 2)


def perfil_territorial_municipio(uf: str, municipio_base: str) -> PerfilTerritorialMunicipio:
    """Perfil territorial REAL (Censo IBGE 2022 + RAIS/CAGED) do municipio
    informado no questionario do Modo 1 - independente de qualquer
    candidatura ja disputada (ver nota metodologica do modulo). Nunca
    lanca excecao por dado ausente - reporta avisos, mesmo padrao do resto
    do SIET."""
    codigo_municipio_tse, municipio_real, aviso_municipio = resolver_municipio(
        _ANO_REFERENCIA_MUNICIPIO, uf, municipio_base
    )
    if aviso_municipio:
        return PerfilTerritorialMunicipio(
            uf=uf, municipio=municipio_base, codigo_municipio_tse=None, n_setores_censitarios=0,
            avisos=[aviso_municipio],
        )

    avisos: list[str] = []
    setores_gdf = carregar_malha("setores", municipio_real, uf)
    if setores_gdf is None or setores_gdf.empty or "CD_SETOR" not in setores_gdf.columns:
        avisos.append(
            f"Malha de setores censitarios indisponivel para {municipio_real}/{uf} - "
            f"perfil demografico do municipio nao pode ser calculado."
        )
        indicadores: dict[str, float | None] = {}
        n_setores = 0
    else:
        setores_ids = {str(s) for s in setores_gdf["CD_SETOR"].dropna().unique()}
        perfil_setores = perfil_demografico_por_setor(setores_ids)
        n_setores = len(perfil_setores)
        indicadores = {var: _media_ponderada_por_populacao(perfil_setores, var) for var in _variaveis_piramide_maslow()}

    perfil_economico = carregar_perfil_economico_por_municipio(municipio_real, uf, chave_cache=codigo_municipio_tse)
    if not perfil_economico.disponivel:
        avisos.append(f"Perfil economico (RAIS/CAGED) indisponivel para {municipio_real}/{uf}.")

    return PerfilTerritorialMunicipio(
        uf=uf, municipio=municipio_real, codigo_municipio_tse=codigo_municipio_tse,
        n_setores_censitarios=n_setores, indicadores_piramide_maslow=indicadores,
        perfil_economico=perfil_economico, avisos=avisos,
    )


@dataclass
class CompatibilidadeCandidatoPauta:
    pauta_id: str
    cargo_analisado: str
    elegivel_pelo_cargo: bool
    motivo_elegibilidade: str
    autoridade_tematica_candidato: float | None
    aderencia_candidato_pauta: float | None
    indice_geral_prioridade_pauta: float
    indice_compatibilidade: float
    classificacao: str
    cobertura_pct: float
    mesmo_territorio_declarado: bool | None  # None = um dos dois campos livres nao foi preenchido


def compatibilidade_candidato_pauta(
    identificacao: IdentificacaoAnalise,
    indices_candidato: ResultadoIndicesCandidato,
    proposta: PropostaPauta,
    indices_pauta: ResultadoIndicesPauta,
    gate: GateCompetencia,
) -> CompatibilidadeCandidatoPauta:
    """Cruza um indice ja calculado do Modo 1 (Autoridade Tematica) com dois
    ja calculados do Modo 3 (aderencia autoavaliada + indice geral de
    prioridade), pesos em config/integration_weights.yaml. Zerado quando o
    gate de competencia (Seção 14.5) reprova o cargo para esta pauta -
    nenhuma pauta fora da competencia real do cargo recebe compatibilidade
    positiva, mesmo com boa autoavaliacao."""
    cfg = integration_weights_config()
    pesos_originais = dict(cfg["indice_compatibilidade_candidato_pauta"]["pesos"])

    autoridade = indices_candidato["autoridade_tematica"].valor if "autoridade_tematica" in indices_candidato.indices else None
    aderencia = proposta.campos_numericos().get("aderencia_candidato")
    prioridade = indices_pauta["indice_geral_prioridade"].valor

    componentes = {
        "autoridade_tematica_candidato": autoridade,
        "aderencia_candidato_pauta": aderencia,
        "indice_geral_prioridade_pauta": prioridade,
    }
    pesos_disponiveis = {k: v for k, v in pesos_originais.items() if componentes.get(k) is not None}
    for k in pesos_originais:
        if componentes.get(k) is None:
            logger.warning("Compatibilidade candidato-pauta '%s': componente '%s' indisponivel.", proposta.pauta_id, k)

    soma_pesos = sum(pesos_disponiveis.values())
    cobertura_pct = round(100.0 * soma_pesos / sum(pesos_originais.values()), 1) if pesos_originais else 0.0

    if not gate.aprovado or soma_pesos == 0:
        indice = 0.0
    else:
        indice = sum(componentes[k] * (peso / soma_pesos) for k, peso in pesos_disponiveis.items())
    indice = round(max(0.0, min(100.0, indice)), 1)

    territorio_candidato = (identificacao.municipio_base or "").strip().upper()
    territorio_pauta = (proposta.territorio_afetado or "").strip().upper()
    mesmo_territorio = None
    if territorio_candidato and territorio_pauta:
        mesmo_territorio = territorio_candidato in territorio_pauta or territorio_pauta in territorio_candidato

    return CompatibilidadeCandidatoPauta(
        pauta_id=proposta.pauta_id,
        cargo_analisado=proposta.cargo_analisado,
        elegivel_pelo_cargo=gate.aprovado,
        motivo_elegibilidade=gate.motivo,
        autoridade_tematica_candidato=autoridade,
        aderencia_candidato_pauta=aderencia,
        indice_geral_prioridade_pauta=prioridade,
        indice_compatibilidade=indice,
        classificacao=_classificar(indice, cfg["limites_classificacao"]),
        cobertura_pct=cobertura_pct,
        mesmo_territorio_declarado=mesmo_territorio,
    )


@dataclass
class ResultadoMatrizIntegrada:
    perfil_territorial: PerfilTerritorialMunicipio
    compatibilidades: list[CompatibilidadeCandidatoPauta] = field(default_factory=list)


def montar_matriz_candidato_territorio_pauta(
    identificacao: IdentificacaoAnalise,
    indices_candidato: ResultadoIndicesCandidato,
    pautas: list[tuple[PropostaPauta, ResultadoIndicesPauta, GateCompetencia]],
) -> ResultadoMatrizIntegrada:
    """Ponto de entrada do Modo 4: perfil territorial real do municipio do
    Modo 1 + compatibilidade candidato-pauta (ordenada da mais para a menos
    compativel) para cada pauta ja analisada no Modo 3."""
    perfil_territorial = perfil_territorial_municipio(identificacao.uf, identificacao.municipio_base)
    compatibilidades = [
        compatibilidade_candidato_pauta(identificacao, indices_candidato, proposta, indices_pauta, gate)
        for proposta, indices_pauta, gate in pautas
    ]
    compatibilidades.sort(key=lambda c: c.indice_compatibilidade, reverse=True)
    return ResultadoMatrizIntegrada(perfil_territorial=perfil_territorial, compatibilidades=compatibilidades)
