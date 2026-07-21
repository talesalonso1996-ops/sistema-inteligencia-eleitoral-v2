"""Perfil do eleitorado por secao (TSE, dataset "Eleitorado Atual") - Fase 5
da V2.

ATENCAO METODOLOGICA (nunca omitir na interface): este arquivo e um
retrato do eleitorado registrado HOJE (o TSE atualiza mensalmente, sem
vinculo com nenhuma eleicao especifica - o proprio arquivo original traz
ANO_ELEICAO=9999 como sentinela de "sem eleicao"). NAO e um retrato
historico na data da eleicao analisada (2022/2024): obitos, novos
registros e mudancas de domicilio alteram a composicao do eleitorado ao
longo do tempo. Qualquer comparacao com o resultado de uma eleicao
passada e uma APROXIMACAO, nunca um "match" exato - documentado em
`LIMITACAO_VINTAGE` para ser exibido explicitamente na interface.

Diferente do Censo IBGE (demographic_analysis.py, por SETOR censitario),
esta fonte e do proprio TSE, por SECAO ELEITORAL (zona+secao) - por isso
vive em modulo proprio, para nao diluir a ressalva de vintage (que nao
existe em nenhuma variavel do Censo) dentro da aba de Demografia."""
from __future__ import annotations

import pandas as pd

from .uf_data_bootstrap import caminho_perfil_eleitor_secao, garantir_perfil_eleitor_secao_uf

LIMITACAO_VINTAGE = (
    "Dado do eleitorado REGISTRADO HOJE (TSE atualiza mensalmente), nao um retrato "
    "historico na data da eleicao analisada - obitos, novos registros e mudancas de "
    "domicilio alteram a composicao do eleitorado ao longo do tempo. A comparacao "
    "com o resultado da eleicao e aproximada, nunca um 'match' exato."
)

_COLUNAS_CONTAGEM = [
    "qt_eleitores_total", "qt_eleitores_jovens", "qt_eleitores_60mais",
    "qt_eleitores_superior", "qt_eleitores_feminino",
]


def _adicionar_percentuais(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    total = out["qt_eleitores_total"].replace(0, pd.NA)
    out["pct_eleitores_jovens"] = (100 * out["qt_eleitores_jovens"] / total).round(2)
    out["pct_eleitores_60mais"] = (100 * out["qt_eleitores_60mais"] / total).round(2)
    out["pct_eleitores_superior"] = (100 * out["qt_eleitores_superior"] / total).round(2)
    out["pct_eleitores_feminino"] = (100 * out["qt_eleitores_feminino"] / total).round(2)
    return out


def carregar_perfil_eleitorado_secao(uf: str) -> pd.DataFrame:
    """Carrega o perfil do eleitorado por secao da UF inteira (baixa e
    converte sob demanda na primeira vez - ver uf_data_bootstrap.py).
    Retorna vazio se a fonte estiver indisponivel (nunca inventa dado)."""
    if not garantir_perfil_eleitor_secao_uf(uf):
        return pd.DataFrame()
    caminho = caminho_perfil_eleitor_secao(uf)
    if not caminho.exists():
        return pd.DataFrame()
    return _adicionar_percentuais(pd.read_parquet(caminho))


def perfil_eleitorado_por_territorio(
    perfil_secao_uf: pd.DataFrame, codigo_municipio_tse: int | None, nivel: str
) -> pd.DataFrame:
    """Agrega o perfil do eleitorado (carregado para a UF inteira) para o
    nivel territorial pedido - 'CD_MUNICIPIO' (cargos estaduais, UF
    inteira) ou 'NR_ZONA' (cargos municipais, filtrado para 1 municipio -
    NR_ZONA sozinho so e um identificador seguro dentro de UM municipio ja
    conhecido, mesma ressalva de vote_filtering.secao_composta/
    zona_uf_composta)."""
    if perfil_secao_uf.empty or nivel not in ("CD_MUNICIPIO", "NR_ZONA"):
        return pd.DataFrame()
    df = perfil_secao_uf
    if codigo_municipio_tse is not None:
        df = df[df["CD_MUNICIPIO"] == codigo_municipio_tse]
    if df.empty:
        return pd.DataFrame()
    agregado = df.groupby(nivel, as_index=False)[_COLUNAS_CONTAGEM].sum()
    return _adicionar_percentuais(agregado)


def comparar_eleitorado_vs_votos_candidato(
    perfil_territorio: pd.DataFrame, terr_candidato: pd.DataFrame, nivel: str
) -> pd.DataFrame:
    """Tabela direta: perfil do eleitorado (hoje) vs. onde o candidato
    realmente vota bem (pct_votos_validos_territorio, ja calculado em
    desempenho_territorial) - mesmo nivel territorial dos dois lados."""
    if perfil_territorio.empty or terr_candidato.empty or nivel not in terr_candidato.columns:
        return pd.DataFrame()
    colunas_candidato = [nivel, "votos_candidato", "pct_votos_validos_territorio"]
    colunas_candidato = [c for c in colunas_candidato if c in terr_candidato.columns]
    return terr_candidato[colunas_candidato].merge(perfil_territorio, on=nivel, how="left")
