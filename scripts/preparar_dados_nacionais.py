"""Gera as versoes NACIONAIS (Brasil inteiro) dos arquivos que ja vinham de
uma fonte nacional na origem, mas eram filtrados para SP em
`preparar_dados_cloud.py` (consulta_cand, eleitorado_local_votacao,
detalhe_votacao_secao, agregados censitarios IBGE).

Os arquivos verdadeiramente por-UF (votacao_secao, malha de setores/bairros)
NAO entram aqui - esses sao baixados e convertidos sob demanda em tempo de
execucao pelo proprio app (ver src/uf_data_bootstrap.py), para nao precisar
pre-processar os 27 estados de uma vez.

Roda uma unica vez, localmente, a partir dos arquivos ja baixados/extraidos
em data/raw/ e C:/Users/Tales/Downloads/. Nenhum dado e alterado/fabricado -
mesma informacao oficial, so sem o recorte para SP.
"""
from __future__ import annotations

import time
from pathlib import Path

import duckdb
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "data" / "cloud_bundle"
SAIDA.mkdir(parents=True, exist_ok=True)


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='3GB'")
    con.execute("PRAGMA threads=4")
    temp_dir = RAIZ / "data" / "cache" / "duckdb_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    con.execute(f"PRAGMA temp_directory='{temp_dir.as_posix()}'")
    return con


def converter_consulta_cand_nacional() -> None:
    origem = str(RAIZ / "data" / "raw" / "consulta_cand_2024_BRASIL.csv").replace("\\", "/")
    destino = SAIDA / "consulta_cand_2024_BR.parquet"
    print(f"[1/5] consulta_cand (Brasil) -> {destino.name} ...")
    t0 = time.time()
    con = _con()
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
    print(f"      OK em {time.time()-t0:.1f}s - {destino.stat().st_size/1e6:.1f} MB")


def converter_eleitorado_local_nacional() -> None:
    origem = str(RAIZ / "data" / "raw" / "eleitorado_local_votacao_2024.csv").replace("\\", "/")
    destino = SAIDA / "eleitorado_local_votacao_BR.parquet"
    print(f"[2/5] eleitorado_local_votacao (Brasil) -> {destino.name} ...")
    t0 = time.time()
    con = _con()
    con.execute(f"""
        COPY (
            SELECT SG_UF, CD_MUNICIPIO, NM_MUNICIPIO, NR_ZONA, NR_SECAO, NR_LOCAL_VOTACAO,
                   NM_LOCAL_VOTACAO, NM_BAIRRO, NR_CEP, NR_LATITUDE, NR_LONGITUDE
            FROM read_csv('{origem}', delim=';', header=true, quote='"',
                encoding='latin-1', ignore_errors=true)
        ) TO '{destino.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    print(f"      OK em {time.time()-t0:.1f}s - {destino.stat().st_size/1e6:.1f} MB")


def converter_detalhe_votacao_nacional() -> None:
    origem = str(RAIZ / "data" / "raw" / "detalhe_votacao_secao_2024_BRASIL.csv").replace("\\", "/")
    destino = SAIDA / "detalhe_votacao_secao_2024_BR.parquet"
    print(f"[3/5] detalhe_votacao_secao (Brasil) -> {destino.name} ...")
    t0 = time.time()
    con = _con()
    con.execute(f"""
        COPY (
            SELECT CD_MUNICIPIO, NR_ZONA, NR_SECAO, DS_CARGO, QT_APTOS,
                   QT_COMPARECIMENTO, QT_ABSTENCOES, QT_VOTOS_BRANCOS, QT_VOTOS_NULOS
            FROM read_csv('{origem}', delim=';', header=true, quote='"',
                encoding='latin-1', ignore_errors=true)
        ) TO '{destino.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    print(f"      OK em {time.time()-t0:.1f}s - {destino.stat().st_size/1e6:.1f} MB")


_IBGE_FONTES = {
    "Agregados_por_setores_demografia_BR.zip": (
        "demografia_setores_BR.parquet",
        ["CD_setor", "V01006", "V01007", "V01008", "V01031", "V01032", "V01033", "V01034",
         "V01035", "V01036", "V01037", "V01038", "V01039", "V01040", "V01041"],
    ),
    "Agregados_por_setores_cor_ou_raca_BR.zip": (
        "cor_raca_setores_BR.parquet",
        ["CD_SETOR", "V01317", "V01318", "V01319", "V01320", "V01321"],
    ),
    "Agregados_por_setores_alfabetizacao_BR.zip": (
        "alfabetizacao_setores_BR.parquet",
        ["CD_setor"] + [f"V00{n}" for n in range(644, 657)] + [f"V00{n}" for n in range(748, 761)],
    ),
    "Agregados_por_setores_renda_responsavel_BR_csv.zip": (
        "renda_setores_BR.parquet",
        ["CD_SETOR", "V06001", "V06002", "V06004"],
    ),
    "Agregados_por_setores_parentesco_BR.zip": (
        "parentesco_setores_BR.parquet",
        ["CD_SETOR", "V01042", "V01062", "V01063"],
    ),
    "Agregados_por_setores_caracteristicas_domicilio2_BR_20250417.zip": (
        "domicilio2_setores_BR.parquet",
        ["setor", "V00199", "V00200", "V00201",
         "V00309", "V00310", "V00311", "V00312", "V00313", "V00314", "V00315", "V00316",
         "V00397", "V00398", "V00399", "V00400", "V00401", "V00402"],
    ),
}


def converter_agregados_ibge_nacional() -> None:
    print("[4/5] Agregados IBGE (Brasil inteiro, sem recorte de UF) ...")
    downloads = Path("C:/Users/Tales/Downloads")
    for nome_zip, (nome_saida, colunas) in _IBGE_FONTES.items():
        origem = downloads / nome_zip
        destino = SAIDA / nome_saida
        t0 = time.time()
        df = pd.read_csv(origem, sep=";", usecols=colunas, dtype=str, encoding="latin-1")
        df.to_parquet(destino, compression="zstd", index=False)
        print(f"      {nome_saida}: OK em {time.time()-t0:.1f}s - {destino.stat().st_size/1e6:.1f} MB - {len(df)} setores")


if __name__ == "__main__":
    converter_consulta_cand_nacional()
    converter_eleitorado_local_nacional()
    converter_detalhe_votacao_nacional()
    converter_agregados_ibge_nacional()

    total = sum(f.stat().st_size for f in SAIDA.glob("*_BR.parquet")) / 1e6
    print(f"\nTotal dos arquivos nacionais gerados: {total:.1f} MB em {SAIDA}")
