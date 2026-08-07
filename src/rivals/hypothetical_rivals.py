"""Rivais hipoteticos de uma candidatura do Modulo Candidato (secao 17 do
briefing de expansao SIET).

PREMISSA METODOLOGICA (declarada em todo resultado, nunca escondida): como
o candidato do Modulo Candidato ainda nao disputou o cargo pretendido, nao
existe "disputa dele" para analisar. Em vez de inventar concorrentes, este
modulo busca a DISPUTA REAL COMPARAVEL MAIS RECENTE (mesmo cargo, mesma
UF/municipio) atraves do proprio motor ja existente do SIET
(`src/candidate_finder.py:buscar_candidatos_disputa`, o mesmo usado para
candidaturas reais em todo o resto do sistema) e trata quem disputou por
ultimo como o melhor proxy real disponivel de quem provavelmente disputara
de novo. E uma premissa, nao um fato - fica sempre explicita."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..candidate_finder import Candidatura, buscar_candidatos_disputa, listar_municipios_uf
from ..questionnaire.candidate_questionnaire import IdentificacaoAnalise
from ..utils import get_logger, load_yaml

logger = get_logger(__name__)

# Rotulo do Modulo Candidato (app.py:_CARGOS_MODO1) -> string real do TSE
# (src/rules/electoral_scope.py) - mesma tabela de cargos, nomenclatura
# diferente por historico (Modulo Candidato usa Title Case na UI).
CARGO_LABEL_PARA_TSE = {
    "Vereador": "VEREADOR",
    "Prefeito": "PREFEITO",
    "Deputado Estadual": "DEPUTADO ESTADUAL",
    "Deputado Distrital": "DEPUTADO DISTRITAL",
    "Deputado Federal": "DEPUTADO FEDERAL",
    "Senador": "SENADOR",
    "Governador": "GOVERNADOR",
    "Presidente": "PRESIDENTE",
}

# Ano real mais recente com dado de votacao disponivel no SIET para cada
# cargo (src/rules/electoral_scope.py:_CARGOS_POR_ANO - municipal=2024,
# estadual/federal=2022).
CARGO_ANO_COMPARAVEL = {
    "VEREADOR": 2024,
    "PREFEITO": 2024,
    "DEPUTADO ESTADUAL": 2022,
    "DEPUTADO DISTRITAL": 2022,
    "DEPUTADO FEDERAL": 2022,
    "SENADOR": 2022,
    "GOVERNADOR": 2022,
    "PRESIDENTE": 2022,
}

CARGOS_MUNICIPAIS = {"VEREADOR", "PREFEITO"}


def rivals_weights_config() -> dict:
    return load_yaml("config/rivals_weights.yaml")


@dataclass
class DisputaComparavel:
    ano: int
    cargo_tse: str
    uf: str
    municipio_codigo: int | None
    municipio_nome: str | None
    candidatos: list[Candidatura] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def resolver_municipio(ano: int, uf: str, municipio_base: str) -> tuple[int | None, str | None, str | None]:
    """Resolve o nome de municipio digitado no questionario para o codigo
    TSE real, por comparacao exata (case-insensitive, sem espacos nas
    pontas) contra a lista real de municipios com candidatura naquele ano/
    UF. NUNCA usa correspondencia aproximada/fuzzy - se nao achar exato,
    retorna None com um aviso claro em vez de arriscar o municipio errado."""
    municipios = listar_municipios_uf(ano, uf)
    if municipios.empty:
        return None, None, f"Nenhum municipio com candidatura encontrado para {uf}/{ano}."

    alvo = municipio_base.strip().upper()
    correspondencia = municipios[municipios["municipio"].str.strip().str.upper() == alvo]
    if correspondencia.empty:
        return None, None, (
            f"Municipio '{municipio_base}' nao encontrado exatamente entre os municipios "
            f"de {uf}/{ano} no TSE - confira a grafia (sem abreviacoes). Rivais nao podem "
            f"ser identificados sem o municipio correto."
        )

    linha = correspondencia.iloc[0]
    codigo = int(linha["codigo_municipio_tse"]) if pd.notna(linha["codigo_municipio_tse"]) else None
    return codigo, str(linha["municipio"]), None


def resolver_disputa_comparavel_cargo(cargo_pretendido_label: str, uf: str, municipio_base: str) -> DisputaComparavel:
    """Encontra a disputa real comparavel mais recente para um cargo/UF/
    municipio quaisquer. Nucleo compartilhado por rivais (este modulo) e
    por compatibilidade partidaria (`src/parties/party_compatibility.py`) -
    a mesma disputa real serve de base para os dois."""
    cargo_tse = CARGO_LABEL_PARA_TSE.get(cargo_pretendido_label)
    if cargo_tse is None:
        return DisputaComparavel(
            ano=0, cargo_tse="", uf=uf, municipio_codigo=None, municipio_nome=None,
            avisos=[f"Cargo '{cargo_pretendido_label}' nao reconhecido (ver CARGO_LABEL_PARA_TSE)."],
        )

    ano = CARGO_ANO_COMPARAVEL[cargo_tse]
    avisos: list[str] = []
    municipio_codigo = None
    municipio_nome = None

    if cargo_tse in CARGOS_MUNICIPAIS:
        municipio_codigo, municipio_nome, aviso_municipio = resolver_municipio(ano, uf, municipio_base)
        if aviso_municipio:
            avisos.append(aviso_municipio)
            return DisputaComparavel(ano, cargo_tse, uf, None, None, avisos=avisos)

    try:
        candidatos = buscar_candidatos_disputa(ano, cargo_tse, uf, municipio_codigo=municipio_codigo)
    except Exception as exc:  # dado indisponivel para essa UF/ano especifico - nao deve derrubar a analise
        avisos.append(f"Nao foi possivel carregar a disputa comparavel real ({ano}/{cargo_tse}/{uf}): {exc}")
        candidatos = []

    if not candidatos:
        avisos.append(
            f"Nenhum candidato real encontrado na disputa comparavel ({ano}/{cargo_tse}/{uf}"
            f"{'/' + municipio_nome if municipio_nome else ''}) - analise nao pode prosseguir."
        )

    return DisputaComparavel(ano, cargo_tse, uf, municipio_codigo, municipio_nome, candidatos, avisos)


def resolver_disputa_comparavel(identificacao: IdentificacaoAnalise) -> DisputaComparavel:
    """Atalho de `resolver_disputa_comparavel_cargo` a partir dos campos do
    questionario do Modulo Candidato."""
    return resolver_disputa_comparavel_cargo(identificacao.cargo_pretendido, identificacao.uf, identificacao.municipio_base)


@dataclass
class RivalProjetado:
    candidatura: Candidatura
    colocacao: int
    indice_rivalidade: float
    classificacao: str
    tipos: list[str] = field(default_factory=list)  # rival_partidario / rival_dominante / rival_direto / rival_baixa_ameaca


@dataclass
class ResultadoRivaisProjetados:
    disputa: DisputaComparavel
    rivais: list[RivalProjetado] = field(default_factory=list)


def _classificar(valor: float, limites: dict[str, int]) -> str:
    ordenado = sorted(limites.items(), key=lambda kv: kv[1], reverse=True)
    for nome, minimo in ordenado:
        if valor >= minimo:
            return nome
    return ordenado[-1][0]


def identificar_rivais_projetados(
    identificacao: IdentificacaoAnalise, top_n: int = 10
) -> ResultadoRivaisProjetados:
    """Identifica ate `top_n` rivais projetados a partir da disputa
    comparavel real mais recente, com Indice de Rivalidade Eleitoral
    (config/rivals_weights.yaml) calculado sobre dado real (votos,
    resultado, partido) - nunca autoavaliacao."""
    disputa = resolver_disputa_comparavel(identificacao)
    if not disputa.candidatos:
        return ResultadoRivaisProjetados(disputa=disputa, rivais=[])

    cfg = rivals_weights_config()
    pesos = cfg["indice_rivalidade"]["pesos"]
    limites = cfg["limites_classificacao"]

    ordenados = sorted(disputa.candidatos, key=lambda c: c.total_votos, reverse=True)
    votos_lider = ordenados[0].total_votos if ordenados else 0
    partido_candidato = identificacao.partido_sigla.strip().upper() if identificacao.partido_sigla else None

    rivais: list[RivalProjetado] = []
    for i, cand in enumerate(ordenados[:top_n]):
        forca_eleitoral = round(min(100.0, 100.0 * cand.total_votos / votos_lider), 1) if votos_lider else 0.0
        foi_eleito = 100.0 if cand.resultado_final.upper().startswith("ELEITO") else 0.0
        mesmo_partido = 100.0 if (partido_candidato and cand.partido_sigla.strip().upper() == partido_candidato) else 0.0

        indice = round(
            forca_eleitoral * pesos["forca_eleitoral"]
            + foi_eleito * pesos["foi_eleito"]
            + mesmo_partido * pesos["mesmo_partido_candidato"],
            1,
        )
        classificacao = _classificar(indice, limites)

        tipos = ["rival_direto"]
        if mesmo_partido:
            tipos.append("rival_partidario")
        if foi_eleito and i < max(1, top_n // 3):
            tipos.append("rival_dominante")
        if indice < limites["baixo"]:
            tipos = ["rival_baixa_ameaca"]

        rivais.append(RivalProjetado(
            candidatura=cand, colocacao=i + 1, indice_rivalidade=indice, classificacao=classificacao, tipos=tipos,
        ))

    return ResultadoRivaisProjetados(disputa=disputa, rivais=rivais)
