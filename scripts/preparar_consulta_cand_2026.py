"""Gera data/raw/consulta_cand_2026_BR.parquet a partir do
consulta_cand_2026_BRASIL.csv oficial do TSE (mesmas colunas usadas por
converter_consulta_cand_nacional() em preparar_dados_nacionais.py, para
manter o schema identico ao de 2024/2022/2018).

Roda uma unica vez, localmente, a partir do CSV ja baixado e extraido do
CDN do TSE (https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/
consulta_cand_2026.zip). Ver observacao real registrada em
config/data_sources.yaml: eleicoes.2026 - o registro de candidaturas de
2026 esta EM ANDAMENTO (prazo de registro ainda aberto na data desta
conversao), os numeros crescem a cada nova consulta ao TSE.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent


def converter(origem_csv: str) -> None:
    destino = RAIZ / "data" / "raw" / "consulta_cand_2026_BR.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    print(f"consulta_cand_2026 (Brasil) -> {destino.name} ...")
    t0 = time.time()
    con = duckdb.connect()
    con.execute(f"""
        COPY (
            SELECT NR_CANDIDATO, NM_CANDIDATO, NM_URNA_CANDIDATO, DS_CARGO, NM_UE, SG_UE,
                   SG_UF, ANO_ELEICAO, NR_TURNO, NR_PARTIDO, SG_PARTIDO, NM_PARTIDO,
                   NM_COLIGACAO, NM_FEDERACAO, DS_SITUACAO_CANDIDATURA, DS_SIT_TOT_TURNO,
                   DS_ELEICAO, TP_ABRANGENCIA, SQ_CANDIDATO
            FROM read_csv('{origem_csv.replace(chr(92), "/")}', delim=';', header=true, quote='"',
                encoding='latin-1', ignore_errors=true)
        ) TO '{destino.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    print(f"      OK em {time.time()-t0:.1f}s - {destino.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python scripts/preparar_consulta_cand_2026.py <caminho para consulta_cand_2026_BRASIL.csv>")
        sys.exit(1)
    converter(sys.argv[1])
