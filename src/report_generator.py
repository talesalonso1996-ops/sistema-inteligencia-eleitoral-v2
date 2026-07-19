"""Geracao do relatorio executivo - HTML (interativo) e PDF (secao 15 do
briefing).

Recebe um dicionario com os resultados ja calculados pelas demais camadas
(nao recalcula nada aqui) e monta os dois formatos de saida.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .candidate_finder import Candidatura
from .charts import figura_para_impressao


@dataclass
class DadosRelatorio:
    candidatura: Candidatura
    resultado_geral: object
    ranking: pd.DataFrame
    territorial_indice: pd.DataFrame
    bairros_agg: pd.DataFrame | None
    correlacoes: pd.DataFrame | None
    limitacoes: list[str] = field(default_factory=list)
    figuras: dict[str, go.Figure] = field(default_factory=dict)
    regressao_logistica: object | None = None  # ResultadoRegressaoLogistica
    clusters_narrativa: pd.DataFrame | None = None
    delta_rivais: pd.DataFrame | None = None
    bairros_potencial: pd.DataFrame | None = None
    rivais_similaridade: pd.DataFrame | None = None
    maslow: object | None = None  # ResultadoMaslow (src/maslow_analysis.py)
    perfil_economico: object | None = None  # PerfilEconomicoMunicipio (src/economic_analysis.py)


def _formatar_numero(valor) -> str:
    if valor is None:
        return "n/d"
    return f"{valor:,.0f}".replace(",", ".")


def gerar_relatorio_html(dados: DadosRelatorio) -> str:
    """Gera o relatorio executivo em HTML autocontido, com graficos
    interativos embutidos (Plotly via CDN)."""
    c = dados.candidatura
    rg = dados.resultado_geral

    graficos_html = "\n".join(
        f"<div class='grafico'><h3>{titulo}</h3>{fig.to_html(include_plotlyjs=False, full_html=False)}</div>"
        for titulo, fig in dados.figuras.items()
    )

    avisos_html = (
        "<ul>" + "".join(f"<li>{a}</li>" for a in dados.limitacoes) + "</ul>"
        if dados.limitacoes else "<p>Nenhuma limitacao registrada nesta execucao.</p>"
    )

    tabela_ranking = dados.ranking.head(15).to_html(index=False, classes="tabela", border=0)
    tabela_territorial = dados.territorial_indice.head(20).to_html(index=False, classes="tabela", border=0)
    tabela_bairros = (
        dados.bairros_agg.head(15).to_html(index=False, classes="tabela", border=0)
        if dados.bairros_agg is not None else "<p>Analise de bairro indisponivel.</p>"
    )

    secao_rivais = ""
    if dados.rivais_similaridade is not None and not dados.rivais_similaridade.empty:
        secao_rivais = f"""
  <h2>Os 3 maiores rivais (mesma base eleitoral)</h2>
  <p>Rivais com a distribuicao geografica de votos mais parecida com a do candidato
  (correlacao de Pearson entre os vetores de participacao por territorio) - quem
  disputa a mesma base eleitoral, independente do tamanho total da candidatura.</p>
  {dados.rivais_similaridade.to_html(index=False, classes='tabela', border=0)}
"""

    secao_correlacoes = ""
    if dados.correlacoes is not None and not dados.correlacoes.empty:
        secao_correlacoes = f"""
  <h2>Correlacao com o desempenho eleitoral</h2>
  {dados.correlacoes.to_html(index=False, classes='tabela', border=0)}
"""

    secao_logistica = ""
    if dados.regressao_logistica is not None:
        m = dados.regressao_logistica
        interpretacoes_html = "<ul>" + "".join(f"<li>{i}</li>" for i in m.interpretacoes) + "</ul>"
        secao_logistica = f"""
  <h2>Regressao logistica - o que explica uma "boa votacao"</h2>
  <p>Limiar de "boa votacao": {m.limiar_usado}% dos votos validos do territorio
  (mediana do proprio candidato) - {m.n_positivos} territorios acima, {m.n_negativos} abaixo.
  Pseudo-R2 (McFadden): {m.pseudo_r2_mcfadden} | Acuracia (na amostra): {m.acuracia*100:.0f}%.</p>
  {m.coeficientes.to_html(index=False, classes='tabela', border=0)}
  {interpretacoes_html}
  <p><i>{m.limitacoes}</i></p>
