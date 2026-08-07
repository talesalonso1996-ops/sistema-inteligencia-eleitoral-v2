"""Relatorio Completo (Etapa 8, tipo 1 de 3 - Secao 28 do briefing de
expansao SIET) - versao AUTOMATICA e REUTILIZAVEL do design rico ja
validado nesta sessao em relatorios entregues como arquivo para
candidatos reais especificos (Orlando Silva, Boulos, Priante, etc.).

NOTA METODOLOGICA CENTRAL (o que este modulo NAO faz, de proposito):
aqueles relatorios anteriores tinham capitulos de biografia, trajetoria
historica e repercussao de midia pesquisados manualmente via WebSearch
para cada pessoa - dado real, mas que exige pesquisa NOVA por candidato,
incompativel com um gerador 100% automatico chamado de dentro do app.
Este modulo cobre deliberadamente SO as secoes 100% orientadas a dado ja
calculado pelas camadas existentes do SIET (TSE/IBGE/RAIS-CAGED) - nunca
fabrica biografia/midia/trajetoria historica. Ver `limitacoes_gerador()`.

Reaproveita o MESMO `DadosRelatorio` (`src/report_generator.py`) ja
computado pela secao "Relatorio" existente em app.py - nao recalcula
nenhuma analise, so troca o RENDERIZADOR (design de 1 pagina rolavel ->
design de paginas A4 com o mesmo sistema visual dos relatorios ricos)."""
from __future__ import annotations

from datetime import datetime

from . import design_system as ds
from ..report_generator import DadosRelatorio


