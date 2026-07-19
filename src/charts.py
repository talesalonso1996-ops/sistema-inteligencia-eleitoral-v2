"""Graficos (Plotly) do sistema (secao 13 do briefing).

Paleta fixa e consistente em todos os graficos: ordem categorica nunca
ciclada (mesma cor sempre no mesmo papel), sequencial de um so tom (azul)
para magnitude, divergente azul<->vermelho para polaridade (acima/abaixo
da media, correlacao positiva/negativa, delta contra rivais), e cores de
status reservadas para as duas classificacoes do produto (indice de
performance territorial e situacao de disputa) - nunca usadas para series
categoricas comuns.

Tema visual: dashboard escuro ("war room"), mesma paleta usada no
`.streamlit/config.toml` e no CSS injetado por `app.py`.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Paleta categorica fixa (ordem nunca ciclada - mesmo papel = mesma cor).
CATEGORICA = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"]
SEQUENCIAL_AZUL = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95"]
DIVERGENTE = ["#e34948", "#3a3f47", "#2a78d6"]  # vermelho - neutro (cinza escuro) - azul

# Status do indice de performance territorial (0-100, ver potential_index.py)
STATUS = {
    "fortaleza": "#0ca30c",
    "consolidado": "#1baf7a",
    "competitivo": "#eda100",
    "crescimento": "#ec835a",
    "baixa_penetracao": "#d03b3b",
}
# Status da classificacao de disputa por territorio (ver competitor_analysis.zonas_de_disputa)
STATUS_DISPUTA = {
    "dominio_absoluto": "#0ca30c",
    "dominio": "#1baf7a",
    "disputa_acirrada": "#eda100",
    "desvantagem": "#d03b3b",
    "sem_votos_no_territorio": "#5b6270",
}
COR_CANDIDATO = "#2a78d6"
COR_CONCORRENTE = "#8a92a3"

# Superficie escura do dashboard - mesmos valores do .streamlit/config.toml
_FUNDO_CARD = "#161b22"
_COR_TEXTO = "#e6e6e6"
_COR_GRID = "#2a3038"

_LAYOUT_BASE = dict(
    template="plotly_dark",
    paper_bgcolor=_FUNDO_CARD,
    plot_bgcolor=_FUNDO_CARD,
    font=dict(family="Inter, system-ui, -apple-system, 'Segoe UI', sans-serif", size=13, color=_COR_TEXTO),
    margin=dict(l=60, r=30, t=50, b=50),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    xaxis=dict(gridcolor=_COR_GRID, zerolinecolor=_COR_GRID),
    yaxis=dict(gridcolor=_COR_GRID, zerolinecolor=_COR_GRID),
)

# Layout claro usado apenas para os graficos embutidos no PDF (impressao)
_LAYOUT_CLARO = dict(
    template="plotly_white",
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=dict(family="Inter, system-ui, -apple-system, 'Segoe UI', sans-serif", size=13, color="#0b0b0b"),
    margin=dict(l=60, r=30, t=50, b=50),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)


def _aplicar_layout(fig: go.Figure, titulo: str, altura: int = 420) -> go.Figure:
    fig.update_layout(title=titulo, height=altura, **_LAYOUT_BASE)
    return fig


def figura_para_impressao(fig: go.Figure) -> go.Figure:
    """Clona a figura e forca fundo claro - usada apenas para o PDF/relatorio
    impresso, onde um grafico com fundo escuro fica ilegivel."""
    clone = go.Figure(fig)
    clone.update_layout(**_LAYOUT_CLARO)
    return clone


def grafico_ranking_disputa(ranking: pd.DataFrame, numero_candidato: int, top_n: int = 20) -> go.Figure:
    """Barras horizontais com os top N candidatos da disputa, destacando o
    candidato analisado em cor diferente dos demais."""
    top = ranking.head(top_n).copy().iloc[::-1]
    cores = [COR_CANDIDATO if n == numero_candidato else COR_CONCORRENTE for n in top["NR_VOTAVEL"]]
    fig = go.Figure(go.Bar(
        x=top["total_votos"], y=top["nome_urna"], orientation="h", marker_color=cores,
        text=top["total_votos"], texttemplate="%{text:,}", textposition="outside",
    ))
    return _aplicar_layout(fig, f"Top {top_n} candidatos - votos totais", altura=max(400, top_n * 24))


def grafico_votos_por_territorio(territorial: pd.DataFrame, coluna_territorio: str, top_n: int = 25) -> go.Figure:
    """Barras dos votos do candidato por territorio (zona/secao/bairro)."""
    top = territorial.nlargest(top_n, "votos_candidato").iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top["votos_candidato"], y=top[coluna_territorio].astype(str), orientation="h",
        marker_color=COR_CANDIDATO,
    ))
    return _aplicar_layout(fig, f"Votos por {coluna_territorio} (top {top_n})", altura=max(400, top_n * 22))


def grafico_comparativo_concorrentes(matriz: pd.DataFrame, coluna_territorio: str) -> go.Figure:
    """Barras agrupadas comparando o candidato aos principais concorrentes,
    territorio a territorio (usa matriz_candidato_territorio)."""
    candidatos = [c for c in matriz.columns if c != coluna_territorio]
    fig = go.Figure()
    for i, nome in enumerate(candidatos):
        fig.add_trace(go.Bar(
            x=matriz[coluna_territorio].astype(str), y=matriz[nome], name=str(nome),
            marker_color=CATEGORICA[i % len(CATEGORICA)],
        ))
    fig.update_layout(barmode="group")
    return _aplicar_layout(fig, "Comparativo com concorrentes por territorio")


def grafico_delta_rivais(delta_df: pd.DataFrame, coluna_territorio: str) -> go.Figure:
    """Barras divergentes: delta de votos (candidato - rival) por
    territorio, para cada rival. Azul = candidato a frente, vermelho =
    rival a frente - usa a paleta DIVERGENTE."""
    fig = go.Figure()
    rivais = delta_df["rival"].unique()
    for i, rival in enumerate(rivais):
        subset = delta_df[delta_df["rival"] == rival].sort_values(coluna_territorio)
        cores = [DIVERGENTE[2] if v >= 0 else DIVERGENTE[0] for v in subset["delta"]]
        fig.add_trace(go.Bar(
            x=subset[coluna_territorio].astype(str), y=subset["delta"], name=str(rival),
            marker_color=cores, visible=(i == 0),
        ))
    botoes = [
        dict(
            label=str(rival), method="update",
            args=[{"visible": [j == i for j in range(len(rivais))]}, {"title": f"Delta de votos vs. {rival}"}],
        )
        for i, rival in enumerate(rivais)
    ]
    fig.update_layout(updatemenus=[dict(buttons=botoes, x=1.0, xanchor="right", y=1.15, yanchor="top")])
    fig.add_hline(y=0, line_color="#5b6270")
    return _aplicar_layout(fig, f"Delta de votos vs. {rivais[0]}" if len(rivais) else "Delta de votos vs. rivais")


def grafico_rivais_similaridade(rivais_similares: pd.DataFrame) -> go.Figure:
    """Barras horizontais com a correlacao de base eleitoral de cada um
    dos rivais mais parecidos (tom sequencial unico - azul)."""
    df = rivais_similares.sort_values("correlacao_base_eleitoral")
    n = len(df)
    cores = [SEQUENCIAL_AZUL[min(int(i / max(n - 1, 1) * (len(SEQUENCIAL_AZUL) - 1)), len(SEQUENCIAL_AZUL) - 1)] for i in range(n)]
    fig = go.Figure(go.Bar(
        x=df["correlacao_base_eleitoral"], y=df["nome_urna"], orientation="h", marker_color=cores,
        text=df["correlacao_base_eleitoral"], texttemplate="%{text:.2f}", textposition="outside",
    ))
    return _aplicar_layout(fig, "Rivais com base eleitoral mais parecida (correlacao)", altura=max(280, n * 60))


def grafico_indice_concentracao(hhi: float) -> go.Figure:
    """Indicador tipo gauge para o indice de concentracao territorial (HHI)."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=hhi * 100,
        number={"suffix": "%"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": COR_CANDIDATO},
            "bgcolor": _FUNDO_CARD,
            "steps": [
                {"range": [0, 15], "color": SEQUENCIAL_AZUL[0]},
                {"range": [15, 40], "color": SEQUENCIAL_AZUL[2]},
                {"range": [40, 100], "color": SEQUENCIAL_AZUL[4]},
            ],
        },
    ))
    return _aplicar_layout(fig, "Concentracao territorial dos votos (HHI)", altura=280)