"""

    secao_clusters = ""
    if dados.clusters_narrativa is not None and not dados.clusters_narrativa.empty:
        cards = "".join(
            f"<div class='cluster'><b>{linha['rotulo_acao']}</b> - Cluster {linha['cluster']}: {linha['resumo']}</div>"
            for _, linha in dados.clusters_narrativa.iterrows()
        )
        secao_clusters = f"""
  <h2>Segmentacao de territorios (clusters)</h2>
  <p>Agrupamento dos territorios por perfil demografico semelhante - usado para decidir
  onde investir esforco de campanha (canvassing, anuncios segmentados, agenda de visitas).</p>
  {cards}
"""

    secao_potencial = ""
    if dados.bairros_potencial is not None and not dados.bairros_potencial.empty:
        secao_potencial = f"""
  <h2>Territorios com maior potencial de crescimento</h2>
  <p>Combina o quanto o territorio esta abaixo da media de territorios com perfil
  demografico parecido (mesmo cluster) com a probabilidade prevista de boa votacao.</p>
  {dados.bairros_potencial.to_html(index=False, classes='tabela', border=0)}
"""

    secao_delta = ""
    if dados.delta_rivais is not None and not dados.delta_rivais.empty:
        secao_delta = f"""
  <h2>Delta de votos contra os principais rivais</h2>
  {dados.delta_rivais.head(30).to_html(index=False, classes='tabela', border=0)}
"""

    secao_maslow = ""
    if dados.maslow is not None and dados.maslow.fonte_efeito != "indisponivel":
        m = dados.maslow
        mapeadas = m.tiers_mapeados.query("status == 'mapeado'") if not m.tiers_mapeados.empty else m.tiers_mapeados
        if not mapeadas.empty:
            mapeadas_html = mapeadas.to_html(index=False, classes="tabela", border=0)
            sem_proxy_html = m.tiers_sem_proxy.to_html(index=False, classes="tabela", border=0)
            narrativa_html = "<ul>" + "".join(f"<li>{f}</li>" for f in m.narrativa) + "</ul>"
            secao_maslow = f"""
  <h2>Abordagem de Maslow (lente interpretativa)</h2>
  <p><i>{m.disclaimer}</i></p>
  {mapeadas_html}
  {narrativa_html}
  <h3>Niveis sem proxy disponivel nos dados atuais</h3>
  {sem_proxy_html}
"""

    secao_economico = ""
    if dados.perfil_economico is not None and dados.perfil_economico.disponivel:
        pe = dados.perfil_economico
        saldo_fmt = f"{pe.saldo_caged_2024:+,}".replace(",", ".")
        secao_economico = f"""
  <h2>Contexto economico do municipio (RAIS + CAGED)</h2>
  <p><i>{pe.limitacoes}</i></p>
  <div class="kpis">
    <div class="kpi"><div class="valor">{_formatar_numero(pe.vinculos_ativos_total)}</div><div class="rotulo">Vinculos formais ativos (RAIS 2023)</div></div>
    <div class="kpi"><div class="valor">{_formatar_numero(pe.estabelecimentos_ativos)}</div><div class="rotulo">Estabelecimentos ativos (RAIS 2023)</div></div>
    <div class="kpi"><div class="valor">{saldo_fmt}</div><div class="rotulo">Saldo de empregos formais (CAGED 2024) - {pe.tendencia}</div></div>
  </div>
