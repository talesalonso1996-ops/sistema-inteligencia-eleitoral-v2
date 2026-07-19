"""Prepara os dados do PILOTO 2022 (SP - Governador): converte o
consulta_cand_2022 nacional (ja baixado em
data/cache/pilot_2022_tmp/consulta_cand_2022_BRASIL.csv, fonte oficial TSE
cdn) para o mesmo formato Parquet reduzido usado por 2024, e baixa/converte
votacao_secao_2022_SP via uf_data_bootstrap (parametrizado por ano).

Rodar uma unica vez, localmente, para validar o piloto antes de generalizar
para as demais UFs/cargos de 2022 (ver plano da V2)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import duckdb

from src.uf_data_bootstrap import garantir_dados_uf, caminho_votacao_secao


def converter_consulta_cand_2022() -> None:
    origem = str(RAIZ / "data" / "cache" / "pilot_2022_tmp" / "consulta_cand_2022_BRASIL.csv").replace("\\", "/")
    destino = RAIZ / "data" / "raw" / "consulta_cand_2022_BR.parquet"
    print(f"consulta_cand_2022 (Brasil) -> {destino.name} ...")
    t0 = time.time()
    con = duckdb.connect()
    con.execute(f"""
        COPY (
            SELECT NR_CANDIDATO, NM_CANDIDATO, NM_URNA_CANDIDATO, DS_CARGO, NM_UE, SG_UE,
                   SG_UF, ANO_ELEICAO, NR_TURNO, NR_PARTIDO, SG_PARTIDO, NM_PARTIDO,
                   NM_COLIGACAO, NM_FEDERACAO, DS_SITUACAO_CANDIDATURA, DS_SIT_TOT_TURNO,
                   DS_ELEICAO, TP_ABRANGENCIA
            FROM read_csv('{origem}', delim=';', header=true, quote='"',
                encoding='latin-1', ignore_errors=true)
        ) TO '{destino.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    print(f"  OK em {time.time()-t0:.1f}s - {destino.stat().st_size/1e6:.1f} MB")


def baixar_votacao_secao_2022_sp() -> None:
    print("votacao_secao_2022_SP -> baixando/convertendo (TSE cdn, pode levar alguns minutos)...")
    t0 = time.time()
    ok = garantir_dados_uf("SP", ano=2022)
    destino = caminho_votacao_secao("SP", ano=2022)
    if ok:
        print(f"  OK em {time.time()-t0:.1f}s - {destino} ({destino.stat().st_size/1e6:.1f} MB)")
    else:
        print("  FALHOU - ver logs")


if __name__ == "__main__":
    converter_consulta_cand_2022()
    baixar_votacao_secao_2022_sp()
