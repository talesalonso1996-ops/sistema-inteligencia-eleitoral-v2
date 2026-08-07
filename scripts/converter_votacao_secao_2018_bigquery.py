"""Constroi votacao_secao_2018_{UF}.parquet no MESMO schema que
votacao_secao_2022/2024 ja usam, a partir do dataset publico br_tse_eleicoes
do Base dos Dados (BigQuery) - fonte alternativa real ao CDN oficial do TSE,
que bloqueia (403/WAF) o download direto de votacao_secao_2018.

Exige autenticacao (Application Default Credentials - `gcloud auth
application-default login`) porque o dataset, embora publico, cobra a
consulta contra um projeto GCP do usuario (~1,5GB processados no total,
dentro do free tier). Roda uma unica vez, manualmente - o resultado final
(parquet por UF) e' publicado como asset da release do GitHub e usado como
fallback estatico por src/uf_data_bootstrap.py, nao uma consulta ao vivo em
producao (a credencial usada aqui e pessoal, nao pode ir para o deploy).

LIMITACOES REAIS desta fonte (documentadas, nunca escondidas):
- So votos NOMINAIS (sem legenda/branco/nulo) - resultado_geral()/
  votos_validos() ficam levemente diferentes de 2022/2024 para cargos
  proporcionais.
- Sem NR_LOCAL_VOTACAO/NM_LOCAL_VOTACAO reais (a tabela nao guarda qual
  predio fisico agrupa secoes, so zona+secao) - por isso NR_SECAO e usado
  como um NR_LOCAL_VOTACAO sintetico (cada secao vira seu proprio "local"),
  consistente com a fonte de coordenadas usada em
  scripts/converter_coordenadas_secao_2018_bigquery.py (tambem por secao,
  nao por predio) - ver src/geographic_analysis.py
  (_carregar_coordenadas_uf_2018) para o join que depende dessa
  consistencia."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

_CARGOS_2018 = ("Governador", "Senador", "Deputado Federal", "Deputado Estadual")
_UFS = (
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT",
    "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
)



def _lookup_municipios(pasta_raw: Path) -> pd.DataFrame:
    """CD_MUNICIPIO -> NM_MUNICIPIO, construido a partir dos arquivos de
    2022 ja baixados localmente (codigo/nome de municipio do TSE e' estavel
    entre ciclos - nao inventa nome novo)."""
    linhas = []
    for p in sorted(pasta_raw.glob("votacao_secao_2022_*.parquet")):
        df = pd.read_parquet(p, columns=["CD_MUNICIPIO", "NM_MUNICIPIO"])
        linhas.append(df.drop_duplicates())
    todos = pd.concat(linhas, ignore_index=True).drop_duplicates(subset="CD_MUNICIPIO")
    return todos.set_index("CD_MUNICIPIO")["NM_MUNICIPIO"]


def _lookup_candidatos(pasta_raw: Path) -> pd.DataFrame:
    """(uf, cargo, numero) -> NM_URNA_CANDIDATO, direto do registro real ja
    baixado (consulta_cand_2018_BR.parquet)."""
    df = pd.read_parquet(
        pasta_raw / "consulta_cand_2018_BR.parquet",
        columns=["NR_CANDIDATO", "NM_URNA_CANDIDATO", "DS_CARGO", "SG_UF"],
    )
    df["_cargo_norm"] = df["DS_CARGO"].str.upper().str.strip()
    df = df.drop_duplicates(subset=["SG_UF", "_cargo_norm", "NR_CANDIDATO"])
    return df.set_index(["SG_UF", "_cargo_norm", "NR_CANDIDATO"])["NM_URNA_CANDIDATO"]


def converter_uf(client: bigquery.Client, uf: str, mun_lookup: pd.Series, cand_lookup: pd.Series, destino: Path) -> int:
    cargos_sql = ", ".join(f"'{c.lower()}'" for c in _CARGOS_2018)
    query = f"""
        SELECT sigla_uf, id_municipio_tse, zona, secao, turno, cargo, numero_candidato, votos
        FROM `basedosdados.br_tse_eleicoes.resultados_candidato_secao`
        WHERE ano = 2018 AND sigla_uf = '{uf}' AND LOWER(cargo) IN ({cargos_sql})
    """
    df = client.query(query).result().to_dataframe()
    if df.empty:
        return 0

    df["NR_VOTAVEL"] = df["numero_candidato"].astype("int64")
    df["CD_MUNICIPIO"] = df["id_municipio_tse"].astype("int64")
    df["NR_ZONA"] = df["zona"].astype("int64")
    df["NR_SECAO"] = df["secao"].astype("int64")
    df["NR_TURNO"] = df["turno"].astype("int64")
    df["QT_VOTOS"] = df["votos"].astype("int64")
    df["ANO_ELEICAO"] = 2018
    df["DS_CARGO"] = df["cargo"].str.title()
    df["_cargo_norm"] = df["cargo"].str.upper().str.strip()

    df["NM_MUNICIPIO"] = df["CD_MUNICIPIO"].map(mun_lookup)
    chave_cand = list(zip(df["sigla_uf"], df["_cargo_norm"], df["NR_VOTAVEL"]))
    df["NM_VOTAVEL"] = [cand_lookup.get(k, "NOME NAO ENCONTRADO NO REGISTRO 2018") for k in chave_cand]
    # NR_SECAO como NR_LOCAL_VOTACAO sintetico - ver nota metodologica no
    # topo do arquivo (consistente com a fonte de coordenadas, tambem por
    # secao).
    df["NR_LOCAL_VOTACAO"] = df["NR_SECAO"]
    df["NM_LOCAL_VOTACAO"] = (
        "Secao " + df["NR_SECAO"].astype(str) + " (2018 - sem nome de local, so coordenada por secao)"
    )

    colunas = [
        "NR_VOTAVEL", "NM_VOTAVEL", "DS_CARGO", "CD_MUNICIPIO", "NM_MUNICIPIO",
        "ANO_ELEICAO", "NR_TURNO", "NR_ZONA", "NR_SECAO", "NR_LOCAL_VOTACAO",
        "NM_LOCAL_VOTACAO", "QT_VOTOS",
    ]
    saida = df[colunas].copy()
    saida["NM_MUNICIPIO"] = saida["NM_MUNICIPIO"].fillna("MUNICIPIO NAO ENCONTRADO")
    saida.to_parquet(destino, compression="zstd", index=False)
    return len(saida)


def main() -> None:
    project = sys.argv[1] if len(sys.argv) > 1 else None
    pasta_raw = Path("data/raw")
    client = bigquery.Client(project=project)

    print("Construindo lookup de municipios (2022 ja baixado localmente)...")
    mun_lookup = _lookup_municipios(pasta_raw)
    print(f"  {len(mun_lookup)} municipios.")

    print("Construindo lookup de candidatos (consulta_cand_2018_BR.parquet)...")
    cand_lookup = _lookup_candidatos(pasta_raw)
    print(f"  {len(cand_lookup)} candidatos.")

    total = 0
    for uf in _UFS:
        destino = pasta_raw / f"votacao_secao_2018_{uf}.parquet"
        n = converter_uf(client, uf, mun_lookup, cand_lookup, destino)
        total += n
        print(f"  {uf}: {n} linhas -> {destino} ({destino.stat().st_size / 1e6:.1f} MB)" if n else f"  {uf}: SEM DADO")

    print(f"OK: {total} linhas no total, {len(_UFS)} arquivos de UF.")


if __name__ == "__main__":
    main()