"""

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Relatorio Executivo - {c.nome_urna}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  body {{ font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; color: #0b0b0b; max-width: 1100px; margin: 0 auto; padding: 32px 20px; background: #fcfcfb; }}
  h1 {{ font-size: 1.6rem; }}
  h2 {{ border-bottom: 2px solid #2a78d6; padding-bottom: 4px; margin-top: 2.5rem; }}
  .kpis {{ display: flex; flex-wrap: wrap; gap: 16px; margin: 20px 0; }}
  .kpi {{ background: white; border: 1px solid #e1e0d9; border-radius: 8px; padding: 14px 18px; min-width: 180px; }}
  .kpi .valor {{ font-size: 1.5rem; font-weight: 700; color: #2a78d6; }}
  .kpi .rotulo {{ font-size: 0.85rem; color: #52514e; }}
  table.tabela {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; margin-bottom: 1.5rem; }}
  table.tabela th {{ background: #2a78d6; color: white; padding: 6px 10px; text-align: left; }}
  table.tabela td {{ padding: 6px 10px; border-bottom: 1px solid #e1e0d9; }}
  .grafico {{ margin-bottom: 2rem; }}
  .cluster {{ background: white; border: 1px solid #e1e0d9; border-left: 4px solid #2a78d6; border-radius: 6px; padding: 8px 14px; margin-bottom: 8px; }}
  .rodape {{ color: #898781; font-size: 0.8rem; margin-top: 3rem; border-top: 1px solid #e1e0d9; padding-top: 12px; }}
</style>
</head>
<body>
  <h1>Relatorio Executivo - Inteligencia Eleitoral</h1>
  <p><b>{c.nome_completo}</b> ("{c.nome_urna}") - {c.cargo} - {c.municipio}/{c.uf} -
     {c.partido_sigla} ({c.partido_nome}) - {c.coligacao_federacao or "Partido isolado"}</p>
  <p>Eleicao {c.ano_eleicao}, {c.turno}º turno. Resultado final declarado pelo TSE: <b>{c.resultado_final}</b>.</p>

  <div class="kpis">
    <div class="kpi"><div class="valor">{_formatar_numero(rg.total_votos)}</div><div class="rotulo">Total de votos</div></div>
    <div class="kpi"><div class="valor">{rg.colocacao_geral}º / {rg.total_concorrentes}</div><div class="rotulo">Colocacao geral</div></div>
    <div class="kpi"><div class="valor">{rg.pct_votos_validos}%</div><div class="rotulo">% dos votos validos</div></div>
    <div class="kpi"><div class="valor">{_formatar_numero(rg.distancia_para_ultimo_eleito)}</div><div class="rotulo">Votos para o ultimo eleito</div></div>
    <div class="kpi"><div class="valor">{rg.pct_candidato_sobre_partido}%</div><div class="rotulo">% dos votos do partido</div></div>
  </div>

  <h2>Concorrentes</h2>
  {tabela_ranking}
  {secao_rivais}

  <h2>Desempenho territorial e indice de performance</h2>
  {tabela_territorial}
  {secao_delta}

  <h2>Bairros/distritos com mais votos</h2>
  {tabela_bairros}
  {secao_correlacoes}
  {secao_logistica}
  {secao_clusters}
  {secao_potencial}

  {secao_maslow}

  {secao_economico}

  <h2>Graficos</h2>
  {graficos_html}

  <h2>Limitacoes metodologicas e avisos desta execucao</h2>
  {avisos_html}

  <div class="rodape">
    Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} - Fontes: TSE (votacao por secao e consulta de
    candidatos, 2024) e IBGE (Censo Demografico 2022, Agregados por Setores Censitarios). Dados agregados
    por territorio - nao permitem inferencia sobre o voto de eleitores individuais.
  </div>
</body></html>"""


def _figura_para_imagem(fig: go.Figure, largura_px: int = 900, altura_px: int = 450) -> Image:
    """Renderiza a figura como PNG estatico para o PDF - sempre em tema
    claro (fundo escuro do dashboard fica ilegivel impresso/na tela do PDF)."""
    fig_clara = figura_para_impressao(fig)
    buffer = io.BytesIO(fig_clara.to_image(format="png", width=largura_px, height=altura_px, scale=2))
    return Image(buffer, width=16 * cm, height=(16 * cm) * altura_px / largura_px)


