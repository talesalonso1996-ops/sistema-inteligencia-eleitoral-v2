"""Redes sociais declaradas por candidato (TSE - rede_social_candidato).

Mesmo padrao de src/candidate_assets.py (patrimonio): rede_social_candidato
tambem NAO identifica o candidato por NR_CANDIDATO, so por SQ_CANDIDATO -
reusa a mesma resolucao (_resolver_sq_candidato) ja usada la, para nao
duplicar aquela logica de filtro por ano/cargo/UF/municipio/turno.

Schema real (confirmado por inspecao de rede_social_candidato_2026_BRASIL.csv
via DuckDB em 2026-08-11 - mesmas colunas usadas em 2022/2024): SQ_CANDIDATO,
NR_ORDEM_REDE_SOCIAL, DS_URL. DS_URL vem em maiusculas e por vezes e' so um
identificador de usuario (ex.: "@FULANO.UP") em vez de uma URL completa -
nunca normalizado/corrigido aqui, mostrado exatamente como o candidato
declarou ao TSE."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .candidate_assets import _resolver_sq_candidato
from .candidate_finder import Candidatura
from .utils import get_logger, resolve_path

logger = get_logger(__name__)

_PLATAFORMAS = {
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "x.com": "X (Twitter)",
    "twitter.com": "X (Twitter)",
    "tiktok.com": "TikTok",
    "youtube.com": "YouTube",
    "linkedin.com": "LinkedIn",
    "threads.com": "Threads",
    "threads.net": "Threads",
    "kwai.com": "Kwai",
}


def _identificar_plataforma(url: str) -> str:
    url_low = url.lower()
    for dominio, nome in _PLATAFORMAS.items():
        if dominio in url_low:
            return nome
    return "Outro"


@dataclass
class PerfilRedesSociaisCandidato:
    numero: int
    redes: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=["plataforma", "url"]))
    disponivel: bool = False
    limitacoes: str = (
        "Links autodeclarados pelo proprio candidato ao TSE no registro de candidatura - "
        "nao verificados quanto a autenticidade/atividade da conta."
    )


def _caminho(caminho: str) -> str:
    return caminho if (len(caminho) > 1 and caminho[1] == ":") else str(resolve_path(caminho))


def _perfil_vazio(numero: int) -> PerfilRedesSociaisCandidato:
    return PerfilRedesSociaisCandidato(numero=numero, disponivel=False)


def carregar_redes_sociais_candidato(candidatura: Candidatura) -> PerfilRedesSociaisCandidato:
    """Ponto de entrada principal: redes sociais declaradas pelo candidato
    ao TSE. Nunca lanca excecao por dado ausente - retorna disponivel=False
    se a fonte nao existir ou o candidato nao tiver declarado nenhuma rede
    (nunca inventa link)."""
    sq_candidato = _resolver_sq_candidato(
        candidatura.numero, candidatura.ano_eleicao, candidatura.cargo, candidatura.turno,
        candidatura.uf, candidatura.codigo_municipio_tse, candidatura.municipio,
    )
    if sq_candidato is None:
        return _perfil_vazio(candidatura.numero)

    from pathlib import Path

    caminho = _caminho(f"data/raw/rede_social_candidato_{candidatura.ano_eleicao}_BR.parquet")
    if not Path(caminho).exists():
        logger.warning("Arquivo rede_social_candidato nao encontrado: %s", caminho)
        return _perfil_vazio(candidatura.numero)

    df = pd.read_parquet(caminho)
    linhas = df[df["SQ_CANDIDATO"] == sq_candidato]
    if linhas.empty:
        return _perfil_vazio(candidatura.numero)

    redes = (
        linhas.sort_values("NR_ORDEM_REDE_SOCIAL")[["DS_URL"]]
        .rename(columns={"DS_URL": "url"})
        .reset_index(drop=True)
    )
    redes["plataforma"] = redes["url"].map(_identificar_plataforma)
    redes = redes[["plataforma", "url"]]
    return PerfilRedesSociaisCandidato(numero=candidatura.numero, redes=redes, disponivel=True)
