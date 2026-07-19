"""Garante que o pacote de dados NACIONAIS reduzido (Parquet, ver
scripts/preparar_dados_nacionais.py) esteja disponivel em data/raw/ antes
do app rodar. Local-first: se os arquivos ja existem (maquina de
desenvolvimento, ou execucao anterior na nuvem), nao baixa nada de novo.

Cobre apenas os arquivos NACIONAIS (registro de candidatos, eleitorado por
local de votacao, censitarios IBGE, RAIS/CAGED) - a votacao_secao e a
malha de setores/bairros de cada UF sao baixadas sob demanda por
src/uf_data_bootstrap.py na primeira busca de um candidato daquele estado,
nao aqui (pre-carregar as 27 UFs de uma vez nao caberia neste pacote).

Usado especificamente para o deploy em ambientes efemeros (Streamlit
Community Cloud), onde data/raw/ nao e versionado no git (arquivos
grandes demais) e precisa ser reconstituido a cada novo container.
"""
from __future__ import annotations

from pathlib import Path

import requests
import streamlit as st

from .utils import data_sources, get_logger, resolve_path

logger = get_logger(__name__)


def _arquivos_faltantes() -> list[str]:
    cfg = data_sources().get("pacote_cloud")
    if not cfg:
        return []
    pasta = resolve_path("data/raw")
    return [nome for nome in cfg["arquivos"] if not (pasta / nome).exists()]


def _baixar(nome_arquivo: str, url_base: str) -> None:
    destino = resolve_path("data/raw") / nome_arquivo
    destino.parent.mkdir(parents=True, exist_ok=True)
    url = f"{url_base}/{nome_arquivo}"
    logger.info("Baixando pacote de dados: %s", url)
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    with open(tmp, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
    tmp.rename(destino)


@st.cache_resource(show_spinner=False)
def garantir_dados_cloud() -> bool:
    """Baixa os arquivos parquet ausentes do GitHub Release configurado em
    config/data_sources.yaml (pacote_cloud). Retorna True se tudo ficou
    disponivel, False se algo falhou (o app deve seguir e reportar a
    limitacao, nao travar - secao 17 do briefing).

    `st.cache_resource` garante que isso roda uma unica vez por sessao do
    container, nao a cada rerun do Streamlit.
    """
    faltantes = _arquivos_faltantes()
    if not faltantes:
        return True

    cfg = data_sources()["pacote_cloud"]
    ok = True
    for nome_arquivo in faltantes:
        try:
            _baixar(nome_arquivo, cfg["url_base"])
        except Exception as exc:
            logger.error("Falha ao baixar %s: %s", nome_arquivo, exc)
            ok = False
    return ok