def gerar_relatorio_pdf(dados: DadosRelatorio, caminho: str | Path) -> Path:
    """Gera um PDF resumido do relatorio executivo (metricas, tabelas e os
    3 primeiros graficos como imagem estatica, sempre em tema claro) -
    versao para impressao."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    c = dados.candidatura
    rg = dados.resultado_geral

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle("TituloCustom", parent=styles["Title"], textColor=colors.HexColor("#2a78d6"))
    secao_style = ParagraphStyle("SecaoCustom", parent=styles["Heading2"], textColor=colors.HexColor("#0b0b0b"))

    doc = SimpleDocTemplate(str(caminho), pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    elementos = [
        Paragraph("Relatorio Executivo - Inteligencia Eleitoral", titulo_style),
        Spacer(1, 10),
        Paragraph(
            f"<b>{c.nome_completo}</b> (\"{c.nome_urna}\") - {c.cargo} - {c.municipio}/{c.uf} - "
            f"{c.partido_sigla} - Resultado: {c.resultado_final}",
            styles["Normal"],
        ),
        Spacer(1, 14),
        Paragraph("Resumo", secao_style),
    ]

    tabela_kpi = Table(
        [
            ["Total de votos", _formatar_numero(rg.total_votos)],
            ["Colocacao geral", f"{rg.colocacao_geral}º de {rg.total_concorrentes}"],
            ["% dos votos validos", f"{rg.pct_votos_validos}%"],
            ["Votos para o ultimo eleito", _formatar_numero(rg.distancia_para_ultimo_eleito)],
            ["Votos do partido na disputa", _formatar_numero(rg.votos_partido_total)],
        ],
        colWidths=[8 * cm, 6 * cm],
    )
    tabela_kpi.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#2a78d6")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e1e0d9")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos += [tabela_kpi, Spacer(1, 16)]

    for titulo, fig in list(dados.figuras.items())[:3]:
        elementos += [Paragraph(titulo, secao_style), _figura_para_imagem(fig), Spacer(1, 12)]

    elementos += [Paragraph("Top 10 concorrentes", secao_style)]
    top10 = dados.ranking.head(10)[["colocacao", "nome_urna", "partido_sigla", "total_votos"]]
    linhas = [list(top10.columns)] + top10.astype(str).values.tolist()
    tabela_rank = Table(linhas, colWidths=[2 * cm, 7 * cm, 3 * cm, 3 * cm])
    tabela_rank.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2a78d6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e1e0d9")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    elementos += [tabela_rank, Spacer(1, 16)]

    if dados.rivais_similaridade is not None and not dados.rivais_similaridade.empty:
        elementos += [Paragraph("Os 3 maiores rivais (mesma base eleitoral)", secao_style)]
        rs = dados.rivais_similaridade[["nome_urna", "partido_sigla", "correlacao_base_eleitoral", "total_votos_rival"]]
        linhas_rs = [list(rs.columns)] + rs.astype(str).values.tolist()
        tabela_rs = Table(linhas_rs, colWidths=[6 * cm, 3 * cm, 4 * cm, 3 * cm])
        tabela_rs.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2a78d6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e1e0d9")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        elementos += [tabela_rs, Spacer(1, 16)]

    if dados.regressao_logistica is not None:
        m = dados.regressao_logistica
        elementos += [
            Paragraph("Regressao logistica - o que explica uma \"boa votacao\"", secao_style),
            Paragraph(
                f"Pseudo-R2 (McFadden): {m.pseudo_r2_mcfadden} | Acuracia (amostra): {m.acuracia*100:.0f}% | "
                f"{m.n_positivos} territorios de boa votacao vs. {m.n_negativos} abaixo do limiar.",
                styles["Normal"],
            ),
        ]
        for texto in m.interpretacoes:
            elementos += [Paragraph(f"- {texto}", styles["Normal"])]
        elementos += [Spacer(1, 12)]

    if dados.clusters_narrativa is not None and not dados.clusters_narrativa.empty:
        elementos += [Paragraph("Segmentacao de territorios (clusters)", secao_style)]
        for _, linha in dados.clusters_narrativa.iterrows():
            elementos += [Paragraph(f"<b>{linha['rotulo_acao']}</b> - {linha['resumo']}", styles["Normal"])]
        elementos += [Spacer(1, 12)]

    if dados.maslow is not None and dados.maslow.fonte_efeito != "indisponivel":
        m = dados.maslow
        mapeadas = m.tiers_mapeados.query("status == 'mapeado'") if not m.tiers_mapeados.empty else m.tiers_mapeados
        if not mapeadas.empty:
            elementos += [
                Paragraph("Abordagem de Maslow (lente interpretativa)", secao_style),
                Paragraph(m.disclaimer, styles["Normal"]),
            ]
            for frase in m.narrativa:
                elementos += [Paragraph(f"- {frase}", styles["Normal"])]
            elementos += [Spacer(1, 12)]

    if dados.perfil_economico is not None and dados.perfil_economico.disponivel:
        pe = dados.perfil_economico
        saldo_fmt = f"{pe.saldo_caged_2024:+,}".replace(",", ".")
        elementos += [
            Paragraph("Contexto economico do municipio (RAIS + CAGED)", secao_style),
            Paragraph(pe.limitacoes, styles["Normal"]),
            Paragraph(
                f"Vinculos formais ativos: {_formatar_numero(pe.vinculos_ativos_total)} | "
                f"Estabelecimentos ativos: {_formatar_numero(pe.estabelecimentos_ativos)} | "
                f"Saldo CAGED 2024: {saldo_fmt} ({pe.tendencia})",
                styles["Normal"],
            ),
            Spacer(1, 12),
        ]

    if dados.limitacoes:
        elementos += [Paragraph("Limitacoes metodologicas", secao_style)]
        for aviso in dados.limitacoes:
            elementos += [Paragraph(f"- {aviso}", styles["Normal"])]

    doc.build(elementos)
    return caminho
