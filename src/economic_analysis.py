"""Perfil economico do municipio - RAIS Estabelecimentos + Novo CAGED
(secao adicional do produto: contexto economico local).

Ambas as fontes tem granularidade de MUNICIPIO (a RAIS Estabelecimentos tem
CNAE por estabelecimento, mas nao tem distrito/bairro fora da capital de
SP) - por isso este modulo NAO alimenta a regressao/clusterizacao
territorial (que opera em nivel de distrito/zona dentro de um unico
municipio: uma variavel sem variacao dentro do municipio nao tem poder
explicativo ali). E exibido como CONTEXTO ECONOMICO do municipio no
relatorio e na interface - dado real, documentado, mas de outro nivel de
agregacao, comunicado explicitamente.

O codigo de municipio da RAIS/CAGED e o codigo IBGE de 7 digitos SEM o
digito verificador final (ex.: Sao Paulo capital = 3550308 (IBGE) ->
355030 (RAIS)) - resolvido aqui reaproveitando a malha de setores
censitarios ja carregada em geographic_analysis.carregar_malha (mesma
fonte, CD_MUN).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .candidate_finder import Candidatura
from .geographic_analysis import carregar_malha
from .utils import cache_key, data_sources, get_logger, read_cache, resolve_path, write_cache

logger = get_logger(__name__)


@dataclass
class PerfilEconomicoMunicipio:
    codigo_municipio_rais: str | None
    vinculos_ativos_total: int | None
    estabelecimentos_ativos: int | None
    saldo_caged_2024: int | None
    admissoes_2024: int | None
    desligamentos_2024: int | None
    tendencia: str  # "crescimento" | "estavel" | "retracao" | "indisponivel"
    disponivel: bool
    vinculos_clt_total: int | None = None
    estabelecimentos_total: int | None = None
    pct_formalizacao_clt: float | None = None  # % dos vinculos ativos que sao CLT
    taxa_atividade_empresarial: float | None = None  # % dos estabelecimentos cadastrados que estao ativos
    limitacoes: str = (
        "RAIS Estabelecimentos e CAGED tem granularidade de MUNICIPIO, nao de "
        "distrito/zona/bairro - por isso sao exibidos como contexto economico "
        "do municipio, nao como variavel da regressao/clusterizacao territorial "
        "(que compara territorios DENTRO do mesmo municipio)."
    )


def _caminho(caminho: str) -> str:
    return caminho if (len(caminho) > 1 and caminho[1] == ":") else str(resolve_path(caminho))


def resolver_codigo_municipio_rais(candidatura: Candidatura) -> str | None:
    """Deriva o codigo de municipio no formato RAIS/CAGED (IBGE 7 digitos
    sem o digito verificador) a partir da malha de setores censitarios ja
    usada em geographic_analysis (mesma fonte oficial IBGE CD_MUN)."""
    setores = carregar_malha("setores", candidatura.municipio, candidatura.uf)
    if setores is None or setores.empty or "CD_MUN" not in setores.columns:
        logger.warning(
            "Nao foi possivel resolver o codigo RAIS do municipio '%s' - malha indisponivel.",
            candidatura.municipio,
        )
        return None
    cd_mun_ibge = str(setores["CD_MUN"].iloc[0]).strip()
    if len(cd_mun_ibge) < 7:
        return None
    return cd_mun_ibge[:6]


def _classificar_tendencia(saldo: int, vinculos_ativos: int) -> str:
    if vinculos_ativos <= 0:
        return "indisponivel"
    variacao_pct = 100 * saldo / vinculos_ativos
    if variacao_pct >= 1.0:
        return "crescimento"
    if variacao_pct <= -1.0:
        return "retracao"
    return "estavel"


def carregar_perfil_economico_municipio(candidatura: Candidatura) -> PerfilEconomicoMunicipio:
    """Ponto de entrada principal: retorna o perfil economico do municipio
    da candidatura (RAIS + CAGED). Nunca lanca excecao por dado ausente -
    retorna disponivel=False com tendencia='indisponivel' se a fonte nao
    existir ou o municipio nao for encontrado (secao 17 do briefing:
    degradar graciosamente, nunca inventar)."""
    key = cache_key("perfil_economico", candidatura.codigo_municipio_tse, candidatura.municipio)
    cached = read_cache("economic_analysis", key)
    if cached is not None and not cached.empty:
        row = cached.iloc[0]
        return PerfilEconomicoMunicipio(**{**row.to_dict(), "disponivel": bool(row["disponivel"])})

    codigo_rais = resolver_codigo_municipio_rais(candidatura)
    if codigo_rais is None:
        resultado = PerfilEconomicoMunicipio(
            codigo_municipio_rais=None, vinculos_ativos_total=None, estabelecimentos_ativos=None,
            saldo_caged_2024=None, admissoes_2024=None, desligamentos_2024=None,
            tendencia="indisponivel", disponivel=False,
        )
        return resultado

    fontes = data_sources()["mte"]
    caminho_rais = _caminho(fontes["rais_estabelecimentos"]["arquivo_local"])
    caminho_caged = _caminho(fontes["caged"]["arquivo_local"])

    rais_df = pd.read_parquet(caminho_rais)
    caged_df = pd.read_parquet(caminho_caged)

    linha_rais = rais_df[rais_df["codigo_municipio_rais"] == codigo_rais]
    linha_caged = caged_df[caged_df["codigo_municipio_rais"] == codigo_rais]

    if linha_rais.empty and linha_caged.empty:
        resultado = PerfilEconomicoMunicipio(
            codigo_municipio_rais=codigo_rais, vinculos_ativos_total=None, estabelecimentos_ativos=None,
            saldo_caged_2024=None, admissoes_2024=None, desligamentos_2024=None,
            tendencia="indisponivel", disponivel=False,
        )
        return resultado

    vinculos_ativos = int(linha_rais["vinculos_ativos_total"].iloc[0]) if not linha_rais.empty else None
    estabelecimentos_ativos = int(linha_rais["estabelecimentos_ativos"].iloc[0]) if not linha_rais.empty else None
    vinculos_clt = int(linha_rais["vinculos_clt_total"].iloc[0]) if not linha_rais.empty else None
    estabelecimentos_total = int(linha_rais["estabelecimentos_total"].iloc[0]) if not linha_rais.empty else None
    saldo = int(linha_caged["saldo_caged_2024"].iloc[0]) if not linha_caged.empty else None
    admissoes = int(linha_caged["admissoes_2024"].iloc[0]) if not linha_caged.empty else None
    desligamentos = int(linha_caged["desligamentos_2024"].iloc[0]) if not linha_caged.empty else None

    tendencia = (
        _classificar_tendencia(saldo, vinculos_ativos)
        if saldo is not None and vinculos_ativos is not None
        else "indisponivel"
    )

    pct_formalizacao_clt = (
        round(100 * vinculos_clt / vinculos_ativos, 2)
        if vinculos_clt is not None and vinculos_ativos else None
    )
    taxa_atividade_empresarial = (
        round(100 * estabelecimentos_ativos / estabelecimentos_total, 2)
        if estabelecimentos_ativos is not None and estabelecimentos_total else None
    )

    resultado = PerfilEconomicoMunicipio(
        codigo_municipio_rais=codigo_rais,
        vinculos_ativos_total=vinculos_ativos,
        estabelecimentos_ativos=estabelecimentos_ativos,
        saldo_caged_2024=saldo,
        admissoes_2024=admissoes,
        desligamentos_2024=desligamentos,
        tendencia=tendencia,
        disponivel=True,
        vinculos_clt_total=vinculos_clt,
        estabelecimentos_total=estabelecimentos_total,
        pct_formalizacao_clt=pct_formalizacao_clt,
        taxa_atividade_empresarial=taxa_atividade_empresarial,
    )
    write_cache("economic_analysis", key, pd.DataFrame([resultado.__dict__]))
    return resultado
