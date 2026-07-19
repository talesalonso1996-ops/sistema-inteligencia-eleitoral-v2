"""Garante os dados POR UF (votacao_secao + malha de setores/bairros
censitarios) sob demanda: diferente do pacote "nucleo" (nacional, sempre
baixado de uma unica vez via GitHub Release em cloud_data_bootstrap.py),
estes arquivos sao grandes o suficiente por estado - so a votacao por
secao de um estado grande pode passar de 1GB - que pre-processar as 27
UFs de uma vez nao caberia no ambiente gratuito de deploy.

Por isso cada UF so e baixada/convertida (direto da fonte oficial: TSE cdn
+ IBGE geoftp) na primeira vez que um candidato daquele estado e
efetivamente buscado, e o resultado fica salvo em data/raw/ (arquivo
parquet reduzido) para as buscas seguintes - nesta sessao do container e,
em ambiente local, permanentemente.

O ano eleitoral (`ano`) e parametrizado (default 2024, para preservar
identico o comportamento/caminhos ja usados por todo chamador existente) -
os templates de URL/nome de arquivo por ano vem de
`config/data_sources.yaml: eleicoes.<ano>` (ver src/rules/electoral_scope.py),
nunca de um literal "2024" espalhado pelo codigo.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import duckdb
import geopandas as gpd
import requests
import streamlit as st

from .utils import data_sources, get_logger, resolve_path

logger = get_logger(__name__)

_IBGE_MALHA_URL = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
    "malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/"
    "{tipo}/gpkg/UF/{uf}/{uf}_{tipo}_CD2022.gpkg"
)

_COLUNAS_SETORES = ["CD_SETOR", "CD_MUN", "NM_MUN", "NM_DIST", "CD_BAIRRO", "geometry"]
_COLUNAS_BAIRROS = ["CD_MUN", "NM_MUN", "NM_BAIRRO", "geometry"]


def _eleicao_cfg(ano: int) -> dict:
    eleicoes = data_sources().get("eleicoes", {})
    if ano not in eleicoes:
        raise ValueError(f"Ano eleitoral nao configurado em config/data_sources.yaml: eleicoes.{ano}")
    return eleicoes[ano]


def caminho_votacao_secao(uf: str, ano: int = 2024) -> Path:
    nome = _eleicao_cfg(ano)["votacao_secao_arquivo"].format(UF=uf.upper())
    return resolve_path("data/raw") / nome


def caminho_malha(tipo: str, uf: str) -> Path:
    return resolve_path("data/raw") / f"{uf.upper()}_{tipo}_CD2022.parquet"


def _pasta_tmp() -> Path:
    pasta = resolve_path("data/cache/uf_download_tmp")
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _baixar(url: str) -> bytes:
    resp = requests.get(url, timeout=600, stream=True)
    resp.raise_for_status()
    return resp.content


def _garantir_votacao_secao_uf(uf: str, ano: int = 2024) -> bool:
    destino = caminho_votacao_secao(uf, ano)
    if destino.exists():
        return True

    url = _eleicao_cfg(ano)["votacao_secao_url"].format(uf=uf.upper())
    logger.info("Baixando votacao_secao %s da UF %s: %s", ano, uf, url)
    try:
        conteudo = _baixar(url)
    except Exception:
        logger.exception("Falha ao baixar votacao_secao %s para UF %s", ano, uf)
        return False

    pasta_tmp = _pasta_tmp()
    nome_csv = None
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            candidatos = [
                n for n in z.namelist()
                if n.lower().endswith(".csv") and "brasil" not in n.lower()
            ]
            if not candidatos:
                logger.error("Nenhum CSV de secao encontrado no zip da UF %s", uf)
                return False
            nome_csv = candidatos[0]
            z.extract(nome_csv, pasta_tmp)
        caminho_csv = (pasta_tmp / nome_csv).as_posix()

        con = duckdb.connect()
        con.execute("PRAGMA memory_limit='1800MB'")
        con.execute("PRAGMA threads=4")
        temp_dir = resolve_path("data/cache/duckdb_tmp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        con.execute(f"PRAGMA temp_directory='{temp_dir.as_posix()}'")

        tmp_out = destino.with_suffix(".tmp")
        con.execute(f"""
            COPY (
                SELECT NR_VOTAVEL, NM_VOTAVEL, DS_CARGO, CD_MUNICIPIO, NM_MUNICIPIO,
                       ANO_ELEICAO, NR_TURNO, NR_ZONA, NR_SECAO, NR_LOCAL_VOTACAO,
                       NM_LOCAL_VOTACAO, QT_VOTOS
                FROM read_csv('{caminho_csv}', delim=';', header=true, quote='"',
                    encoding='latin-1', ignore_errors=true)
            ) TO '{tmp_out.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        tmp_out.rename(destino)
        logger.info("votacao_secao %s da UF %s convertida: %s", ano, uf, destino)
        return True
    except Exception:
        logger.exception("Falha ao converter votacao_secao %s da UF %s", ano, uf)
        return False
    finally:
        if nome_csv:
            (pasta_tmp / nome_csv).unlink(missing_ok=True)


