"""Baixa e converte rede_social_candidato_{ano} (TSE - redes sociais
declaradas por candidato no registro de candidatura) para um parquet
nacional reduzido - mesmo padrao de preparar_bem_candidato.py.

Fonte real (confirmada por HEAD HTTP e inspecao de schema em 2026-08-11):
https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/rede_social_candidato_{ano}.zip
(fica dentro da pasta consulta_cand no CDN, nao numa pasta propria).

So mantem as colunas realmente usadas por src/candidate_social_media.py:
SQ_CANDIDATO (chave de juncao - mesma logica ja usada por bem_candidato/
candidate_assets.py, rede_social_candidato tambem NAO tem NR_CANDIDATO) e
DS_URL (link declarado, ex.: instagram.com/fulano, facebook.com/fulano).

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
    destino = DESTINO / f"rede_social_candidato_{ano}_BR.parquet"
    print(f"[{ano}] baixando rede_social_candidato_{ano}.zip ...")
    t0 = time.time()
    url = f"https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/rede_social_candidato_{ano}.zip"
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
            SELECT SQ_CANDIDATO, NR_ORDEM_REDE_SOCIAL, DS_URL
            FROM read_csv('{caminho_csv}', delim=';', header=true, quote='"',
                encoding='latin-1', ignore_errors=true)
        ) TO '{tmp_out.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    os.replace(tmp_out, destino)
    (tmp_dir / nome_csv).unlink(missing_ok=True)
    print(f"[{ano}] OK em {time.time()-t0:.1f}s - {destino.stat().st_size/1e6:.1f} MB - {destino}")


if __name__ == "__main__":
    processar_ano(2026)
    processar_ano(2024)
    processar_ano(2022)
