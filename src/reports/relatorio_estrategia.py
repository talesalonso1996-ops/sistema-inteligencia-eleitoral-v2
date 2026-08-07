"""Relatorio de Estrategia/Marketing (Etapa 8, tipo 2 de 3 - Secao 28 do
briefing de expansao SIET) - versao AUTOMATICA e ENXUTA, deliberadamente
menor que os relatorios "Parte 2" entregues como arquivo para candidatos
reais nesta sessao (Orlando Silva, Aline Torres, Marlon Reis, Priante).

NOTA METODOLOGICA (por que "enxuta", nao um espelho 1:1 da Parte 2): a
Parte 2 daqueles relatorios tem capitulos com narrativa escrita a mao por
zona ("Zona 192 - a maior oportunidade isolada do estado") e uma secao de
pesquisa cultural/microinfluenciadores feita via WebSearch especifica por
candidato ("Criadores e paginas locais reais - onde foram encontrados, e
onde nao"). Isso exige pesquisa NOVA por pessoa, exatamente o mesmo motivo
pelo qual `relatorio_completo.py` (tipo 1) nunca gera biografia/midia. Este
modulo cobre so a fatia 100% orientada a dado ja calculado pelo SIET:
portfolio de territorios de investimento, rivais diretos + patrimonio
comparativo (TSE), segmentacao territorial e leitura de necessidades via
Piramide de Maslow. O "plano de acao" e literalmente a mesma classificacao
de potencial ja calculada, reapresentada em ordem de prioridade - nunca uma
tatica de campanha inventada (canal, mensagem, formato de anuncio etc.),
que exigiria conhecimento que os dados nao contem. Ver `limitacoes_gerador()`.

Reaproveita o MESMO `DadosRelatorio` (`src/report_generator.py`) que o tipo
1 - so troca quais campos sao renderizados e como."""
from __future__ import annotations

from datetime import datetime

from . import design_system as ds
from ..report_generator import DadosRelatorio


