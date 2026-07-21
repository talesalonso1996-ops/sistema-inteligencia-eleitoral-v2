"""Regenera consulta_cand_2022_BR.parquet e consulta_cand_2024_BR.parquet
adicionando a coluna SQ_CANDIDATO - necessaria para juntar com
bem_candidato_{ano} (Fase 5, item C: bens declarados de candidatos), que
so identifica o candidato por SQ_CANDIDATO, nunca por NR_CANDIDATO.

Os CSVs originais de consulta_cand foram apagados de data/raw/ apos a
conversao inicial (so o parquet reduzido de 18 colunas foi mantido) -
baixa de novo direto da fonte oficial TSE cdn (mesma URL ja usada em
config/data_sources.yaml) e regenera o parquet com as MESMAS 18 colunas
de antes + SQ_CANDIDATO. Nenhuma query existente em candidate_finder.py
faz SELECT * nesse arquivo (sempre lista as colunas explicitamente) -
adicionar uma coluna e 100% aditivo, sem risco para o codigo ja em
producao.

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

_COLUNAS = (
    "NR_CANDIDATO, NM_CANDIDATO, NM_URNA_CANDIDATO, DS_CARGO, NM_UE, SG_UE, "
    "SG_UF, ANO_ELEICAO, NR_TURNO, NR_PARTIDO, SG_PARTIDO, NM_PARTIDO, "
    "NM_COLIGACAO, NM_FEDERACAO, DS_SITUACAO_CANDIDATURA, DS_SIT_TOT_TURNO, "
    "DS_ELEICAO, TP_ABRANGENCIA, SQ_CANDIDATO"
)


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='2GB'")
    temp_dir = RAIZ / "data" / "cache" / "duckdb_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    con.execute(f"PRAGMA temp_directory='{temp_dir.as_posix()}'")
    return con


def processar_ano(ano: int) -> None:
    destino = DESTINO / f"consulta_cand_{ano}_BR.parquet"
    print(f"[{ano}] baixando consulta_cand_{ano}.zip ...")
    t0 = time.time()
    url = f"https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{ano}.zip"
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
            SELECT {_COLUNAS}
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
