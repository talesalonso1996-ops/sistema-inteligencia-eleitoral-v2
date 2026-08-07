"""Constroi coordenadas_secao_2018_{UF}.parquet - latitude/longitude reais
por (municipio TSE, zona, secao) para 2018, a partir da tabela local_secao
do dataset publico br_tse_eleicoes (Base dos Dados/BigQuery).

Diferente de votacao_secao (que identifica o LOCAL DE VOTACAO - o predio
fisico, varias secoes por predio), local_secao da' coordenada por SECAO
diretamente - por isso este arquivo tem uma granularidade mais fina que
NR_LOCAL_VOTACAO, mas essa e' a unica coordenada real disponivel para 2018
(nao existe fonte "local de votacao 2018" equivalente ao
eleitorado_local_votacao usado para 2022/2024).

id_municipio na tabela local_secao e' o codigo IBGE (7 digitos) - diferente
do codigo TSE (id_municipio_tse) usado no resto deste projeto. Resolvido
com um crosswalk construido a partir de resultados_candidato_secao (que tem
os dois codigos lado a lado), nao um arquivo de referencia externo.

Cobertura real: ~87,5% das secoes de 2018 tem coordenada (melhor_urbano OU
melhor_rural nao nulo) - as demais ficam de fora deste arquivo (nunca
preenchidas com coordenada fabricada)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

_UFS = (
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT",
    "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
)


def _crosswalk_municipio(client: bigquery.Client, uf: str) -> pd.DataFrame:
    """(id_municipio IBGE) -> id_municipio_tse, construido a partir do
    proprio resultados_candidato_secao (que ja traz os dois codigos)."""
    query = f"""
        SELECT DISTINCT id_municipio, id_municipio_tse
        FROM `basedosdados.br_tse_eleicoes.resultados_candidato_secao`
        WHERE ano = 2018 AND sigla_uf = '{uf}'
    """
    return client.query(query).result().to_dataframe()


def converter_uf(client: bigquery.Client, uf: str, destino: Path) -> int:
    crosswalk = _crosswalk_municipio(client, uf)

    query = f"""
        SELECT id_municipio, zona, secao,
               ST_X(COALESCE(melhor_urbano, melhor_rural)) AS longitude,
               ST_Y(COALESCE(melhor_urbano, melhor_rural)) AS latitude
        FROM `basedosdados.br_tse_eleicoes.local_secao`
        WHERE ano = 2018 AND sigla_uf = '{uf}'
          AND COALESCE(melhor_urbano, melhor_rural) IS NOT NULL
    """
    df = client.query(query).result().to_dataframe()
    if df.empty:
        return 0

    df = df.merge(crosswalk, on="id_municipio", how="left")
    sem_municipio = df["id_municipio_tse"].isna().sum()
    df = df.dropna(subset=["id_municipio_tse"])

    saida = pd.DataFrame({
        "CD_MUNICIPIO": df["id_municipio_tse"].astype("int64"),
        "NR_ZONA": df["zona"].astype("int64"),
        "NR_SECAO": df["secao"].astype("int64"),
        "latitude": df["latitude"].astype("float64"),
        "longitude": df["longitude"].astype("float64"),
    })
    # coordenadas reais mas fora do Brasil (erro de geocodificacao na fonte)
    # - mesmo filtro ja usado em geographic_analysis.carregar_coordenadas_locais.
    saida = saida[saida["latitude"].between(-34, 6) & saida["longitude"].between(-74, -28)]
    saida.to_parquet(destino, compression="zstd", index=False)
    if sem_municipio:
        print(f"    aviso: {sem_municipio} linhas sem municipio_tse correspondente (descartadas)")
    return len(saida)


def main() -> None:
    project = sys.argv[1] if len(sys.argv) > 1 else None
    pasta_raw = Path("data/raw")
    client = bigquery.Client(project=project)

    total = 0
    for uf in _UFS:
        destino = pasta_raw / f"coordenadas_secao_2018_{uf}.parquet"
        n = converter_uf(client, uf, destino)
        total += n
        print(f"  {uf}: {n} linhas -> {destino}" if n else f"  {uf}: SEM DADO")

    print(f"OK: {total} linhas no total, {len(_UFS)} arquivos de UF.")


if __name__ == "__main__":
    main()