def limitacoes_gerador() -> list[str]:
    return [
        "Gerado automaticamente a partir de dado ja calculado pelo SIET (TSE/IBGE/RAIS-CAGED) - "
        "nao inclui biografia, trajetoria historica pre-TSE ou repercussao de midia (exigiriam "
        "pesquisa via fonte externa especifica por candidato, fora do escopo de um gerador automatico).",
        "Numero de paginas varia conforme o dado disponivel para a candidatura (ex.: malha geografica "
        "nao configurada para todas as UFs, regressao pode ficar indisponivel com poucas observacoes).",
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


def _fmt_pct(v, casas: int = 2) -> str:
    if v is None:
        return "n/d"
    try:
        return f"{v:.{casas}f}%".replace(".", ",")
    except (TypeError, ValueError):
        return str(v)


def gerar_relatorio_completo_html(dados: DadosRelatorio) -> str:
    c = dados.candidatura
    rg = dados.resultado_geral
    paginas: list[str] = []
    contador_pagina = 2  # capa=1

    # ---------------------------------------------------------------- CAPA
    situacao_tom = "green" if (rg.colocacao_geral or 0) <= rg.total_concorrentes / 2 else "amber"
    badges = (
        ds.badge(c.resultado_final, situacao_tom)
        + f'<span style="font-size:12.5px; color:#cfe0f2;">Eleicao {c.ano_eleicao} '
        f'&middot; {rg.colocacao_geral or "n/d"}o de {rg.total_concorrentes} &middot; {_fmt(rg.total_votos)} votos</span>'
    )
    paginas.append(ds.capa(
        titulo=c.nome_urna,
        subtitulo=f'"{c.nome_urna}" &middot; {c.cargo.title()} &middot; {c.municipio}/{c.uf}<br/>{c.partido_sigla} - {c.partido_nome}',
        badges_html=badges,
        rodape_esq="Dados oficiais TSE (candidaturas, votacao por secao) + Censo Demografico IBGE 2022",
        rodape_dir=f"Gerado automaticamente pelo SIET em {datetime.now().strftime('%d/%m/%Y')}<br/>Leitura territorial, nunca individual. O voto e secreto.",
    ))

    # ------------------------------------------------------- RESUMO EXECUTIVO
    contador_pagina += 1
    corpo = ds.kpi_grid([
        ("Total de votos", _fmt(rg.total_votos), _fmt_pct(rg.pct_votos_validos), ""),
        ("Colocacao", f"{rg.colocacao_geral or 'n/d'}o", f"de {rg.total_concorrentes}", ""),
        ("1o colocado", _fmt(rg.votos_primeiro_colocado), rg.nome_primeiro_colocado, ""),
        ("Distancia p/ 1o colocado", _fmt(rg.distancia_para_primeiro_colocado), "votos", "red" if rg.distancia_para_primeiro_colocado else ""),
    ])
    corpo += "<table><tbody>"
    corpo += f"<tr><td>Nome completo</td><td>{c.nome_completo}</td></tr>"
    corpo += f"<tr><td>Numero</td><td>{c.numero}</td></tr>"
    corpo += f"<tr><td>Cargo</td><td>{c.cargo}</td></tr>"
    corpo += f"<tr><td>Unidade eleitoral</td><td>{c.municipio}/{c.uf}</td></tr>"
    corpo += f"<tr><td>Partido</td><td>{c.partido_sigla} - {c.partido_nome}</td></tr>"
    corpo += f"<tr><td>Coligacao/federacao</td><td>{c.coligacao_federacao}</td></tr>"
    corpo += f"<tr><td>Resultado oficial</td><td>{c.resultado_final}</td></tr>"
    if rg.votos_ultimo_eleito is not None:
        corpo += f"<tr><td>Votos do ultimo eleito</td><td>{_fmt(rg.votos_ultimo_eleito)}</td></tr>"
        corpo += f"<tr><td>Distancia p/ ultimo eleito</td><td>{_fmt(rg.distancia_para_ultimo_eleito)}</td></tr>"
    corpo += f"<tr><td>Votos totais do partido na disputa</td><td>{_fmt(rg.votos_partido_total)} ({_fmt_pct(rg.pct_partido_sobre_validos)})</td></tr>"
    corpo += f"<tr><td>Participacao do candidato no partido</td><td>{_fmt_pct(rg.pct_candidato_sobre_partido)}</td></tr>"
    corpo += "</tbody></table>"
    paginas.append(ds.pagina("Resumo executivo", "Fonte: TSE - candidaturas e votacao por secao",
                              "Numeros-chave do resultado", corpo, pagina_num=contador_pagina))

    # -------------------------------------------------------------- RANKING
    contador_pagina += 1
    corpo = ds.tabela_df(dados.ranking, max_linhas=20)
    paginas.append(ds.pagina("Ranking dos concorrentes", "Fonte: TSE - ranking_disputa",
                              "Os mais votados da disputa", corpo,
                              sub=f"{len(dados.ranking)} candidatos na disputa completa.",
                              pagina_num=contador_pagina))

    if dados.ranking_partidos is not None:
        contador_pagina += 1
        corpo = ds.tabela_df(dados.ranking_partidos, max_linhas=15)
        paginas.append(ds.pagina("Desempenho por partido", "Fonte: TSE - ranking_partidos",
                                  "Forca partidaria na disputa", corpo, pagina_num=contador_pagina))

    # ------------------------------------------------------- RIVAIS
    if dados.rivais_similaridade is not None and not dados.rivais_similaridade.empty:
        contador_pagina += 1
        corpo = ds.tabela_df(dados.rivais_similaridade)
        if "Rivais por similaridade de base eleitoral" in dados.figuras:
            corpo += ds.figura_plotly(dados.figuras["Rivais por similaridade de base eleitoral"])
        paginas.append(ds.pagina("Rivais da mesma base territorial", "Fonte: TSE - rivais_por_similaridade_eleitorado",
                                  "Quem disputa o mesmo eleitorado", corpo,
                                  sub="Similaridade de distribuicao territorial do voto - nao e volume de votos.",
                                  pagina_num=contador_pagina))

    # ------------------------------------------------------- TERRITORIO
    contador_pagina += 1
    corpo = ""
    if "Votos por territorio" in "".join(dados.figuras.keys()) or any("Votos por" in k for k in dados.figuras):
        chave_grafico = next((k for k in dados.figuras if k.startswith("Votos por")), None)
        if chave_grafico:
            corpo += ds.figura_plotly(dados.figuras[chave_grafico])
    corpo += ds.tabela_df(dados.territorial_indice, max_linhas=25)
    paginas.append(ds.pagina("Indice de performance territorial", "Fonte: TSE - calcular_indice_performance",
                              "Onde o candidato e mais forte", corpo, pagina_num=contador_pagina))

    if dados.zonas_disputa is not None and not dados.zonas_disputa.empty:
        contador_pagina += 1
        contagem = dados.zonas_disputa["situacao"].value_counts()
        itens = [(sit.replace("_", " ").title(), str(n), "territorios", "") for sit, n in contagem.items()]
        corpo = ds.kpi_grid(itens, cols=min(4, max(1, len(itens))))
        corpo += ds.tabela_df(dados.zonas_disputa, max_linhas=25)
        paginas.append(ds.pagina("Situacao da disputa por territorio", "Fonte: TSE - zonas_de_disputa",
                                  "Dominio, disputa acirrada ou desvantagem", corpo, pagina_num=contador_pagina))

    if dados.concentracao_territorial is not None:
        contador_pagina += 1
        ct = dados.concentracao_territorial
        corpo = ds.kpi_grid([
            ("HHI", f"{ct.hhi:.4f}", "0=disperso, 1=concentrado", ""),
            ("Gini", f"{ct.gini:.4f}", "desigualdade entre territorios", ""),
            ("Dependencia do maior territorio", _fmt_pct(ct.dependencia_maior_municipio_pct), "", ""),
            ("Dependencia top-5", _fmt_pct(ct.dependencia_top5_pct), "", ""),
        ])
        paginas.append(ds.pagina("Concentracao territorial", "Fonte: TSE - calcular_concentracao_territorial",
                                  "HHI e Gini do voto", corpo, pagina_num=contador_pagina))

    # ------------------------------------------------------- DEMOGRAFIA / ESTATISTICA
    if dados.correlacoes is not None and not dados.correlacoes.empty:
        contador_pagina += 1
        corpo = ds.tabela_df(dados.correlacoes)
        paginas.append(ds.pagina("Correlacoes com a votacao", "Fonte: Censo IBGE 2022 - correlacoes_com_votos",
                                  "O que anda junto com o voto", corpo, pagina_num=contador_pagina))

    if dados.regressao_linear is not None or dados.regressao_logistica is not None:
        contador_pagina += 1
        corpo = ""
        if dados.regressao_linear is not None:
            r = dados.regressao_linear
            corpo += f"<p><strong>Regressao linear</strong> - R2={r.r_quadrado}, R2 ajustado={r.r_quadrado_ajustado}, n={r.n_observacoes}</p>"
            corpo += ds.tabela_df(r.coeficientes)
        if dados.regressao_logistica is not None:
            m = dados.regressao_logistica
            corpo += f"<p style='margin-top:14px;'><strong>Regressao logistica</strong> - Pseudo-R2={m.pseudo_r2_mcfadden}, acuracia={m.acuracia}</p>"
            corpo += ds.tabela_df(m.coeficientes)
            corpo += ds.callout(m.limitacoes)
        paginas.append(ds.pagina("Regressao territorial", "Fonte: Censo IBGE 2022 - regression_models",
                                  "O que explica o padrao territorial", corpo, pagina_num=contador_pagina))

    if dados.clusters_narrativa is not None and not dados.clusters_narrativa.empty:
        contador_pagina += 1
        corpo = ds.tabela_df(dados.clusters_narrativa)
        paginas.append(ds.pagina("Clusters territoriais", "Fonte: Censo IBGE 2022 - segmentar_territorios",
                                  "Perfis territoriais reais", corpo, pagina_num=contador_pagina))

    if dados.bairros_potencial is not None and not dados.bairros_potencial.empty:
        contador_pagina += 1
        corpo = ""
        if "Territorios com maior potencial" in dados.figuras:
            corpo += ds.figura_plotly(dados.figuras["Territorios com maior potencial"])
        corpo += ds.tabela_df(dados.bairros_potencial, max_linhas=15)
        paginas.append(ds.pagina("Territorios de maior potencial", "Fonte: identificar_bairros_potencial",
                                  "Onde investir esforco de campanha", corpo, pagina_num=contador_pagina))

    # ------------------------------------------------------- MONTE CARLO
    if dados.cenario_monte_carlo is not None:
        contador_pagina += 1
        cen = dados.cenario_monte_carlo
        corpo = ds.kpi_grid([
            ("Votos reais hoje", _fmt(cen.votos_reais_atuais), f"{cen.n_territorios} territorios", ""),
            ("Cenario conservador (p5)", _fmt(cen.conservador), "", ""),
            ("Cenario mediano (p50)", _fmt(cen.mediano), "", ""),
            ("Cenario otimista (p95)", _fmt(cen.otimista), "", ""),
        ])
        corpo += ds.callout(
            "Simulacao de Monte Carlo PARAMETRICA: propaga a incerteza estatistica real dos "
            "coeficientes ja estimados pela regressao linear (Normal(coeficiente, erro-padrao)) - "
            "nunca fabrica taxa de crescimento ou pesquisa hipotetica. Nao simula turnout futuro "
            "nem comportamento de rivais.", "Metodologia", "warn",
        )
        if dados.simulacao_monte_carlo is not None:
            corpo += ds.tabela_df(dados.simulacao_monte_carlo.territorios, max_linhas=20)
        paginas.append(ds.pagina("Cenarios de votos (Monte Carlo)", "Fonte: src/projections/monte_carlo.py",
                                  "Faixas de incerteza estatistica real", corpo, pagina_num=contador_pagina))

    # ------------------------------------------------------- MASLOW
    if dados.maslow is not None and dados.maslow.fonte_efeito != "indisponivel":
        contador_pagina += 1
        corpo = f"<p>Fonte do efeito: <strong>{dados.maslow.fonte_efeito}</strong></p>"
        if "Piramide de Maslow" in dados.figuras:
            corpo += ds.figura_plotly(dados.figuras["Piramide de Maslow"])
        mapeadas = dados.maslow.tiers_mapeados
        if mapeadas is not None and not mapeadas.empty:
            colunas = [col for col in ["tier", "label", "variavel", "valor_efeito", "significativo"] if col in mapeadas.columns]
            corpo += ds.tabela_df(mapeadas[colunas] if colunas else mapeadas)
        paginas.append(ds.pagina("Piramide de Maslow", "Fonte: gerar_analise_maslow",
                                  "Necessidades humanas e padrao de voto", corpo, pagina_num=contador_pagina))

    # ------------------------------------------------------- CONTEXTO ECONOMICO
    if dados.perfil_economico is not None and dados.perfil_economico.disponivel:
        contador_pagina += 1
        pe = dados.perfil_economico
        corpo = ds.kpi_grid([
            ("Vinculos formais ativos", _fmt(pe.vinculos_ativos_total), "", ""),
            ("Estabelecimentos ativos", _fmt(pe.estabelecimentos_ativos), "", ""),
            ("Saldo CAGED 2024", _fmt(pe.saldo_caged_2024), pe.tendencia, "" if (pe.saldo_caged_2024 or 0) >= 0 else "red"),
            ("Formalizacao CLT", _fmt_pct(pe.pct_formalizacao_clt), "", ""),
        ])
        corpo += ds.callout(pe.limitacoes)
        if "Perfil economico do municipio (RAIS/CAGED)" in dados.figuras:
            corpo += ds.figura_plotly(dados.figuras["Perfil economico do municipio (RAIS/CAGED)"])
        paginas.append(ds.pagina("Contexto economico", "Fonte: RAIS Estabelecimentos + Novo CAGED",
                                  "Mercado de trabalho do municipio", corpo, pagina_num=contador_pagina))

    # ------------------------------------------------------- LIMITACOES
    contador_pagina += 1
    limitacoes_todas = list(dados.limitacoes) + limitacoes_gerador()
    corpo = "<ul class='tight'>" + "".join(f"<li>{l}</li>" for l in limitacoes_todas) + "</ul>"
    paginas.append(ds.pagina("Limitacoes e fontes", "Nota final",
                              "O que este relatorio nao sabe, e de onde vem o que ele sabe", corpo,
                              pagina_num=contador_pagina))

    html = ds.head(f"Relatorio SIET - {c.nome_urna}") + "\n".join(paginas)
    return html
