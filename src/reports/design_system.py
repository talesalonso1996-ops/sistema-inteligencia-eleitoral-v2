"""Design system compartilhado dos relatorios ricos do SIET (Etapa 8,
Secao 28 do briefing de expansao). Mesmo sistema visual (A4, `.page`,
`.kpi-grid`, `.callout`, `.badge`, `.toc-list`) ja validado nesta sessao em
varios relatorios reais entregues como arquivo (Orlando Silva, Boulos,
etc.) - centralizado aqui pela primeira vez como modulo Python reutilizavel
em vez de HTML copiado manualmente por candidato.

Diferente daqueles relatorios (escritos a mao, com narrativa/biografia
pesquisada via WebSearch especificamente para uma pessoa), este modulo
gera um documento 100% automatico a partir de dado ja calculado por outras
camadas do SIET - por isso cobre só as secoes que sao seguras de gerar sem
intervencao humana (nunca fabrica biografia, midia ou trajetoria historica
sem fonte - ver nota metodologica em `relatorio_completo.py`)."""
from __future__ import annotations

CSS = """
:root {
  --paper: #faf9f6; --paper-alt: #f1efe8; --ink: #1a1a1a; --ink-2: #5b5b56; --ink-muted: #8a8a84;
  --navy: #0f2f52; --navy-2: #1c4d7c; --blue: #2a78d6; --blue-bg: #eaf1fb;
  --red: #b93630; --red-bg: #fbeae9; --green: #0ca30c; --green-bg: #eaf7ea;
  --amber: #c98500; --amber-bg: #fbf1de; --line: #dedbd1;
  --serif: Georgia, "Iowan Old Style", "Palatino Linotype", "Times New Roman", serif;
  --sans: system-ui, -apple-system, "Segoe UI", sans-serif;
  color-scheme: light;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #cfcabf; font-family: var(--sans); color: var(--ink); -webkit-font-smoothing: antialiased; }
body { padding: 28px 0 60px; }
.page {
  width: 210mm; min-height: 297mm; margin: 0 auto 28px; background: var(--paper);
  box-shadow: 0 4px 18px rgba(0,0,0,0.18), 0 0 0 1px rgba(0,0,0,0.04);
  position: relative; padding: 20mm 18mm 18mm; display: flex; flex-direction: column; overflow: hidden;
}
.page.cover { padding: 0; height: 297mm; }
.running-head {
  display: flex; justify-content: space-between; align-items: baseline; font-size: 10px;
  letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-muted); border-bottom: 1px solid var(--line);
  padding-bottom: 8px; margin-bottom: 14px; font-variant-numeric: tabular-nums;
}
.running-head strong { color: var(--navy); font-weight: 700; }
.running-foot {
  margin-top: auto; padding-top: 10px; border-top: 1px solid var(--line); display: flex;
  justify-content: space-between; font-size: 10px; color: var(--ink-muted); letter-spacing: 0.03em;
  font-variant-numeric: tabular-nums;
}
h1, h2, h3, h4 { font-family: var(--serif); font-weight: 700; text-wrap: balance; color: var(--navy); }
.sec-eyebrow { font-family: var(--sans); font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--blue); font-weight: 600; margin: 0 0 6px; }
.sec-title { font-size: 26px; margin: 0 0 4px; line-height: 1.15; }
.sec-sub { font-family: var(--sans); font-size: 13.5px; color: var(--ink-2); margin: 0 0 18px; max-width: 62ch; }
.page-body { flex: 1; }
p { line-height: 1.6; font-size: 13.5px; color: var(--ink); }
strong { color: var(--navy); }
table { width: 100%; border-collapse: collapse; font-size: 12px; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); }
th { background: var(--navy); color: #fff; font-weight: 600; font-size: 11px; letter-spacing: 0.02em; text-transform: uppercase; }
tbody tr:nth-child(even) { background: var(--paper-alt); }
td.num, th.num { text-align: right; }
.callout { border-left: 4px solid var(--blue); background: var(--blue-bg); padding: 12px 16px; border-radius: 0 6px 6px 0; font-size: 12.5px; color: var(--ink-2); margin: 14px 0; }
.callout.warn { border-color: var(--amber); background: var(--amber-bg); }
.callout.alert { border-color: var(--red); background: var(--red-bg); }
.callout.good { border-color: var(--green); background: var(--green-bg); }
.callout strong { display: block; color: var(--ink); font-size: 12px; margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.04em; font-family: var(--sans); }
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0; }
.kpi-grid.cols-3 { grid-template-columns: repeat(3, 1fr); }
.kpi { background: var(--paper-alt); border: 1px solid var(--line); border-radius: 8px; padding: 14px 14px 12px; }
.kpi .label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-muted); margin-bottom: 6px; }
.kpi .value { font-family: var(--serif); font-size: 24px; font-weight: 700; color: var(--navy); line-height: 1.1; font-variant-numeric: tabular-nums; }
.kpi .value.red { color: var(--red); }
.kpi .sub { font-size: 10.5px; color: var(--ink-2); margin-top: 4px; }
.badge { display: inline-block; padding: 3px 11px; border-radius: 999px; font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; }
.badge.red { background: var(--red); color: #fff; } .badge.navy { background: var(--navy); color: #fff; }
.badge.green { background: var(--green); color: #fff; } .badge.amber { background: var(--amber); color: #fff; }
.fig { margin: 14px 0; }
.fig .credit { font-size: 10.5px; color: var(--ink-muted); margin-top: 6px; }
.toc-list { list-style: none; padding: 0; margin: 10px 0; column-count: 2; column-gap: 30px; }
.toc-list li { display: flex; justify-content: space-between; gap: 6px; padding: 6px 0; border-bottom: 1px dotted var(--line); font-size: 12.5px; break-inside: avoid; }
.toc-list .n { color: var(--ink-muted); font-variant-numeric: tabular-nums; }
ul.tight { margin: 6px 0; padding-left: 18px; } ul.tight li { font-size: 13px; line-height: 1.55; margin-bottom: 6px; }
.table-scroll { overflow-x: auto; }
@media print { body { background: #fff; padding: 0; } .page { box-shadow: none; margin: 0; } }
"""

