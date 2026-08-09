"""Relatorio Comparativo/Historico (Etapa 8, tipo 3 de 3 - Secao 28 do
briefing de expansao SIET) - versao AUTOMATICA, mirando a "Parte 3" dos
relatorios comparativos entregues como arquivo para candidatos reais nesta
sessao (Priante 2014-2022, Boulos comparativo 2022-2024).

NOTA METODOLOGICA CENTRAL: diferente dos tipos 1 e 2 (que so trocam o
RENDERIZADOR de dado ja calculado), este tipo precisa primeiro descobrir se
existe uma segunda disputa real da MESMA pessoa em outro ano carregado
neste projeto - isso e feito por `src/candidate_history.py`, que casa por
NOME DECLARADO + UF (as fontes daqui nao tem CPF) de forma deliberadamente
conservadora: nunca escolhe entre homonimos. Este renderizador nunca
inventa uma trajetoria - quando `ResultadoComparativoHistorico.
candidatura_comparavel` e None, a secao correspondente explica por que
nenhum comparativo foi encontrado, em vez de omitir silenciosamente ou
fabricar uma narrativa. Ver `limitacoes_gerador()` e as limitacoes ja
embutidas em `ResultadoComparativoHistorico.limitacoes`."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape as _esc

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import design_system as ds
from ..report_generator import DadosRelatorio


def limitacoes_gerador() -> list[str]:
    return [
        "O comparativo historico so e tentado entre os anos com votacao por secao "
        "carregada localmente neste projeto (2022 e 2024) - candidaturas de outros anos "
        "nao geram comparativo territorial.",
        "O cruzamento entre eleicoes usa nome declarado + UF, nunca um identificador "
        "unico como CPF - ver a limitacao especifica na secao correspondente deste relatorio.",
    ]


def _fmt(v) -> str:
    if v is None:
        return "n/d"
    try:
        if isinstance(v, float) and v != v:  # NaN
            return "n/d"
        return f"{v:,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(v)


def gerar_relatorio_comparativo_html(dados: DadosRelatorio) -> str:
    c = dados.candidatura
    comp = dados.comparativo_historico
    paginas: list[str] = []
    contador_pagina = 2  # capa=1

    # ---------------------------------------------------------------- CAPA
    badges = (
        ds.badge("Comparativo", "navy")
        + f'<span style="font-size:12.5px; color:#cfe0f2;">Eleicao {c.ano_eleicao} '
        f'&middot; {c.cargo.title()} &middot; {c.municipio}/{c.uf}</span>'
    )
    paginas.append(ds.capa(
        titulo=c.nome_urna,
        subtitulo="Relatorio Comparativo/Historico &middot; Continuidade entre disputas reais<br/>"
                  f"{c.partido_sigla} - {c.partido_nome}",
        badges_html=badges,
        rodape_esq="Dados oficiais TSE (consulta_cand, votacao por secao)",
        rodape_dir=f"Gerado automaticamente pelo SIET em {datetime.now().strftime('%d/%m/%Y')}<br/>Leitura territorial, nunca individual. O voto e secreto.",
    ))

    # ------------------------------------------------------- RESUMO
    contador_pagina += 1
    encontrado = comp is not None and comp.candidatura_comparavel is not None
    com_territorio = encontrado and comp.comparativo_zonas is not None and not comp.comparativo_zonas.empty
    if com_territorio:
        situacao_label, situacao_tom = "Comparativo territorial real encontrado", "good"
    elif encontrado:
        situacao_label, situacao_tom = "Segunda candidatura encontrada, sem dado territorial", "warn"
    else:
        situacao_label, situacao_tom = "Nenhuma segunda disputa comparavel encontrada", "warn"
    corpo = ds.callout(
        f"Esta e a versao automatica: o sistema procura, por nome declarado + UF, uma "
        f"segunda disputa REAL da mesma pessoa nos anos com dado carregado neste projeto "
        f"(2022 e 2024) - nunca inventa uma trajetoria quando nao encontra.",
        situacao_label, situacao_tom,
    )
    if comp is not None:
        corpo += "<ul class='tight'>" + "".join(f"<li>{l}</li>" for l in comp.limitacoes) + "</ul>"
    paginas.append(ds.pagina("Resumo executivo", "Relatorio Comparativo",
                              "O que este relatorio encontrou", corpo, pagina_num=contador_pagina))

    if com_territorio:
        cand_a, cand_b = comp.candidatura_atual, comp.candidatura_comparavel

        # ------------------------------------------------- DUAS DISPUTAS REAIS
        contador_pagina += 1
        corpo = ds.kpi_grid([
            (f"{cand_a.ano_eleicao} - {cand_a.cargo.title()}", _fmt(cand_a.total_votos),
             f"{cand_a.partido_sigla} - {cand_a.resultado_final}", ""),
            (f"{cand_b.ano_eleicao} - {cand_b.cargo.title()}", _fmt(comp.votos_totais_comparavel),
             f"{cand_b.partido_sigla} - {cand_b.resultado_final}", ""),
            ("Zonas em comum", str(comp.n_zonas_comuns), "presentes nos dois anos", ""),
            ("Correlacao territorial", f"{comp.correlacao_territorial:.3f}" if comp.correlacao_territorial is not None else "n/d",
             "Pearson, voto por zona", ""),
        ])
        corpo += ds.callout(
            "Correlacao territorial mede se as MESMAS zonas eleitorais foram fortes/fracas nas "
            "duas disputas (continuidade de base) - proximo de 1 indica base territorial estavel; "
            "proximo de 0 indica pouca relacao entre onde o voto veio em cada disputa. Nao mede "
            "crescimento nem serve como projecao para uma eleicao futura.", "Metodologia", "warn",
        )
        paginas.append(ds.pagina("Duas disputas reais", "Fonte: TSE - candidate_history",
                                  f"{cand_a.ano_eleicao} vs {cand_b.ano_eleicao}", corpo, pagina_num=contador_pagina))

        # ------------------------------------------------- ZONA A ZONA
        contador_pagina += 1
        corpo = ds.tabela_df(comp.comparativo_zonas, max_linhas=30)
        paginas.append(ds.pagina("Zona a zona", "Fonte: TSE - desempenho_territorial (NR_ZONA)",
                                  "Onde a base se manteve, onde mudou", corpo,
                                  sub="Só as zonas eleitorais presentes nas duas disputas.",
                                  pagina_num=contador_pagina))

    elif encontrado:
        contador_pagina += 1
        cb = comp.candidatura_comparavel
        corpo = "<table><tbody>"
        corpo += f"<tr><td>Ano</td><td>{cb.ano_eleicao}</td></tr>"
        corpo += f"<tr><td>Cargo</td><td>{cb.cargo}</td></tr>"
        corpo += f"<tr><td>Partido</td><td>{cb.partido_sigla} - {cb.partido_nome}</td></tr>"
        corpo += f"<tr><td>Resultado</td><td>{cb.resultado_final}</td></tr>"
        corpo += "</tbody></table>"
        corpo += ds.callout(
            "Candidatura real encontrada no registro do TSE (consulta_cand), mas sem votacao "
            "por secao carregada localmente neste projeto para esse ano - nao e possivel montar "
            "comparativo territorial. Nenhum numero de voto por zona e mostrado ou estimado.",
            "Limitacao de dado", "warn",
        )
        paginas.append(ds.pagina("Segunda candidatura encontrada", "Fonte: TSE - consulta_cand",
                                  "Registro real, sem dado territorial", corpo, pagina_num=contador_pagina))

    else:
        contador_pagina += 1
        corpo = ds.callout(
            "Nenhuma segunda disputa real foi encontrada para esta pessoa nos anos com dado "
            "carregado neste projeto. Isso pode significar que a pessoa disputou só esta "
            "eleicao, que disputou em outro ano/UF fora do escopo deste projeto, ou que o nome "
            "declarado nao bateu de forma inequivoca (o casamento e conservador de proposito - "
            "nunca escolhe entre homonimos). Nenhuma trajetoria e inferida ou estimada.",
            "Sem comparativo", "warn",
        )
        paginas.append(ds.pagina("Segunda candidatura nao encontrada", "Fonte: TSE - candidate_history",
                                  "Nada a comparar", corpo, pagina_num=contador_pagina))

    # ------------------------------------------------------- LIMITACOES
    contador_pagina += 1
    limitacoes_todas = list(dados.limitacoes) + limitacoes_gerador()
    corpo = "<ul class='tight'>" + "".join(f"<li>{l}</li>" for l in limitacoes_todas) + "</ul>"
    paginas.append(ds.pagina("Limitacoes e fontes", "Nota final",
                              "O que este relatorio nao sabe, e de onde vem o que ele sabe", corpo,
                              pagina_num=contador_pagina))

    html = ds.head(f"Relatorio Comparativo SIET - {c.nome_urna}") + "\n".join(paginas)
    return html


def _tabela_reportlab(linhas: list[list[str]], col_widths: list[float]) -> Table:
    tabela = Table(linhas, colWidths=col_widths)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2a78d6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e1e0d9")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    return tabela


def gerar_relatorio_comparativo_pdf(dados: DadosRelatorio, caminho: str | Path) -> Path:
    """Versao PDF resumida do relatorio comparativo - mesmo padrao ReportLab
    (tema claro, tabelas + texto) ja usado por report_generator.gerar_relatorio_pdf
    (Tipo 1) e relatorio_estrategia.gerar_relatorio_estrategia_pdf (Tipo 2).
    Cobre as 3 situacoes reais que gerar_relatorio_comparativo_html cobre
    (comparativo territorial encontrado / segunda candidatura sem territorio /
    nenhuma segunda disputa encontrada) - nunca fabrica uma trajetoria quando
    nao ha comparativo real."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    c = dados.candidatura
    comp = dados.comparativo_historico

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle("TituloCustom", parent=styles["Title"], textColor=colors.HexColor("#2a78d6"))
    secao_style = ParagraphStyle("SecaoCustom", parent=styles["Heading2"], textColor=colors.HexColor("#0b0b0b"))

    doc = SimpleDocTemplate(str(caminho), pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    elementos = [
        Paragraph("Relatorio Comparativo/Historico - Inteligencia Eleitoral", titulo_style),
        Spacer(1, 10),
        # ReportLab Paragraph interpreta mini-XML, nao escapa sozinho (ver
        # nota identica em report_generator.py) - _esc() evita que um "&"
        # real (ex.: coligacao/partido) quebre a geracao do PDF.
        Paragraph(
            f"<b>{_esc(c.nome_completo)}</b> (\"{_esc(c.nome_urna)}\") - {_esc(c.cargo)} - "
            f"{_esc(c.municipio)}/{_esc(c.uf)} - {_esc(c.partido_sigla)} - Eleicao {c.ano_eleicao}",
            styles["Normal"],
        ),
        Spacer(1, 14),
    ]

    encontrado = comp is not None and comp.candidatura_comparavel is not None
    com_territorio = encontrado and comp.comparativo_zonas is not None and not comp.comparativo_zonas.empty

    if com_territorio:
        cand_a, cand_b = comp.candidatura_atual, comp.candidatura_comparavel
        elementos += [Paragraph("Duas disputas reais", secao_style)]
        linhas = [
            ["Disputa", "Votos", "Partido / Resultado"],
            [f"{cand_a.ano_eleicao} - {cand_a.cargo.title()}", f"{cand_a.total_votos:,.0f}".replace(",", "."),
             f"{cand_a.partido_sigla} - {cand_a.resultado_final}"],
            [f"{cand_b.ano_eleicao} - {cand_b.cargo.title()}", _fmt(comp.votos_totais_comparavel),
             f"{cand_b.partido_sigla} - {cand_b.resultado_final}"],
        ]
        elementos += [_tabela_reportlab(linhas, [7 * cm, 4 * cm, 5 * cm]), Spacer(1, 8)]
        corr_txt = f"{comp.correlacao_territorial:.3f}" if comp.correlacao_territorial is not None else "n/d"
        elementos += [Paragraph(
            f"Zonas em comum: <b>{comp.n_zonas_comuns}</b>. Correlacao territorial: "
            f"<b>{corr_txt}</b> (Pearson, voto por zona).",
            styles["Normal"],
        )]
        elementos += [Paragraph(
            "Correlacao territorial mede se as mesmas zonas eleitorais foram fortes/fracas nas duas "
            "disputas (continuidade de base) - nao mede crescimento nem serve como projecao para uma "
            "eleicao futura.",
            styles["Normal"],
        ), Spacer(1, 14)]

        elementos += [Paragraph("Zona a zona (ate 30 zonas)", secao_style)]
        zonas = comp.comparativo_zonas.head(30)
        linhas_z = [list(zonas.columns)] + zonas.astype(str).values.tolist()
        n_cols = len(zonas.columns)
        elementos += [_tabela_reportlab(linhas_z, [16 * cm / n_cols] * n_cols), Spacer(1, 14)]

    elif encontrado:
        cb = comp.candidatura_comparavel
        elementos += [Paragraph("Segunda candidatura encontrada, sem dado territorial", secao_style)]
        linhas = [
            ["Ano", "Cargo", "Partido", "Resultado"],
            [str(cb.ano_eleicao), cb.cargo, f"{cb.partido_sigla} - {cb.partido_nome}", cb.resultado_final],
        ]
        elementos += [_tabela_reportlab(linhas, [3 * cm, 5 * cm, 5 * cm, 5 * cm]), Spacer(1, 8)]
        elementos += [Paragraph(
            "Candidatura real encontrada no registro do TSE (consulta_cand), mas sem votacao por "
            "secao carregada localmente neste projeto para esse ano - nao e possivel montar "
            "comparativo territorial. Nenhum numero de voto por zona e mostrado ou estimado.",
            styles["Normal"],
        ), Spacer(1, 14)]

    else:
        elementos += [Paragraph("Nenhuma segunda disputa comparavel encontrada", secao_style)]
        elementos += [Paragraph(
            "Nenhuma segunda disputa real foi encontrada para esta pessoa nos anos com dado carregado "
            "neste projeto. Isso pode significar que a pessoa disputou so esta eleicao, que disputou "
            "em outro ano/UF fora do escopo deste projeto, ou que o nome declarado nao bateu de forma "
            "inequivoca (o casamento e conservador de proposito - nunca escolhe entre homonimos). "
            "Nenhuma trajetoria e inferida ou estimada.",
            styles["Normal"],
        ), Spacer(1, 14)]

    limitacoes_todas = list(dados.limitacoes) + limitacoes_gerador()
    if comp is not None:
        limitacoes_todas = limitacoes_todas + list(comp.limitacoes)
    elementos += [Paragraph("Limitacoes e fontes", secao_style)]
    for aviso in limitacoes_todas:
        elementos += [Paragraph(f"- {aviso}", styles["Normal"])]

    doc.build(elementos)
    return caminho
