"""Regras centralizadas de abrangencia territorial por cargo/ano (V2).

Unica fonte de verdade sobre "qual e o universo eleitoral de uma
candidatura" - substitui condicionais de ano/cargo espalhadas pela
aplicacao (como existiam no V1, ver candidate_finder.py) por uma tabela
unica consultada via `resolver_escopo()`.

A estrutura constitucional dos cargos (`_CARGO_SCOPE_TABLE` abaixo) e
independente do ano - Prefeito sempre e municipal, Presidente sempre e
nacional, etc. O que varia por ano sao os valores BRUTOS do TSE
(DS_ELEICAO, TP_ABRANGENCIA) e os templates de URL/arquivo - esses vem de
`config/data_sources.yaml: eleicoes.<ano>`, nunca de literais no codigo.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..utils import data_sources


class EscopoInvalidoError(ValueError):
    """Levantado quando a combinacao ano/cargo/UF/municipio/turno pedida
    nao corresponde a uma disputa eleitoral valida (ex.: Deputado Distrital
    fora do DF, 2o turno para cargo proporcional, cargo inexistente no ano)."""


@dataclass(frozen=True)
class EscopoEleitoral:
    """Resultado da resolucao de escopo para uma disputa especifica -
    consumido por candidate_finder.py, pelos adaptadores e pela UI (para
    decidir quais campos sao obrigatorios e quais niveis territoriais
    mostrar)."""

    ano_eleicao: int
    cargo: str
    tipo_abrangencia: str  # "NACIONAL" | "ESTADUAL" | "DISTRITAL" | "MUNICIPAL"
    uf_obrigatoria: bool
    municipio_obrigatorio: bool
    uf_e_filtro_analitico: bool  # True so p/ Presidente: UF nunca reduz o total oficial nacional
    niveis_territoriais_disponiveis: tuple[str, ...]
    permite_segundo_turno: bool
    universo_eleitoral: str  # descricao textual do universo (para exibicao/relatorio)
    tipos_concorrentes_validos: tuple[str, ...]
    filtro_sql_ds_eleicao: str
    filtro_sql_tp_abrangencia: str | None


@dataclass(frozen=True)
class _RegraCargo:
    tipo_abrangencia: str
    uf_obrigatoria: bool
    municipio_obrigatorio: bool
    uf_e_filtro_analitico: bool
    niveis_territoriais_disponiveis: tuple[str, ...]
    permite_segundo_turno: bool
    universo_eleitoral: str
    tipos_concorrentes_validos: tuple[str, ...]
    exige_uf_especifica: str | None = None  # ex.: "DF" para deputado distrital


_NIVEIS_MUNICIPAIS = ("MUNICIPIO", "DISTRITO", "BAIRRO", "ZONA", "LOCAL_VOTACAO", "SECAO")
_NIVEIS_ESTADUAIS = ("UF", "REGIAO_DO_ESTADO", "MUNICIPIO", "ZONA", "LOCAL_VOTACAO", "SECAO")
_NIVEIS_NACIONAIS = ("BRASIL", "REGIAO", "UF", "MUNICIPIO", "ZONA", "LOCAL_VOTACAO", "SECAO")
_NIVEIS_DISTRITAIS = ("DF", "REGIAO_ADMINISTRATIVA", "ZONA", "LOCAL_VOTACAO", "SECAO")

_CARGO_SCOPE_TABLE: dict[str, _RegraCargo] = {
    "PREFEITO": _RegraCargo(
        tipo_abrangencia="MUNICIPAL",
        uf_obrigatoria=True,
        municipio_obrigatorio=True,
        uf_e_filtro_analitico=False,
        niveis_territoriais_disponiveis=_NIVEIS_MUNICIPAIS,
        permite_segundo_turno=True,
        universo_eleitoral="Eleitorado do municipio selecionado",
        tipos_concorrentes_validos=("mesmo_municipio_cargo_turno",),
    ),
    "VEREADOR": _RegraCargo(
        tipo_abrangencia="MUNICIPAL",
        uf_obrigatoria=True,
        municipio_obrigatorio=True,
        uf_e_filtro_analitico=False,
        niveis_territoriais_disponiveis=_NIVEIS_MUNICIPAIS,
        permite_segundo_turno=False,
        universo_eleitoral="Eleitorado do municipio selecionado",
        tipos_concorrentes_validos=(
            "mesmo_municipio", "mesmo_partido_federacao",
            "votacao_semelhante", "base_territorial_semelhante",
        ),
    ),
    "PRESIDENTE": _RegraCargo(
        tipo_abrangencia="NACIONAL",
        uf_obrigatoria=False,
        municipio_obrigatorio=False,
        uf_e_filtro_analitico=True,
        niveis_territoriais_disponiveis=_NIVEIS_NACIONAIS,
        permite_segundo_turno=True,
        universo_eleitoral="Eleitorado do Brasil inteiro (UF e apenas um recorte analitico)",
        tipos_concorrentes_validos=("mesma_disputa_nacional",),
    ),
    "GOVERNADOR": _RegraCargo(
        tipo_abrangencia="ESTADUAL",
        uf_obrigatoria=True,
        municipio_obrigatorio=False,
        uf_e_filtro_analitico=False,
        niveis_territoriais_disponiveis=_NIVEIS_ESTADUAIS,
        permite_segundo_turno=True,
        universo_eleitoral="Eleitorado de toda a UF selecionada",
        tipos_concorrentes_validos=("mesma_disputa_estadual",),
    ),
    "SENADOR": _RegraCargo(
        tipo_abrangencia="ESTADUAL",
        uf_obrigatoria=True,
        municipio_obrigatorio=False,
        uf_e_filtro_analitico=False,
        niveis_territoriais_disponiveis=_NIVEIS_ESTADUAIS,
        permite_segundo_turno=False,
        universo_eleitoral="Eleitorado de toda a UF selecionada",
        tipos_concorrentes_validos=("mesma_disputa_estadual",),
    ),
    "DEPUTADO FEDERAL": _RegraCargo(
        tipo_abrangencia="ESTADUAL",
        uf_obrigatoria=True,
        municipio_obrigatorio=False,
        uf_e_filtro_analitico=False,
        niveis_territoriais_disponiveis=_NIVEIS_ESTADUAIS,
        permite_segundo_turno=False,
        universo_eleitoral="Eleitorado de toda a UF selecionada (cargo proporcional - nao limitado ao municipio de origem/maior votacao do candidato)",
        tipos_concorrentes_validos=("mesma_disputa_estadual", "mesmo_partido_federacao"),
    ),
    "DEPUTADO ESTADUAL": _RegraCargo(
        tipo_abrangencia="ESTADUAL",
        uf_obrigatoria=True,
        municipio_obrigatorio=False,
        uf_e_filtro_analitico=False,
        niveis_territoriais_disponiveis=_NIVEIS_ESTADUAIS,
        permite_segundo_turno=False,
        universo_eleitoral="Eleitorado de toda a UF selecionada (todos os municipios, cargo proporcional)",
        tipos_concorrentes_validos=("mesma_disputa_estadual", "mesmo_partido_federacao"),
    ),
    "DEPUTADO DISTRITAL": _RegraCargo(
        tipo_abrangencia="DISTRITAL",
        uf_obrigatoria=True,
        municipio_obrigatorio=False,
        uf_e_filtro_analitico=False,
        niveis_territoriais_disponiveis=_NIVEIS_DISTRITAIS,
        permite_segundo_turno=False,
        universo_eleitoral="Eleitorado de todo o Distrito Federal",
        tipos_concorrentes_validos=("mesma_disputa_distrital", "mesmo_partido_federacao"),
        exige_uf_especifica="DF",
    ),
}

_CARGOS_POR_ANO: dict[int, tuple[str, ...]] = {
    2024: ("PREFEITO", "VEREADOR"),
    2022: (
        "PRESIDENTE", "GOVERNADOR", "SENADOR",
        "DEPUTADO FEDERAL", "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL",
    ),
}


@lru_cache(maxsize=None)
def _eleicao_cfg(ano: int) -> dict:
    eleicoes = data_sources().get("eleicoes", {})
    if ano not in eleicoes:
        raise EscopoInvalidoError(
            f"Ano eleitoral nao configurado em config/data_sources.yaml: eleicoes.{ano}"
        )
    return eleicoes[ano]


def cargos_disponiveis(ano: int, uf: str | None = None) -> list[str]:
    """Lista os cargos validos para o ano (e, se informada, a UF) - usada
    pela UI para popular o seletor de cargo dependente do ano/UF (ex.:
    Deputado Distrital so aparece quando uf='DF')."""
    disponiveis = []
    for cargo in _CARGOS_POR_ANO.get(ano, ()):
        regra = _CARGO_SCOPE_TABLE[cargo]
        if regra.exige_uf_especifica and uf and uf.upper() != regra.exige_uf_especifica:
            continue
        disponiveis.append(cargo)
    return disponiveis


def resolver_escopo(
    ano: int, cargo: str, uf: str | None = None, municipio: str | None = None, turno: int = 1,
) -> EscopoEleitoral:
    """Resolve a abrangencia territorial de uma disputa - unica funcao que
    o resto do sistema deve consultar para saber se uma candidatura e
    municipal/estadual/distrital/nacional, quais campos sao obrigatorios,
    quais niveis territoriais existem e se ha 2o turno."""
    cargo_norm = cargo.strip().upper()
    if ano not in _CARGOS_POR_ANO:
        raise EscopoInvalidoError(
            f"Ano eleitoral nao suportado: {ano}. Anos disponiveis: {sorted(_CARGOS_POR_ANO)}"
        )
    if cargo_norm not in _CARGO_SCOPE_TABLE:
        raise EscopoInvalidoError(f"Cargo desconhecido: {cargo!r}")
    if cargo_norm not in _CARGOS_POR_ANO[ano]:
        raise EscopoInvalidoError(f"Cargo {cargo_norm!r} nao existe na eleicao de {ano}")

    regra = _CARGO_SCOPE_TABLE[cargo_norm]

    if regra.exige_uf_especifica:
        if not uf:
            raise EscopoInvalidoError(f"{cargo_norm} exige uf='{regra.exige_uf_especifica}'")
        if uf.strip().upper() != regra.exige_uf_especifica:
            raise EscopoInvalidoError(
                f"{cargo_norm} so existe na UF {regra.exige_uf_especifica}, "
                f"nao em {uf.strip().upper()}"
            )
    elif regra.uf_obrigatoria and not uf and not regra.uf_e_filtro_analitico:
        raise EscopoInvalidoError(f"{cargo_norm} exige uma UF")

    if regra.municipio_obrigatorio and not municipio:
        raise EscopoInvalidoError(f"{cargo_norm} exige um municipio")

    if turno == 2 and not regra.permite_segundo_turno:
        raise EscopoInvalidoError(
            f"{cargo_norm} nao tem segundo turno (cargo proporcional ou "
            f"disputa decidida em turno unico)"
        )
    if turno not in (1, 2):
        raise EscopoInvalidoError(f"Turno invalido: {turno}")

    eleicao_cfg = _eleicao_cfg(ano)
    return EscopoEleitoral(
        ano_eleicao=ano,
        cargo=cargo_norm,
        tipo_abrangencia=regra.tipo_abrangencia,
        uf_obrigatoria=regra.uf_obrigatoria,
        municipio_obrigatorio=regra.municipio_obrigatorio,
        uf_e_filtro_analitico=regra.uf_e_filtro_analitico,
        niveis_territoriais_disponiveis=regra.niveis_territoriais_disponiveis,
        permite_segundo_turno=regra.permite_segundo_turno,
        universo_eleitoral=regra.universo_eleitoral,
        tipos_concorrentes_validos=regra.tipos_concorrentes_validos,
        filtro_sql_ds_eleicao=eleicao_cfg["ds_eleicao_ilike_por_abrangencia"][regra.tipo_abrangencia],
        filtro_sql_tp_abrangencia=eleicao_cfg["tp_abrangencia_por_cargo"].get(regra.tipo_abrangencia),
    )