def head(titulo: str) -> str:
    """Bloco <head> completo, com o CSS ja embutido - concatenacao direta
    (nunca `.format()`/f-string aplicada DEPOIS de juntar com o CSS: o CSS
    tem chaves `{ }` em toda regra, que `.format()` tentaria interpretar
    como placeholder e quebraria com KeyError)."""
    return (
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{titulo}</title>"
        f"<style>{CSS}</style>"
        '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>'
    )


def pagina(rotulo_secao: str, eyebrow: str, titulo: str, corpo_html: str, sub: str = "", pagina_num: int | str = "") -> str:
    """Uma pagina .page padrao (nao-capa) - o bloco basico reutilizado por
    toda secao do relatorio."""
    sub_html = f'<p class="sec-sub">{sub}</p>' if sub else ""
    return f"""
<div class="page">
  <div class="running-head"><strong>SIET</strong><span>{rotulo_secao}</span></div>
  <div class="page-body">
    <div class="sec-eyebrow">{eyebrow}</div>
    <h1 class="sec-title">{titulo}</h1>
    {sub_html}
    {corpo_html}
  </div>
  <div class="running-foot"><span>SIET Inteligencia Eleitoral</span><span>Pagina {pagina_num}</span></div>
</div>
"""


def capa(titulo: str, subtitulo: str, badges_html: str, rodape_esq: str, rodape_dir: str) -> str:
    return f"""
<div class="page cover" style="padding:0;">
  <div style="position:relative; height:100%; display:flex; flex-direction:column; color:#fff; background:linear-gradient(160deg, var(--navy) 0%, #142c47 60%, #0a1a2c 100%);">
    <div style="position:relative; z-index:1; display:flex; flex-direction:column; height:100%; padding:16mm 18mm;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div style="font-family:var(--serif); font-size:22px; font-weight:700; letter-spacing:0.02em;">SIET</div>
        <div style="font-size:10.5px; letter-spacing:0.1em; text-transform:uppercase; opacity:0.85; text-align:right;">Sistema de Inteligencia<br/>Eleitoral &amp; Tendencias</div>
      </div>
      <div style="flex:1; display:flex; flex-direction:column; justify-content:center; max-width:150mm;">
        <div style="font-size:12px; letter-spacing:0.14em; text-transform:uppercase; color:#bcd4ef; margin-bottom:14px;">Relatorio Completo de Inteligencia Eleitoral</div>
        <h1 style="font-size:40px; color:#fff; margin:0 0 10px; line-height:1.08;">{titulo}</h1>
        <div style="font-size:16px; color:#e4ecf6; margin-bottom:22px;">{subtitulo}</div>
        <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">{badges_html}</div>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:flex-end; font-size:10.5px; color:#c9d8ea;">
        <div>{rodape_esq}</div>
        <div style="text-align:right;">{rodape_dir}</div>
      </div>
    </div>
  </div>
</div>
"""


def kpi_grid(itens: list[tuple[str, str, str, str]], cols: int = 4) -> str:
    """itens: lista de (label, valor, sub, tom) - tom em {"", "red"}."""
    classe = "kpi-grid" if cols == 4 else f"kpi-grid cols-{cols}"
    cards = "".join(
        f'<div class="kpi"><div class="label">{label}</div><div class="value {tom}">{valor}</div>'
        f'<div class="sub">{sub}</div></div>'
        for label, valor, sub, tom in itens
    )
    return f'<div class="{classe}">{cards}</div>'


def callout(texto: str, titulo: str = "", tom: str = "") -> str:
    classe = f"callout {tom}".strip()
    titulo_html = f"<strong>{titulo}</strong>" if titulo else ""
    return f'<div class="{classe}">{titulo_html}{texto}</div>'


def tabela_df(df, max_linhas: int | None = None) -> str:
    """Renderiza um DataFrame real ja calculado - nunca gera dado, so
    formata o que ja existe."""
    if df is None or df.empty:
        return "<p><em>Sem dado disponivel para esta tabela.</em></p>"
    dados = df.head(max_linhas) if max_linhas else df
    return f'<div class="table-scroll">{dados.to_html(index=False, classes="", border=0, na_rep="n/d")}</div>'


def figura_plotly(fig, legenda: str = "") -> str:
    """Grafico Plotly interativo embutido (mesma convencao ja usada em
    src/report_generator.py: plotly.js carregado uma unica vez via CDN no
    <head>, cada figura so envia sua propria div+dados)."""
    corpo = fig.to_html(include_plotlyjs=False, full_html=False)
    credito = f'<div class="credit">{legenda}</div>' if legenda else ""
    return f'<div class="fig">{corpo}{credito}</div>'


def badge(texto: str, tom: str = "navy") -> str:
    return f'<span class="badge {tom}">{texto}</span>'
