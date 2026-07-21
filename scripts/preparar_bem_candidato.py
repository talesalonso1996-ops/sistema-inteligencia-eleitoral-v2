"""Baixa e converte bem_candidato_{ano} (TSE - patrimonio declarado por
candidato) para um parquet nacional reduzido - mesmo padrao de
preparar_dados_nacionais.py, mas para uma fonte que so foi confirmada
depois daquele script (Fase 5, item C: bens declarados de candidatos).

So mantem as colunas realmente usadas por src/candidate_assets.py:
SQ_CANDIDATO (chave de juncao - bem_candidato NAO tem NR_CANDIDATO, so o
ID sequencial interno do TSE), tipo/descricao do bem e valor declarado.
VR_BEM_CANDIDATO vem com virgula decimal brasileira ("20000,00") - convertido
para DOUBLE aqui, mesmo tratamento ja usado em demographic_analysis.py.

Tamanho real confirmado antes de escrever este script: 2022 (~23MB CSV
nacional), 2024 (~46MB zip, maior por causa do volume de candidaturas
municipais) - pequeno o suficiente para um parquet nacional unico, sem
precisar de bootstrap por UF.

Rodar uma unica vez, localmente."""
from __future__ import annotations

import io
import os
import time
import zipfile
from pathlib import Path

import duckdb
import requests

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "data" / "raw"


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='2GB'")
    temp_dir = RAIZ / "data" / "cache" / "duckdb_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    con.execute(f"PRAGMA temp_directory='{temp_dir.as_posix()}'")
    return con


def processar_ano(ano: int) -> None:
    destino = DESTINO / f"bem_candidato_{ano}_BR.parquet"
    print(f"[{ano}] baixando bem_candidato_{ano}.zip ...")
    t0 = time.time()
    url = f"https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_{ano}.zip"
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()

    tmp_dir = RAIZ / "data" / "cache" / "uf_download_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        nome_csv = next(n for n in z.namelist() if "BRASIL" in n.upper())
        z.extract(nome_csv, tmp_dir)
    caminho_csv = (tmp_dir / nome_csv).as_posix()

    con = _con()
    tmp_out = destino.with_suffix(".tmp")
    con.execute(f"""
        COPY (
            SELECT
                SQ_CANDIDATO,
                DS_TIPO_BEM_CANDIDATO,
                DS_BEM_CANDIDATO,
                TRY_CAST(REPLACE(VR_BEM_CANDIDATO, ',', '.') AS DOUBLE) AS VR_BEM_CANDIDATO
            FROM read_csv('{caminho_csv}', delim=';', header=true, quote='"',
                encoding='latin-1', ignore_errors=true)
        ) TO '{tmp_out.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    os.replace(tmp_out, destino)
    (tmp_dir / nome_csv).unlink(missing_ok=True)
    print(f"[{ano}] OK em {time.time()-t0:.1f}s - {destino.stat().st_size/1e6:.1f} MB - {destino}")


if __name__ == "__main__":
    processar_ano(2022)
    processar_ano(2024)
