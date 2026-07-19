"""Segmentacao de territorios por perfil demografico + desempenho
eleitoral (secao 10.3 do briefing), via K-Means.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .data_validation import validar_amostra_minima
from .utils import DataIssue, get_logger, indicators_config

logger = get_logger(__name__)


@dataclass
class ResultadoClustering:
    territorios_com_cluster: pd.DataFrame  # dataframe original + coluna 'cluster'
    perfil_clusters: pd.DataFrame  # media de cada variavel por cluster
    k_escolhido: int
    silhouette: float
    variaveis_utilizadas: list[str]


def _melhor_k(dados_padronizados, k_min: int, k_max: int) -> tuple[int, float]:
    """Escolhe k pelo maior indice de silhueta dentro do intervalo
    configurado (config/indicators.yaml: clustering.k_min/k_max)."""
    melhor_k, melhor_score = k_min, -1.0
    k_max_efetivo = min(k_max, len(dados_padronizados) - 1)
    for k in range(k_min, max(k_max_efetivo, k_min) + 1):
        if k >= len(dados_padronizados):
            break
        labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(dados_padronizados)
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(dados_padronizados, labels)
        if score > melhor_score:
            melhor_k, melhor_score = k, score
    return melhor_k, melhor_score


def segmentar_territorios(
    df: pd.DataFrame, variaveis: list[str], k: int | None = None
) -> tuple[ResultadoClustering | None, list[DataIssue]]:
    """Agrupa territorios por similaridade nas variaveis informadas
    (padronizadas via z-score). Se `k` nao for informado, escolhe
    automaticamente pelo indice de silhueta dentro de k_min/k_max
    (config/indicators.yaml). Se `k` for informado (ex.: k=10, segmentacao
    padrao do produto), e' limitado a no maximo n_territorios-1, com aviso
    quando o cap for aplicado."""
    cfg = indicators_config()["clustering"]
    variaveis_validas = [v for v in variaveis if v in df.columns]
    dados = df[variaveis_validas].dropna()

    issues = validar_amostra_minima(len(dados), max(cfg["k_min"] * 3, 6), "segmentar_territorios")
    if issues or not variaveis_validas:
        return None, issues

    scaler = StandardScaler()
    padronizados = scaler.fit_transform(dados)

    if k is None:
        k, score = _melhor_k(padronizados, cfg["k_min"], cfg["k_max"])
    else:
        k_pedido = k
        k = min(k, len(dados) - 1)
        if k < k_pedido:
            issues.append(
                DataIssue(
                    etapa="segmentar_territorios",
                    severidade="aviso",
                    mensagem=(
                        f"k={k_pedido} solicitado, mas ha apenas {len(dados)} territorios - "
                        f"reduzido para k={k}."
                    ),
                )
            )
        labels_teste = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(padronizados)
        score = silhouette_score(padronizados, labels_teste) if len(set(labels_teste)) > 1 else 0.0

    modelo = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels = modelo.fit_predict(padronizados)

    resultado_df = df.loc[dados.index].copy()
    resultado_df["cluster"] = labels

    perfil = resultado_df.groupby("cluster")[variaveis_validas].mean().round(2)
    perfil["n_territorios"] = resultado_df.groupby("cluster").size()

    return (
        ResultadoClustering(
            territorios_com_cluster=resultado_df,
            perfil_clusters=perfil.reset_index(),
            k_escolhido=k,
            silhouette=round(float(score), 3),
            variaveis_utilizadas=variaveis_validas,
        ),
        issues,
    )


def gerar_narrativa_clusters(
    resultado: ResultadoClustering, coluna_votos: str = "votos_candidato"
) -> pd.DataFrame:
    """Traduz o perfil estatistico de cada cluster em um rotulo de acao e um
    resumo em linguagem natural - a segmentacao so tem valor para uma
    campanha se disser CLARAMENTE onde investir esforco/recurso, nao so
    "cluster 3 tem renda X"."""
    df = resultado.territorios_com_cluster
    variaveis = resultado.variaveis_utilizadas
    perfil = resultado.perfil_clusters.set_index("cluster")

    medias_gerais = df[variaveis].mean()
    desvios_gerais = df[variaveis].std(ddof=0).replace(0, 1)
    votos_medio_geral = df[coluna_votos].mean()

    z_scores = (perfil[variaveis] - medias_gerais) / desvios_gerais
    cluster_mais_forte = perfil[coluna_votos].idxmax() if coluna_votos in perfil.columns else None
    z_cluster_forte = z_scores.loc[cluster_mais_forte] if cluster_mais_forte is not None else None
    distancia_ao_forte = (
        ((z_scores - z_cluster_forte) ** 2).sum(axis=1) ** 0.5
        if z_cluster_forte is not None else pd.Series(0, index=z_scores.index)
    )
    limiar_similaridade = distancia_ao_forte.median() if len(distancia_ao_forte) > 1 else 0.0

    linhas = []
    for cluster_id, linha in perfil.iterrows():
        votos_medio_cluster = float(linha.get(coluna_votos, df.loc[df["cluster"] == cluster_id, coluna_votos].mean()))
        variacao_pct = (
            round(100 * (votos_medio_cluster - votos_medio_geral) / votos_medio_geral, 1)
            if votos_medio_geral else 0.0
        )

        if variacao_pct >= 20:
            rotulo = "Fortaleza"
        elif variacao_pct <= -20:
            parecido_com_forte = (
                cluster_id != cluster_mais_forte and distancia_ao_forte.get(cluster_id, 99) <= limiar_similaridade
            )
            rotulo = "Alto potencial" if parecido_com_forte else "Baixa prioridade"
        else:
            rotulo = "Consolidar"

        z_cluster = z_scores.loc[cluster_id]
        destaques = z_cluster.abs().sort_values(ascending=False).head(2).index.tolist()
        descricao_variaveis = "; ".join(
            f"{var} {'alto' if z_cluster[var] > 0 else 'baixo'} (vs. media geral dos territorios)"
            for var in destaques
        )

        resumo = (
            f"Cluster {cluster_id} ({int(linha['n_territorios'])} territorios): {descricao_variaveis}. "
            f"Votacao do candidato {'{:+.1f}'.format(variacao_pct)}% vs. media geral -> {rotulo}."
        )

        linhas.append({
            "cluster": cluster_id,
            "n_territorios": int(linha["n_territorios"]),
            "rotulo_acao": rotulo,
            "votos_medio": round(votos_medio_cluster, 1),
            "votos_medio_vs_geral_pct": variacao_pct,
            "resumo": resumo,
        })

    return pd.DataFrame(linhas).sort_values("votos_medio", ascending=False).reset_index(drop=True)
