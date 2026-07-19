"""Gera o pacote de dados enxuto (Parquet/GeoParquet) usado no deploy em
nuvem (Streamlit Community Cloud).

Roda uma unica vez, localmente, a partir dos arquivos oficiais ja baixados
(ver config/data_sources.yaml) e produz data/cloud_bundle/ com versoes
reduzidas: apenas as colunas realmente usadas pelo sistema, filtradas para
SP quando a fonte original e nacional, em formato colunar comprimido.

Nenhum dado e alterado/fabricado - e' a MESMA informacao oficial (TSE/IBGE),
apenas menos colunas e formato mais eficiente. Os arquivos gerados aqui sao
publicados como assets de uma GitHub Release e baixados automaticamente
pelo app quando os dados brutos completos nao estao disponiveis localmente
(ver src/cloud_data_bootstrap.py).
"""
from __future__ import annotations

import time
from pathlib import Path

import duckdb
import geopandas as gpd

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "data" / "cloud_bundle"
SAIDA.mkdir(parents=True, exist_ok=True)


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='2GB'")
    con.execute("PRAGMA threads=4")
    temp_dir = RAIZ / "data" / "cache" / "duckdb_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    con.execute(f"PRAGMA temp_directory='{temp_dir.as_posix()}'")
    return con


def converter_votacao_secao() -> None:
    origem = "C:/Users/Tales/Downloads/votacao_secao_2024_SP/votacao_secao_2024_SP.csv"
    destino = SAIDA / "votacao_secao_2024_SP.parquet"
    print(f"[1/6] votacao_secao_2024_SP -> {destino.name} ...")
    t0 = time.time()
    con = _con()
    con.execute(f"""
        COPY (
            SELECT NR_VOTAVEL, NM_VOTAVEL, DS_CARGO, CD_MUNICIPIO, NM_MUNICIPIO,
                   ANO_ELEICAO, NR_TURNO, NR_ZONA, NR_SECAO, NR_LOCAL_VOTACAO,
                   NM_LOCAL_VOTACAO, QT_VOTOS
            FROM read_csv('{origem}', delim=';', header=true, quote='"',
                encoding='latin-1', ignore_errors=true)
        ) TO '{destino.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    print(f"      OK em {time.time()-t0:.1f}s - {destino.stat().st_size/1e6:.1f} MB")


def converter_eleitorado_local() -> None:
    origem = str(RAIZ / "data" / "raw" / "eleitorado_local_votacao_2024.csv").replace("\\", "/")
    destino = SAIDA / "eleitorado_local_votacao_SP.parquet"
    print(f"[2/6] eleitorado_local_votacao (filtrado SP) -> {destino.name} ...")
    t0 = time.time()
    con = _con()
    con.execute(f"""
        COPY (
            SELECT CD_MUNICIPIO, NM_MUNICIPIO, NR_ZONA, NR_SECAO, NR_LOCAL_VOTACAO,
                   NM_LOCAL_VOTACAO, NM_BAIRRO, NR_LATITUDE, NR_LONGITUDE
            FROM read_csv('{origem}', delim=';', header=true, quote='"',
                encoding='latin-1', ignore_errors=true)
            WHERE SG_UF = 'SP'
        ) TO '{destino.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    print(f"      OK em {time.time()-t0:.1f}s - {destino.stat().st_size/1e6:.1f} MB")


def converter_detalhe_votacao() -> None:
    origem = str(RAIZ / "data" / "raw" / "detalhe_votacao_secao_2024_SP.csv").replace("\\", "/")
    destino = SAIDA / "detalhe_votacao_secao_2024_SP.parquet"
    print(f"[3/6] detalhe_votacao_secao_SP -> {destino.name} ...")
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


def converter_consulta_cand() -> None:
    origem = str(RAIZ / "data" / "raw" / "consulta_cand_2024_SP.csv").replace("\\", "/")
    destino = SAIDA / "consulta_cand_2024_SP.parquet"
    print(f"[4/6] consulta_cand_SP -> {destino.name} ...")
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


_IBGE_FONTES = {
    "Agregados_por_setores_demografia_BR.zip": (
        "demografia_setores_SP.parquet",
        ["CD_setor", "V01006", "V01007", "V01008", "V01031", "V01032", "V01033", "V01034",
         "V01035", "V01036", "V01037", "V01038", "V01039", "V01040", "V01041"],
        "CD_setor",
    ),
    "Agregados_por_setores_cor_ou_raca_BR.zip": (
        "cor_raca_setores_SP.parquet",
        ["CD_SETOR", "V01317", "V01318", "V01319", "V01320", "V01321"],
        "CD_SETOR",
    ),
    "Agregados_por_setores_alfabetizacao_BR.zip": (
        "alfabetizacao_setores_SP.parquet",
        ["CD_setor"] + [f"V00{n}" for n in range(644, 657)] + [f"V00{n}" for n in range(748, 761)],
        "CD_setor",
    ),
    "Agregados_por_setores_renda_responsavel_BR_csv.zip": (
        "renda_setores_SP.parquet",
        ["CD_SETOR", "V06001", "V06002", "V06004"],
        "CD_SETOR",
    ),
}


def converter_agregados_ibge() -> None:
    # DuckDB recusa alguns bytes destes arquivos mesmo com encoding='latin-1'
    # (validacao interna mais estrita); pandas decodifica latin-1 sem falhas
    # (mapeamento total sobre os 256 valores de byte), entao usamos pandas aqui.
    import pandas as pd

    print("[5/6] Agregados IBGE (filtrando setores de SP - prefixo '35') ...")
    downloads = Path("C:/Users/Tales/Downloads")
    for nome_zip, (nome_saida, colunas, col_setor) in _IBGE_FONTES.items():
        origem = downloads / nome_zip
        destino = SAIDA / nome_saida
        t0 = time.time()
        df = pd.read_csv(origem, sep=";", usecols=colunas, dtype=str, encoding="latin-1")
        df = df[df[col_setor].str.startswith("35")]
        df.to_parquet(destino, compression="zstd", index=False)
        print(f"      {nome_saida}: OK em {time.time()-t0:.1f}s - {destino.stat().st_size/1e6:.1f} MB")


def converter_malhas_geograficas() -> None:
    print("[6/6] Malhas geograficas (setores/bairros) -> GeoParquet ...")
    colunas_setores = ["CD_SETOR", "CD_MUN", "NM_MUN", "NM_DIST", "CD_BAIRRO", "geometry"]
    colunas_bairros = ["CD_MUN", "NM_MUN", "NM_BAIRRO", "geometry"]

    t0 = time.time()
    setores = gpd.read_file("C:/Users/Tales/Downloads/SP_setores_CD2022.gpkg")
    setores = setores[[c for c in colunas_setores if c in setores.columns]]
    destino_setores = SAIDA / "SP_setores_CD2022.parquet"
    setores.to_parquet(destino_setores, compression="zstd")
    print(f"      setores: OK em {time.time()-t0:.1f}s - {destino_setores.stat().st_size/1e6:.1f} MB")

    t0 = time.time()
    bairros = gpd.read_file("C:/Users/Tales/Downloads/SP_bairros_CD2022.gpkg")
    bairros = bairros[[c for c in colunas_bairros if c in bairros.columns]]
    destino_bairros = SAIDA / "SP_bairros_CD2022.parquet"
    bairros.to_parquet(destino_bairros, compression="zstd")
    print(f"      bairros: OK em {time.time()-t0:.1f}s - {destino_bairros.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    converter_votacao_secao()
    converter_eleitorado_local()
    converter_detalhe_votacao()
    converter_consulta_cand()
    converter_agregados_ibge()
    converter_malhas_geograficas()

    total = sum(f.stat().st_size for f in SAIDA.glob("*")) / 1e6
    print(f"\nTotal do pacote reduzido: {total:.1f} MB em {SAIDA}")
