"""Indice de Performance Eleitoral Territorial (0-100) - secao 11 do
briefing.

Combina, por territorio, seis componentes normalizados (0-100) com pesos
configuraveis em config/indicators.yaml. Cada componente e normalizado por
min-max DENTRO da distribuicao dos proprios territorios do candidato -
ou seja, o indice mede forca RELATIVA entre os territorios do candidato,
nao dominio eleitoral absoluto (um candidato com poucos votos no total
ainda tera territorios classificados como "fortaleza" relativa dele
mesmo). Essa escolha metodologica e deliberada e documentada aqui e no
relatorio final.

Quando um componente nao esta disponivel (ex.: comparecimento sem o
arquivo de detalhe por secao), seu peso e redistribuido proporcionalmente
entre os componentes disponiveis, e a limitacao e registrada no log.
"""
from __future__ import annotations

import pandas as pd

from .utils import get_logger, indicators_config

logger = get_logger(__name__)


def _normalizar_0_100(serie: pd.Series) -> pd.Series:
    """Min-max scaling para 0-100. Serie constante (min==max) vira 50
    (neutro) para todos os territorios, evitando divisao por zero."""
    minimo, maximo = serie.min(), serie.max()
    if pd.isna(minimo) or pd.isna(maximo) or maximo == minimo:
        return pd.Series(50.0, index=serie.index)
    return 100 * (serie - minimo) / (maximo - minimo)


def calcular_indice_performance(
    territorial: pd.DataFrame, hhi_concentracao: float
) -> pd.DataFrame:
    """Calcula o indice de performance (0-100) e a classificacao para cada
    territorio. Espera um dataframe ja enriquecido com:
    pct_votos_validos_territorio, participacao_no_total_candidato,
    desvio_vs_media, margem_pct (de zonas_de_disputa) e, opcionalmente,
    comparecimento/QT_APTOS."""
    cfg = indicators_config()["indice_performance"]
    pesos = dict(cfg["pesos"])
    df = territorial.copy()

    componentes: dict[str, pd.Series] = {}
    componentes["percentual_votos_territorio"] = _normalizar_0_100(df["pct_votos_validos_territorio"])
    componentes["desempenho_vs_media"] = _normalizar_0_100(df["desvio_vs_media"])
    componentes["participacao_no_total_candidato"] = _normalizar_0_100(df["participacao_no_total_candidato"])

    if "margem_pct" in df.columns:
        componentes["distancia_concorrente_principal"] = _normalizar_0_100(df["margem_pct"].fillna(df["margem_pct"].min()))
    else:
        pesos.pop("distancia_concorrente_principal", None)
        logger.warning("Componente 'distancia_concorrente_principal' indisponivel - peso redistribuido.")

    if "comparecimento" in df.columns and df["comparecimento"].notna().any() and "QT_APTOS" in df.columns:
        pct_comparecimento = 100 * df["comparecimento"] / df["QT_APTOS"].replace(0, pd.NA)
        componentes["comparecimento"] = _normalizar_0_100(pct_comparecimento)
    else:
        pesos.pop("comparecimento", None)
        logger.warning("Componente 'comparecimento' indisponivel - peso redistribuido.")

    # Penalidade de concentracao territorial: unica por candidato (HHI),
    # aplicada igualmente a todos os territorios.
    peso_penalidade = pesos.pop("concentracao_territorial_penalidade", 0.0)
    penalidade = hhi_concentracao * 100 * peso_penalidade

    soma_pesos = sum(pesos.values())
    pesos_normalizados = {k: v / soma_pesos for k, v in pesos.items()} if soma_pesos else {}

    indice = pd.Series(0.0, index=df.index)
    for nome, peso in pesos_normalizados.items():
        indice = indice + componentes[nome].fillna(0) * peso
    indice = (indice - penalidade).clip(lower=0, upper=100)

    df["indice_performance"] = indice.round(1)
    limites = cfg["limites_classificacao"]
    df["classificacao"] = df["indice_performance"].apply(lambda v: _classificar(v, limites))
    return df


def _classificar(valor: float, limites: dict[str, int]) -> str:
    ordenado = sorted(limites.items(), key=lambda kv: kv[1], reverse=True)
    for nome, minimo in ordenado:
        if valor >= minimo:
            return nome
    return ordenado[-1][0]
