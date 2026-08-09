"""Relatorio Aprofundado (Tipo 4, melhorias pos-Etapa 8) - vai alem do
Tipo 1 Completo, cobrindo o que ele deliberadamente NAO inclui hoje: os 4
indices de desempenho eleitoral real (IDP/IVE/IEC/QEC,
src/indicators/candidate_performance_indices.py, Etapa 9) comparando o
candidato-alvo com seus rivais reais por similaridade de base eleitoral -
ate agora so exibidos ao vivo na secao "Concorrencia" do app, nunca antes
incluidos em nenhum dos 3 relatorios exportaveis.

Reaproveita literalmente as ~14 secoes do Tipo 1 (`relatorio_completo._montar_paginas`)
e injeta 1 secao nova antes de "Limitacoes e fontes" - nenhuma logica
duplicada, nenhum indice novo inventado (mesma formula ja validada na
Etapa 9, mesmo limite metodologico ja documentado em
config/indicators.yaml sobre QEC em disputas proporcionais)."""
from __future__ import annotations

from . import design_system as ds
from . import relatorio_completo
from ..report_generator import DadosRelatorio


def limitacoes_gerador() -> list[str]:
    return relatorio_completo.limitacoes_gerador() + [
        "Os indices IDP/IVE/IEC/QEC medem desempenho eleitoral REAL observavel (colocacao, "
        "concentracao territorial, cobertura, solidez das vitorias) - nunca a qualidade da "
        "decisao estrategica do candidato, que exigiria julgamento subjetivo fora do escopo de "
        "um indice automatico.",
    ]


def _pagina_desempenho(dados: DadosRelatorio, contador_pagina: int) -> str | None:
    if not dados.indices_desempenho_candidato:
        return None
    idx = dados.indices_desempenho_candidato
    corpo = ds.kpi_grid([
        ("IDP - Desempenho Politico", f"{idx.get('IDP', 0):.0f}", "quanto maior, melhor", ""),
        ("IVE - Vulnerabilidade Eleitoral", f"{idx.get('IVE', 0):.0f}", "quanto maior, PIOR", "red"),
        ("IEC - Eficiencia de Campanha", f"{idx.get('IEC', 0):.0f}", "quanto maior, melhor", ""),
        ("QEC - Qualidade da Estrategia", f"{idx.get('QEC', 0):.0f}", "solidez das vitorias territoriais", ""),
    ])
    corpo += ds.callout(
        "4 indices calculados a partir do resultado eleitoral REAL de cada candidato na mesma "
        "disputa - nunca uma estimativa ou percepcao subjetiva. QEC tende a ficar perto de zero "
        "em disputas proporcionais concorridas (muitos candidatos fortes), onde 'dominar' um "
        "territorio com folga e raro mesmo para o 1o colocado - ver metodologia completa em "
        "config/indicators.yaml.", "Metodologia", "warn",
    )
    if "Desempenho eleitoral real (IDP/IVE/IEC/QEC)" in dados.figuras:
        corpo += ds.figura_plotly(dados.figuras["Desempenho eleitoral real (IDP/IVE/IEC/QEC)"])
    if dados.indices_desempenho_rivais is not None and not dados.indices_desempenho_rivais.empty:
        corpo += ds.tabela_df(dados.indices_desempenho_rivais)
    return ds.pagina(
        "Desempenho eleitoral real", "Fonte: TSE - candidate_performance_indices",
        "IDP / IVE / IEC / QEC - candidato x rivais", corpo, pagina_num=contador_pagina,
    )


def gerar_relatorio_aprofundado_html(dados: DadosRelatorio) -> str:
    c = dados.candidatura
    paginas, contador_pagina = relatorio_completo._montar_paginas(dados)

    pagina_desempenho = _pagina_desempenho(dados, contador_pagina + 1)
    if pagina_desempenho is not None:
        contador_pagina += 1
        paginas.append(pagina_desempenho)

    contador_pagina += 1
    limitacoes_todas = list(dados.limitacoes) + limitacoes_gerador()
    corpo = "<ul class='tight'>" + "".join(f"<li>{limitacao}</li>" for limitacao in limitacoes_todas) + "</ul>"
    paginas.append(ds.pagina(
        "Limitacoes e fontes", "Nota final",
        "O que este relatorio nao sabe, e de onde vem o que ele sabe", corpo, pagina_num=contador_pagina,
    ))

    html = ds.head(f"Relatorio Aprofundado SIET - {c.nome_urna}") + "\n".join(paginas)
    return html