def grafico_curva_lorenz(curva_lorenz: pd.DataFrame) -> go.Figure:
    """Curva de Lorenz da concentracao do voto entre municipios da UF (V2,
    cargos estaduais) - reta diagonal = distribuicao perfeitamente
    igualitaria; quanto mais a curva se afasta dela, mais concentrado."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=curva_lorenz["pct_municipios_acumulado"], y=curva_lorenz["pct_votos_acumulado"],
        mode="lines", line=dict(color=COR_CANDIDATO, width=3), name="Curva de Lorenz",
    ))
    fig.add_trace(go.Scatter(
        x=[0, 100], y=[0, 100], mode="lines",
        line=dict(color="#5b6270", width=1, dash="dash"), name="Igualdade perfeita",
    ))
    fig.update_xaxes(title="% de municipios (acumulado)")
    fig.update_yaxes(title="% de votos (acumulado)")
    return _aplicar_layout(fig, "Concentracao do voto entre municipios (curva de Lorenz)")


def grafico_correlacoes(correlacoes: pd.DataFrame) -> go.Figure:
    """Barras horizontais divergentes (azul<->vermelho) para o coeficiente
    de correlacao de cada variavel demografica com os votos."""
    df = correlacoes.sort_values("correlacao")
    cores = [DIVERGENTE[0] if v < 0 else DIVERGENTE[2] for v in df["correlacao"]]
    fig = go.Figure(go.Bar(
        x=df["correlacao"], y=df["variavel"], orientation="h", marker_color=cores,
        text=df["correlacao"], texttemplate="%{text:.2f}", textposition="outside",
    ))
    fig.add_vline(x=0, line_color="#5b6270")
    return _aplicar_layout(fig, "Correlacao com o desempenho eleitoral", altura=max(300, len(df) * 40))


def grafico_dispersao_correlacao(df: pd.DataFrame, coluna_votos: str, variavel: str) -> go.Figure:
    """Dispersao votos x variavel demografica, com linha de tendencia
    (regressao linear simples) - detalha uma correlacao especifica."""
    fig = px.scatter(
        df, x=variavel, y=coluna_votos, trendline="ols",
        color_discrete_sequence=[COR_CANDIDATO],
    )
    fig.update_traces(marker=dict(size=9, opacity=0.75))
    return _aplicar_layout(fig, f"{coluna_votos} vs. {variavel}")


def grafico_clusters(resultado_clustering: pd.DataFrame, eixo_x: str, eixo_y: str, rotulo: str) -> go.Figure:
    """Dispersao dos territorios coloridos por cluster (paleta categorica
    fixa, identidade nunca so por cor - rotulo tambem aparece no hover)."""
    fig = px.scatter(
        resultado_clustering, x=eixo_x, y=eixo_y, color="cluster",
        hover_name=rotulo if rotulo in resultado_clustering.columns else None,
        color_discrete_sequence=CATEGORICA,
    )
    fig.update_traces(marker=dict(size=11, opacity=0.85, line=dict(width=1, color=_FUNDO_CARD)))
    return _aplicar_layout(fig, "Segmentacao de territorios (clusters)")


def grafico_perfil_clusters(perfil_clusters: pd.DataFrame, variaveis: list[str]) -> go.Figure:
    """Barras agrupadas comparando a media de cada variavel entre clusters."""
    fig = go.Figure()
    for i, var in enumerate(variaveis):
        if var not in perfil_clusters.columns:
            continue
        fig.add_trace(go.Bar(
            x=perfil_clusters["cluster"].astype(str), y=perfil_clusters[var], name=var,
            marker_color=CATEGORICA[i % len(CATEGORICA)],
        ))
    fig.update_layout(barmode="group")
    return _aplicar_layout(fig, "Perfil medio por cluster")


def grafico_distribuicao_indice(territorial_com_indice: pd.DataFrame) -> go.Figure:
    """Contagem de territorios por classificacao do indice de performance,
    usando a paleta de status (cores reservadas, nunca usadas para series)."""
    contagem = territorial_com_indice["classificacao"].value_counts()
    ordem = ["fortaleza", "consolidado", "competitivo", "crescimento", "baixa_penetracao"]
    contagem = contagem.reindex(ordem).fillna(0)
    fig = go.Figure(go.Bar(
        x=contagem.index, y=contagem.values,
        marker_color=[STATUS[c] for c in contagem.index],
    ))
    return _aplicar_layout(fig, "Territorios por classificacao do indice de performance", altura=380)


def grafico_ranking_partidos(ranking_partidos: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """Barras dos partidos com mais votos na disputa."""
    top = ranking_partidos.head(top_n).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top["votos_totais"], y=top["partido_sigla"], orientation="h",
        marker_color=COR_CANDIDATO,
    ))
    return _aplicar_layout(fig, f"Top {top_n} partidos por votos na disputa")


def grafico_votos_por_bairro(bairros_agg: pd.DataFrame, top_n: int = 15) -> go.Figure:
    """Barras horizontais dos bairros/distritos com mais votos do
    candidato."""
    top = bairros_agg.nlargest(top_n, "votos_candidato").iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top["votos_candidato"], y=top["bairro"], orientation="h",
        marker_color=COR_CANDIDATO,
    ))
    return _aplicar_layout(fig, f"Top {top_n} bairros/distritos - votos do candidato", altura=max(400, top_n * 26))


def grafico_zonas_disputa(territorial_classificado: pd.DataFrame, coluna_territorio: str) -> go.Figure:
    """Barras coloridas pela situacao (dominio/disputa acirrada/desvantagem)
    - paleta de status (STATUS_DISPUTA), identidade reforcada por texto na
    legenda."""
    fig = go.Figure()
    for situacao, cor in STATUS_DISPUTA.items():
        subset = territorial_classificado[territorial_classificado["situacao"] == situacao]
        if subset.empty:
            continue
        fig.add_trace(go.Bar(
            x=subset[coluna_territorio].astype(str), y=subset["votos_candidato"],
            name=situacao.replace("_", " "), marker_color=cor,
        ))
    return _aplicar_layout(fig, "Classificacao de disputa por territorio")


def grafico_bairros_potencial(bairros_potencial: pd.DataFrame, coluna_territorio: str) -> go.Figure:
    """Barras horizontais dos territorios com maior score de potencial de
    crescimento (tom sequencial unico - azul, mais escuro = maior potencial)."""
    df = bairros_potencial.sort_values("score_potencial").iloc[::-1]
    n = len(df)
    cores = [
        SEQUENCIAL_AZUL[min(int(i / max(n - 1, 1) * (len(SEQUENCIAL_AZUL) - 1)), len(SEQUENCIAL_AZUL) - 1)]
        for i in range(n)
    ][::-1]
    fig = go.Figure(go.Bar(
        x=df["score_potencial"], y=df[coluna_territorio].astype(str), orientation="h",
        marker_color=cores, text=df["score_potencial"], texttemplate="%{text:.0f}", textposition="outside",
    ))
    return _aplicar_layout(fig, "Territorios com maior potencial de crescimento", altura=max(350, n * 32))


def grafico_perfil_economico_municipio(perfil) -> go.Figure:
    """Admissoes x desligamentos formais do municipio em 2024 (CAGED) -
    contexto economico do municipio (nivel municipal, nao territorial -
    ver limitacoes em economic_analysis.PerfilEconomicoMunicipio)."""
    cores_tendencia = {"crescimento": "#0ca30c", "estavel": "#eda100", "retracao": "#d03b3b"}
    cor = cores_tendencia.get(perfil.tendencia, "#8a92a3")
    fig = go.Figure(go.Bar(
        x=["Admissoes 2024", "Desligamentos 2024"],
        y=[perfil.admissoes_2024, perfil.desligamentos_2024],
        marker_color=[COR_CANDIDATO, "#5b6270"],
        text=[perfil.admissoes_2024, perfil.desligamentos_2024], textposition="outside",
    ))
    fig.add_annotation(
        text=f"Saldo: {perfil.saldo_caged_2024:+,}".replace(",", ".") + f" ({perfil.tendencia})",
        x=0.5, y=1.12, xref="paper", yref="paper", showarrow=False,
        font=dict(color=cor, size=14),
    )
    return _aplicar_layout(fig, "Movimentacao de empregos formais (CAGED, municipio, 2024)", altura=380)


def grafico_pizza_votos_validos(rg) -> go.Figure:
    """Pizza simples: participacao do candidato nos votos validos da
    disputa vs. o restante."""
    fig = go.Figure(go.Pie(
        labels=["Candidato", "Demais candidatos"],
        values=[rg.total_votos, rg.votos_validos_disputa - rg.total_votos],
        marker_colors=[COR_CANDIDATO, "#3a3f47"],
        hole=0.55,
    ))
    return _aplicar_layout(fig, "Participacao nos votos validos da disputa", altura=350)


def grafico_piramide_maslow(
    tiers_mapeados: pd.DataFrame, tiers_sem_proxy: pd.DataFrame, ordem_tiers: list[str]
) -> go.Figure:
    """Barras horizontais na ordem hierarquica de Maslow (base embaixo,
    topo em cima): comprimento = magnitude do efeito ja calculado
    (log-odds/coeficiente/correlacao), cor = polaridade (paleta DIVERGENTE
    - azul aumenta a chance/votos, vermelho reduz, mesma convencao de
    grafico_correlacoes). Niveis sem proxy disponivel viram uma barra
    cinza hachurada de tamanho fixo pequeno + anotacao textual - NUNCA um
    numero inventado."""
    labels_por_tier: dict[str, str] = {}
    if not tiers_mapeados.empty:
        for tier_key, grupo in tiers_mapeados.dropna(subset=["tier"]).groupby("tier"):
            labels_por_tier[tier_key] = grupo["label"].iloc[0]
    for _, row in tiers_sem_proxy.iterrows():
        labels_por_tier.setdefault(row["tier"], row["label"])

    mapeadas = tiers_mapeados[tiers_mapeados["status"] == "mapeado"] if not tiers_mapeados.empty else tiers_mapeados
    magnitude_maxima = float(mapeadas["magnitude"].max()) if not mapeadas.empty else 1.0
    stub = max(magnitude_maxima * 0.15, 0.05)

    fig = go.Figure()
    for tier_key in reversed(ordem_tiers):
        label = labels_por_tier.get(tier_key, tier_key)
        subset = mapeadas[mapeadas["tier"] == tier_key] if not mapeadas.empty else mapeadas

        if subset is not None and not subset.empty:
            valor_medio = float(subset["valor_efeito"].mean())
            aumenta = valor_medio > 1 if (subset["tipo_efeito"] == "odds_ratio").all() else valor_medio > 0
            cor = DIVERGENTE[2] if aumenta else DIVERGENTE[0]
            fig.add_trace(go.Bar(
                x=[float(subset["magnitude"].mean())], y=[label], orientation="h",
                marker_color=cor, text=[", ".join(subset["variavel"])], textposition="outside",
                showlegend=False,
            ))
        else:
            fig.add_trace(go.Bar(
                x=[stub], y=[label], orientation="h", showlegend=False,
                marker=dict(color="rgba(0,0,0,0)", pattern=dict(shape="/", fgcolor="#5b6270"),
                            line=dict(color="#5b6270", width=1)),
            ))
            fig.add_annotation(
                x=stub * 1.15, y=label, text="sem proxy disponivel", showarrow=False,
                xanchor="left", font=dict(color="#8a92a3", size=11),
            )

    fig.update_layout(yaxis=dict(categoryorder="array", categoryarray=[labels_por_tier.get(t, t) for t in reversed(ordem_tiers)]))
    return _aplicar_layout(fig, "Piramide de Maslow - proxies demograficos e efeito estimado", altura=420)
