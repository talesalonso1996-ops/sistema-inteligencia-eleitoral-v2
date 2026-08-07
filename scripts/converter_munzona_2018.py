"""Converte o mirror alternativo de votacao_candidato_munzona_2018 (fonte:
data.brasil.io, ja que o CDN oficial do TSE bloqueia o download direto de
votacao_secao_2018 com 403) para um parquet nacional reduzido, no mesmo
padrao dos demais arquivos _BR.parquet ja usados no projeto.

Granularidade: candidato x municipio x zona x turno (NAO e nivel de secao -
o mirror so tem QT_VOTOS_NOMINAIS agregado ja por zona, sem legenda). Cargos
mantidos: os 4 ja suportados por electoral_scope.py para 2018 (Governador,
Senador, Deputado Federal, Deputado Estadual) - o arquivo BR.csv
(Presidente) e excluido de proposito, fora do escopo atual.

Rodar uma unica vez, manualmente, a partir da pasta com os CSVs extraidos
do zip baixado de
https://data.brasil.io/mirror/eleicoes-brasil/votacao_candidato_munzona/votacao_candidato_munzona_2018.zip
(nao versionado - arquivo grande demais, baixado sob demanda)."""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

_CARGOS_2018 = ("Governador", "Senador", "Deputado Federal", "Deputado Estadual")


def converter(pasta_csvs: Path, destino: Path) -> None:
    csvs = sorted(
        p for p in pasta_csvs.glob("votacao_candidato_munzona_2018_*.csv")
        if p.stem.rsplit("_", 1)[-1] not in ("BR", "BRASIL")
    )
    if not csvs:
        raise SystemExit(f"Nenhum CSV de UF encontrado em {pasta_csvs}")

    lista = ", ".join(f"'{p.as_posix()}'" for p in csvs)
    cargos_sql = ", ".join(f"'{c}'" for c in _CARGOS_2018)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute(f"PRAGMA memory_limit='3GB'")

    sql = f"""
        COPY (
            SELECT
                CAST(NR_CANDIDATO AS INTEGER) AS NR_VOTAVEL,
                NM_URNA_CANDIDATO AS NM_VOTAVEL,
                DS_CARGO,
                SG_UF,
                CAST(CD_MUNICIPIO AS INTEGER) AS CD_MUNICIPIO,
                NM_MUNICIPIO,
                CAST(ANO_ELEICAO AS INTEGER) AS ANO_ELEICAO,
                CAST(NR_TURNO AS INTEGER) AS NR_TURNO,
                CAST(NR_ZONA AS INTEGER) AS NR_ZONA,
                SG_PARTIDO,
                DS_SIT_TOT_TURNO,
                CAST(QT_VOTOS_NOMINAIS AS INTEGER) AS QT_VOTOS
            FROM read_csv([{lista}], delim=';', header=true, quote='"',
                          encoding='latin-1', ignore_errors=true, union_by_name=true)
            WHERE DS_CARGO IN ({cargos_sql})
        ) TO '{destino.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """
    print(f"Convertendo {len(csvs)} arquivos de UF -> {destino}")
    con.execute(sql)

    n = con.execute(f"SELECT COUNT(*) FROM read_parquet('{destino.as_posix()}')").fetchone()[0]
    print(f"OK: {n} linhas gravadas em {destino} ({destino.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/raw/votacao_candidato_munzona_2018_BR.parquet")
    dest.parent.mkdir(parents=True, exist_ok=True)
    converter(pasta, dest)
