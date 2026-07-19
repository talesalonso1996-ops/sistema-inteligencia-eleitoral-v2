"""Indicadores territoriais para cargos de abrangencia ESTADUAL/DISTRITAL
(Governador, Senador, Deputado Federal/Estadual/Distrital) - V2. Aplicados
no nivel de MUNICIPIO dentro da UF, complementando (sem substituir) os
indicadores ja existentes para cargos municipais
(electoral_metrics.desempenho_territorial/indice_concentracao_hhi,
potential_index.calcular_indice_performance), que continuam identicos e
sao a base tecnica reaproveitada aqui (HHI, normalizacao 0-100, pesos
configuraveis).

Metodologia (limitacao documentada, nunca escondida): o "universo de
municipios da UF" e aproximado pelo conjunto de municipios com pelo menos
1 voto registrado NA DISPUTA COMPLETA (votos_disputa, todos os candidatos)
- para um cargo estadual, o voto e obrigatorio e universal, entao esse
conjunto coincide, na pratica, com a totalidade de municipios da UF (a
excecao teorica - um municipio sem nenhum voto para nenhum candidato dessa
disputa - e virtualmente inexistente e seria, de qualquer forma, um
municipio sem urnas instaladas, nao um erro de calculo)."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .electoral_metrics import indice_concentracao_hhi
from .utils import get_logger, indicators_config

logger = get_logger(__name__)


@dataclass
class PresencaEleitoral:
    n_municipios_com_votos: int
    n_municipios_universo: int
    pct_cobertura: float
    municipios_sem_votos: list[str]
    n_municipios_acima_media: int
    municipio_maior_votacao_absoluta: str
    votos_municipio_maior_votacao_absoluta: int
    municipio_maior_votacao_proporcional: str
    pct_municipio_maior_votacao_proporcional: float
    participacao_top5_pct: float
    participacao_top10_pct: float
    participacao_top20_pct: float


@dataclass
class ConcentracaoTerritorial:
    dependencia_maior_municipio_pct: float
    dependencia_top5_pct: float
    dependencia_top10_pct: float
    gini: float
    hhi: float
    curva_lorenz: pd.DataFrame  # colunas: pct_municipios_acumulado, pct_votos_acumulado


def calcular_presenca_eleitoral(
    territorial_municipio: pd.DataFrame,
    votos_disputa: pd.DataFrame,
    coluna_municipio: str = "CD_MUNICIPIO",
    coluna_municipio_nome: str = "NM_MUNICIPIO",
    coluna_votos: str = "votos_candidato",
) -> PresencaEleitoral:
    """`territorial_municipio`: saida de
    electoral_metrics.desempenho_territorial(..., nivel='CD_MUNICIPIO'),
    ja com `coluna_municipio_nome` mesclado (uma linha por municipio ONDE O
    CANDIDATO TEVE VOTO). `votos_disputa`: dataframe bruto da disputa
    completa (mesmo que alimenta desempenho_territorial/ranking_disputa),
    usado so para descobrir o universo de municipios da UF (ver
    metodologia no docstring do modulo)."""
    df = territorial_municipio.sort_values(coluna_votos, ascending=False).reset_index(drop=True)
    total_votos = float(df[coluna_votos].sum())

    universo = votos_disputa[[coluna_municipio, coluna_municipio_nome]].drop_duplicates()
    com_votos = set(df[coluna_municipio])
    todos = set(universo[coluna_municipio])
    nomes_sem_votos = sorted(
        universo[universo[coluna_municipio].isin(todos - com_votos)][coluna_municipio_nome].tolist()
    )

    media = df[coluna_votos].mean() if len(df) else 0.0
    n_acima_media = int((df[coluna_votos] > media).sum())

    linha_top_abs = df.iloc[0] if len(df) else None
    if "pct_votos_validos_territorio" in df.columns and len(df):
        linha_top_pct = df.sort_values("pct_votos_validos_territorio", ascending=False).iloc[0]
    else:
        linha_top_pct = linha_top_abs

    def _participacao_top_n(n: int) -> float:
        if not total_votos:
            return 0.0
        return round(100 * df.head(n)[coluna_votos].sum() / total_votos, 2)

    return PresencaEleitoral(
        n_municipios_com_votos=len(com_votos),
        n_municipios_universo=len(todos),
        pct_cobertura=round(100 * len(com_votos) / len(todos), 2) if todos else 0.0,
        municipios_sem_votos=nomes_sem_votos,
        n_municipios_acima_media=n_acima_media,
        municipio_maior_votacao_absoluta=str(linha_top_abs[coluna_municipio_nome]) if linha_top_abs is not None else "",
        votos_municipio_maior_votacao_absoluta=int(linha_top_abs[coluna_votos]) if linha_top_abs is not None else 0,
        municipio_maior_votacao_proporcional=str(linha_top_pct[coluna_municipio_nome]) if linha_top_pct is not None else "",
        pct_municipio_maior_votacao_proporcional=(
            round(float(linha_top_pct["pct_votos_validos_territorio"]), 2)
            if linha_top_pct is not None and "pct_votos_validos_territorio" in df.columns else 0.0
        ),
        participacao_top5_pct=_participacao_top_n(5),
        participacao_top10_pct=_participacao_top_n(10),
        participacao_top20_pct=_participacao_top_n(20),
    )


def _gini(valores: pd.Series) -> float:
    """Coeficiente de Gini classico (0 = distribuicao perfeitamente
    igualitaria entre municipios, 1 = toda a votacao concentrada em um
    unico municipio)."""
    x = valores.sort_values().to_numpy(dtype=float)
    n = len(x)
    if n == 0 or x.sum() == 0:
        return 0.0
    cum = x.cumsum()
    return round(float((n + 1 - 2 * (cum.sum() / cum[-1])) / n), 4)


def _curva_lorenz(valores: pd.Series) -> pd.DataFrame:
    x = valores.sort_values().to_numpy(dtype=float)
    n = len(x)
    if n == 0 or x.sum() == 0:
        return pd.DataFrame({"pct_municipios_acumulado": [], "pct_votos_acumulado": []})
    cum_votos = x.cumsum() / x.sum() * 100
    pct_municipios = [(i + 1) / n * 100 for i in range(n)]
    return pd.DataFrame({
        "pct_municipios_acumulado": [0.0] + pct_municipios,
        "pct_votos_acumulado": [0.0] + list(cum_votos),
    })


def calcular_concentracao_territorial(
    territorial_municipio: pd.DataFrame, coluna_votos: str = "votos_candidato",
) -> ConcentracaoTerritorial:
    """Concentracao da votacao do candidato entre os municipios da UF onde
    teve voto - reaproveita indice_concentracao_hhi (electoral_metrics.py),
    ja validado para o nivel municipal (mesma formula, so muda o nivel de
    agregacao do dataframe de entrada)."""
    df = territorial_municipio.sort_values(coluna_votos, ascending=False).reset_index(drop=True)
    total = float(df[coluna_votos].sum())

    def _dependencia_top_n(n: int) -> float:
        if not total:
            return 0.0
        return round(100 * df.head(n)[coluna_votos].sum() / total, 2)

    return ConcentracaoTerritorial(
        dependencia_maior_municipio_pct=_dependencia_top_n(1),
        dependencia_top5_pct=_dependencia_top_n(5),
        dependencia_top10_pct=_dependencia_top_n(10),
        gini=_gini(df[coluna_votos]),
        hhi=indice_concentracao_hhi(df, coluna_votos=coluna_votos),
        curva_lorenz=_curva_lorenz(df[coluna_votos]),
    )


def _normalizar_0_100_valor(valor: float, minimo: float, maximo: float) -> float:
    """Normaliza um unico valor escalar (nao uma serie por territorio, como
    em potential_index._normalizar_0_100) para 0-100, dado um minimo/maximo
    teorico conhecido - usado aqui porque os indicadores de presenca/
    concentracao sao UM valor por candidato, nao um valor por territorio."""
    if maximo == minimo:
        return 50.0
    return max(0.0, min(100.0, 100 * (valor - minimo) / (maximo - minimo)))


def calcular_indice_capilaridade(
    presenca: PresencaEleitoral, concentracao: ConcentracaoTerritorial,
) -> tuple[float, str]:
    """Indice de capilaridade eleitoral (0-100): quanto mais alto, mais
    pulverizada/capilarizada e a base de votos do candidato entre os
    municipios da UF (baixa dependencia de poucos redutos, boa cobertura
    territorial) - o oposto de uma base concentrada em poucos municipios.
    Pesos configuraveis em config/indicators.yaml: indice_capilaridade.

    LIMITACAO METODOLOGICA (documentada, nao escondida): mede so
    cobertura/concentracao entre municipios - NAO inclui uma dimensao de
    "distribuicao entre regioes/mesorregioes do estado" por falta de um
    mapeamento oficial de mesorregiao por municipio integrado a esta base
    (gap, nao preenchido com dado nao verificado)."""
    cfg = indicators_config()["indice_capilaridade"]
    pesos = dict(cfg["pesos"])

    componente_cobertura = _normalizar_0_100_valor(presenca.pct_cobertura, 0, 100)
    componente_baixa_concentracao_hhi = _normalizar_0_100_valor(1 - concentracao.hhi, 0, 1)
    componente_baixa_dependencia_top5 = _normalizar_0_100_valor(100 - concentracao.dependencia_top5_pct, 0, 100)

    componentes = {
        "cobertura_municipios": componente_cobertura,
        "baixa_concentracao_hhi": componente_baixa_concentracao_hhi,
        "baixa_dependencia_top5": componente_baixa_dependencia_top5,
    }
    soma_pesos = sum(pesos.values())
    indice = sum(componentes[nome] * (peso / soma_pesos) for nome, peso in pesos.items() if soma_pesos)
    indice = round(max(0.0, min(100.0, indice)), 1)

    limites = cfg["limites_classificacao"]
    ordenado = sorted(limites.items(), key=lambda kv: kv[1], reverse=True)
    classificacao = next((nome for nome, minimo in ordenado if indice >= minimo), ordenado[-1][0])
    return indice, classificacao