def limitacoes_gerador() -> list[str]:
    return [
        "Gerado automaticamente a partir de dado ja calculado pelo SIET (TSE/IBGE/RAIS-CAGED) - "
        "versao enxuta do modelo de relatorio de estrategia: nao inclui narrativa manual por zona, "
        "pesquisa de cena cultural/microinfluenciadores ou qualquer tatica de campanha (canal, "
        "mensagem, formato de anuncio) - exigiriam pesquisa ou julgamento humano especifico por "
        "candidato, fora do escopo de um gerador automatico.",
        "O 'plano de acao' reapresenta em ordem de prioridade a mesma classificacao de potencial "
        "territorial ja calculada (gap vs. cluster + probabilidade estatistica quando disponivel) - "
        "nao e uma recomendacao tatica nova.",
        "Numero de paginas varia conforme o dado disponivel para a candidatura.",
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


def gerar_relatorio_estrategia_html(dados: DadosRelatorio) -> str:
    c = dados.candidatura
    paginas: list[str] = []
    contador_pagina = 2  # capa=1

    # ---------------------------------------------------------------- CAPA
    badges = (
        ds.badge("Estrategia", "navy")
        + f'<span style="font-size:12.5px; color:#cfe0f2;">Eleicao {c.ano_eleicao} '
        f'&middot; {c.cargo.title()} &middot; {c.municipio}/{c.uf}</span>'
    )
    paginas.append(ds.capa(
        titulo=c.nome_urna,
        subtitulo=f"Relatorio de Estrategia &middot; Territorios de investimento e rivais diretos<br/>{c.partido_sigla} - {c.partido_nome}",
        badges_html=badges,
        rodape_esq="Dados oficiais TSE (candidaturas, votacao por secao, patrimonio declarado) + Censo Demografico IBGE 2022",
        rodape_dir=f"Gerado automaticamente pelo SIET em {datetime.now().strftime('%d/%m/%Y')}<br/>Leitura territorial, nunca individual. O voto e secreto.",
    ))

    # ------------------------------------------------------- RESUMO
    contador_pagina += 1
    n_potencial = len(dados.bairros_potencial) if dados.bairros_potencial is not None else 0
    n_rivais = len(dados.rivais_similaridade) if dados.rivais_similaridade is not None else 0
    corpo = ds.kpi_grid([
        ("Territorios de investimento mapeados", str(n_potencial), "maior potencial de crescimento", ""),
        ("Rivais diretos identificados", str(n_rivais), "mesma base eleitoral", ""),
        ("Clusters territoriais", str(len(dados.clusters_narrativa)) if dados.clusters_narrativa is not None else "n/d", "perfis demograficos distintos", ""),
        ("Candidatura", c.nome_urna, c.resultado_final, ""),
    ])
    corpo += ds.callout(
        "Esta e a versao automatica e enxuta do relatorio de estrategia: cobre so o que e "
        "100% calculavel a partir de dado ja oficial (TSE/IBGE/RAIS-CAGED), sem narrativa "
        "manual por zona nem pesquisa de cena cultural/microinfluenciadores por candidato "
        "(ver 'Limitacoes e fontes' ao final).", "O que este relatorio cobre",
    )
    paginas.append(ds.pagina("Resumo executivo", "Relatorio de Estrategia",
                              "Panorama desta versao automatica", corpo, pagina_num=contador_pagina))

    # ------------------------------------------------------- PORTFOLIO DE INVESTIMENTO
    if dados.bairros_potencial is not None and not dados.bairros_potencial.empty:
        contador_pagina += 1
        pot = dados.bairros_potencial
        corpo = ""
        if "Territorios com maior potencial" in dados.figuras:
            corpo += ds.figura_plotly(dados.figuras["Territorios com maior potencial"])
        corpo += ds.tabela_df(pot, max_linhas=15)
        paginas.append(ds.pagina("Portfolio de territorios de investimento", "Fonte: identificar_bairros_potencial",
                                  "Onde o gap real e maior", corpo,
                                  sub="Ranqueado por gap vs. media de territorios com perfil demografico semelhante "
                                      "e, quando disponivel, probabilidade estatistica de boa votacao.",
                                  pagina_num=contador_pagina))

        # --------------------------------------------------- PLANO DE ACAO
        contador_pagina += 1
        col_territorio = pot.columns[0]
        itens_html = "".join(
            f"<li><strong>Prioridade {i + 1} - {row[col_territorio]}:</strong> {row['justificativa']} "
            f"(score de potencial: {row['score_potencial']:.1f})</li>"
            for i, row in pot.reset_index(drop=True).iterrows()
        )
        corpo = (
            "<p>Ordem de prioridade de investimento de esforco de campanha, direto da classificacao "
            "de potencial acima - nao e uma tatica nova, e a mesma analise reapresentada como plano.</p>"
            f"<ul class='tight'>{itens_html}</ul>"
        )
        paginas.append(ds.pagina("Plano de acao priorizado", "Fonte: identificar_bairros_potencial (reapresentado)",
                                  "Por onde comecar", corpo, pagina_num=contador_pagina))

    # ------------------------------------------------------- RIVAIS + PATRIMONIO
    if dados.rivais_similaridade is not None and not dados.rivais_similaridade.empty:
        contador_pagina += 1
        corpo = ds.tabela_df(dados.rivais_similaridade)
        if "Rivais por similaridade de base eleitoral" in dados.figuras:
            corpo += ds.figura_plotly(dados.figuras["Rivais por similaridade de base eleitoral"])
        paginas.append(ds.pagina("Rivais diretos", "Fonte: TSE - rivais_por_similaridade_eleitorado",
                                  "Quem disputa a mesma base territorial", corpo,
                                  sub="Similaridade de distribuicao territorial do voto - nao e volume de votos.",
                                  pagina_num=contador_pagina))

    if dados.patrimonio_comparativo is not None and not dados.patrimonio_comparativo.empty:
        contador_pagina += 1
        corpo = ds.tabela_df(dados.patrimonio_comparativo)
        corpo += ds.callout(
            "Valor total autodeclarado pelo proprio candidato ao TSE - nao e uma auditoria "
            "patrimonial, apenas o que consta oficialmente na candidatura. Uma proxy grosseira "
            "de capacidade de autofinanciamento de campanha, nunca uma medida de forca eleitoral.",
            "Limitacao", "warn",
        )
        paginas.append(ds.pagina("Patrimonio comparativo", "Fonte: TSE - bem_candidato (patrimonio_comparativo)",
                                  "Capacidade declarada de autofinanciamento", corpo, pagina_num=contador_pagina))

    # ------------------------------------------------------- SEGMENTACAO TERRITORIAL
    if dados.clusters_narrativa is not None and not dados.clusters_narrativa.empty:
        contador_pagina += 1
        corpo = ds.tabela_df(dados.clusters_narrativa)
        paginas.append(ds.pagina("Segmentacao territorial", "Fonte: Censo IBGE 2022 - segmentar_territorios",
                                  "Perfis territoriais reais, nao 3 arquetipos genericos", corpo, pagina_num=contador_pagina))

    # ------------------------------------------------------- MASLOW (leitura de necessidades)
    if dados.maslow is not None and dados.maslow.fonte_efeito != "indisponivel":
        contador_pagina += 1
        corpo = f"<p>Fonte do efeito: <strong>{dados.maslow.fonte_efeito}</strong></p>"
        if "Piramide de Maslow" in dados.figuras:
            corpo += ds.figura_plotly(dados.figuras["Piramide de Maslow"])
        mapeadas = dados.maslow.tiers_mapeados
        if mapeadas is not None and not mapeadas.empty:
            colunas = [col for col in ["tier", "label", "variavel", "valor_efeito", "significativo"] if col in mapeadas.columns]
            corpo += ds.tabela_df(mapeadas[colunas] if colunas else mapeadas)
        corpo += ds.callout(
            "Leitura de necessidades por proxy demografico e estatistico (Censo/RAIS-CAGED e "
            "correlacao com o voto) - nunca uma pesquisa de opiniao real sobre pautas prioritarias.",
            "Metodologia", "warn",
        )
        paginas.append(ds.pagina("Leitura de necessidades por territorio", "Fonte: gerar_analise_maslow",
                                  "O que o proprio dado sugere, nao pesquisa de opiniao", corpo, pagina_num=contador_pagina))

    # ------------------------------------------------------- LIMITACOES
    contador_pagina += 1
    limitacoes_todas = list(dados.limitacoes) + limitacoes_gerador()
    corpo = "<ul class='tight'>" + "".join(f"<li>{l}</li>" for l in limitacoes_todas) + "</ul>"
    paginas.append(ds.pagina("Limitacoes e fontes", "Nota final",
                              "O que este relatorio nao sabe, e de onde vem o que ele sabe", corpo,
                              pagina_num=contador_pagina))

    html = ds.head(f"Relatorio de Estrategia SIET - {c.nome_urna}") + "\n".join(paginas)
    return html