def _garantir_malha_tipo_uf(tipo: str, uf: str) -> bool:
    destino = caminho_malha(tipo, uf)
    if destino.exists():
        return True

    url = _IBGE_MALHA_URL.format(tipo=tipo, uf=uf.upper())
    logger.info("Baixando malha de %s da UF %s: %s", tipo, uf, url)
    try:
        conteudo = _baixar(url)
    except Exception:
        logger.exception("Falha ao baixar malha de %s para UF %s (pode nao existir para esta UF)", tipo, uf)
        return False

    pasta_tmp = _pasta_tmp()
    caminho_gpkg = pasta_tmp / f"{uf.upper()}_{tipo}_CD2022.gpkg"
    try:
        caminho_gpkg.write_bytes(conteudo)
        gdf = gpd.read_file(caminho_gpkg)
        colunas = _COLUNAS_SETORES if tipo == "setores" else _COLUNAS_BAIRROS
        gdf = gdf[[c for c in colunas if c in gdf.columns]]
        tmp_out = destino.with_suffix(".tmp")
        gdf.to_parquet(tmp_out, compression="zstd")
        tmp_out.rename(destino)
        logger.info("Malha de %s da UF %s convertida: %s", tipo, uf, destino)
        return True
    except Exception:
        logger.exception("Falha ao converter malha de %s da UF %s", tipo, uf)
        return False
    finally:
        caminho_gpkg.unlink(missing_ok=True)


@st.cache_resource(show_spinner=False)
def garantir_dados_uf(uf: str, ano: int = 2024) -> bool:
    """Garante votacao_secao da UF (do ano eleitoral informado) em
    data/raw/, baixando e convertendo sob demanda (TSE cdn) na primeira
    busca daquele estado/ano. Cacheado por (UF, ano) - `st.cache_resource`
    chaveia pelos argumentos - nao repete o download na mesma sessao do
    container. Default `ano=2024` preserva o comportamento/assinatura ja
    usado por todo chamador existente do V1.

    NAO baixa a malha geografica (setores/bairros) aqui - um numero de
    candidato pode aparecer em varias UFs no registro nacional
    (consulta_cand) so para descobrir o total de votos de cada uma, e a
    malha (bem mais pesada, e a mesma para qualquer ano eleitoral - Censo
    2022 nao muda por ano de eleicao) so e realmente necessaria depois que
    o usuario ESCOLHE uma candidatura especifica para analisar (ver
    garantir_malha_uf, chamada por geographic_analysis.carregar_malha)."""
    return _garantir_votacao_secao_uf(uf, ano)


@st.cache_resource(show_spinner=False)
def garantir_malha_uf(uf: str) -> bool:
    """Garante a malha (setores + bairros, CD2022) da UF em data/raw/,
    baixando e convertendo sob demanda (IBGE geoftp) na primeira vez que uma
    candidatura daquele estado e efetivamente analisada (nao apenas
    encontrada na busca). Best-effort: algumas UFs podem nao ter um dos
    dois produtos publicados (ex.: bairros) - a ausencia degrada
    graciosamente para "sem aquele nivel de analise espacial", nunca
    trava o sistema nem simula poligono algum."""
    ok_setores = _garantir_malha_tipo_uf("setores", uf)
    ok_bairros = _garantir_malha_tipo_uf("bairros", uf)
    return ok_setores or ok_bairros
