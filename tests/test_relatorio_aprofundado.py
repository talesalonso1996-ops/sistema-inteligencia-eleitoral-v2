import dataclasses

import pandas as pd

from src import charts
from src.competitor_analysis import ranking_disputa, rivais_por_similaridade_eleitorado, zonas_de_disputa
from src.electoral_metrics import desempenho_territorial, resultado_geral
from src.indicators.candidate_performance_indices import calcular_indices_desempenho_real
from src.potential_index import calcular_indice_performance
from src.report_generator import DadosRelatorio
from src.reports import relatorio_completo
from src.reports.relatorio_aprofundado import gerar_relatorio_aprofundado_html, limitacoes_gerador
from src.state_scope_indicators import calcular_concentracao_territorial

_NIVEL = "NR_ZONA"


def _construir_dados_relatorio_com_desempenho(candidatura_sp, dados_disputa, ranking_sp) -> DadosRelatorio:
    vc, vd, rd = dados_disputa
    rg = resultado_geral(candidatura_sp, vd, rd)
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, _NIVEL)
    zonas_disp = zonas_de_disputa(terr, vd, rd, candidatura_sp, _NIVEL)
    concentracao = calcular_concentracao_territorial(terr)
    indice_terr = calcular_indice_performance(zonas_disp, concentracao.hhi)
    rivais, _ = rivais_por_similaridade_eleitorado(candidatura_sp, vd, rd, _NIVEL, top_n=3)

    indices_candidato = calcular_indices_desempenho_real(candidatura_sp, vc, vd, rd, _NIVEL)
    nomes_radar = [candidatura_sp.nome_urna]
    valores_radar = [indices_candidato.valores()]
    linhas_rivais = [{"nome_urna": candidatura_sp.nome_urna, **indices_candidato.valores()}]
    for linha in rivais.itertuples():
        vc_rival = vd[vd["NR_VOTAVEL"] == int(linha.numero)]
        if vc_rival.empty:
            continue
        # Mesmo padrao ja usado na secao "Concorrencia" do app.py: constroi
        # uma Candidatura real do rival (mesmo numero) para que
        # calcular_indices_desempenho_real filtre/calcule pelo rival certo,
        # nao pelo candidato-alvo.
        candidatura_rival = dataclasses.replace(
            candidatura_sp, numero=int(linha.numero), nome_urna=linha.nome_urna,
            nome_completo=linha.nome_urna, total_votos=int(linha.total_votos_rival),
        )
        indices_rival = calcular_indices_desempenho_real(candidatura_rival, vc_rival, vd, rd, _NIVEL)
        nomes_radar.append(linha.nome_urna)
        valores_radar.append(indices_rival.valores())
        linhas_rivais.append({"nome_urna": linha.nome_urna, **indices_rival.valores()})

    figuras = {}
    if len(nomes_radar) > 1:
        figuras["Desempenho eleitoral real (IDP/IVE/IEC/QEC)"] = charts.grafico_radar_desempenho(nomes_radar, valores_radar)

    return DadosRelatorio(
        candidatura=candidatura_sp, resultado_geral=rg, ranking=ranking_sp,
        territorial_indice=indice_terr, bairros_agg=None, correlacoes=None,
        rivais_similaridade=rivais, zonas_disputa=zonas_disp, concentracao_territorial=concentracao,
        figuras=figuras,
        indices_desempenho_candidato=indices_candidato.valores(),
        indices_desempenho_rivais=pd.DataFrame(linhas_rivais),
    )


def test_gerar_relatorio_aprofundado_inclui_secao_de_desempenho(candidatura_sp, dados_disputa, ranking_sp):
    dados = _construir_dados_relatorio_com_desempenho(candidatura_sp, dados_disputa, ranking_sp)
    html = gerar_relatorio_aprofundado_html(dados)
    assert "Desempenho eleitoral real" in html
    assert "IDP" in html and "IVE" in html and "IEC" in html and "QEC" in html
    assert candidatura_sp.nome_urna in html


def _titulos_das_secoes(html: str) -> list[str]:
    """Extrai o rotulo (running-head) de cada pagina .page - mais preciso
    que contar 'class="page' (que tambem casa com 'class="page-body"' e
    'class="page cover"', inflando a contagem por pagina)."""
    import re

    return re.findall(r'<span>([^<]+)</span></div>\s*<div class="page-body">', html)


def test_gerar_relatorio_aprofundado_reaproveita_todas_as_secoes_do_tipo1(candidatura_sp, dados_disputa, ranking_sp):
    """O Tipo 4 precisa ter TODAS as secoes do Tipo 1 (nenhuma secao
    perdida no refactor de relatorio_completo._montar_paginas), na MESMA
    ordem, mais a secao nova de desempenho inserida antes de
    'Limitacoes e fontes' - nunca menos secoes que o Tipo 1."""
    dados = _construir_dados_relatorio_com_desempenho(candidatura_sp, dados_disputa, ranking_sp)
    html_tipo1 = relatorio_completo.gerar_relatorio_completo_html(dados)
    html_tipo4 = gerar_relatorio_aprofundado_html(dados)
    titulos1 = _titulos_das_secoes(html_tipo1)
    titulos4 = _titulos_das_secoes(html_tipo4)

    assert titulos1[-1] == "Limitacoes e fontes"
    assert titulos4[-1] == "Limitacoes e fontes"
    assert titulos4[-2] == "Desempenho eleitoral real"
    # todas as secoes do Tipo 1 (exceto a ultima, "Limitacoes") continuam
    # presentes e na mesma ordem no Tipo 4
    assert titulos4[:-2] == titulos1[:-1]


def test_relatorio_aprofundado_funciona_sem_indices_de_desempenho(candidatura_sp, dados_disputa, ranking_sp):
    """Campo aditivo - se indices_desempenho_candidato nao foi calculado
    (candidatura antiga, chamador que nao preencheu), o Tipo 4 degrada
    graciosamente (pula a secao nova), nunca quebra."""
    vc, vd, rd = dados_disputa
    rg = resultado_geral(candidatura_sp, vd, rd)
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, _NIVEL)
    indice_terr = calcular_indice_performance(terr, 0.1)
    dados_minimos = DadosRelatorio(
        candidatura=candidatura_sp, resultado_geral=rg, ranking=ranking_sp,
        territorial_indice=indice_terr, bairros_agg=None, correlacoes=None,
    )
    html = gerar_relatorio_aprofundado_html(dados_minimos)
    assert candidatura_sp.nome_urna in html
    assert "Desempenho eleitoral real" not in html


def test_limitacoes_gerador_inclui_limitacoes_do_tipo1_e_do_idp(candidatura_sp, dados_disputa, ranking_sp):
    dados = _construir_dados_relatorio_com_desempenho(candidatura_sp, dados_disputa, ranking_sp)
    html = gerar_relatorio_aprofundado_html(dados)
    for limitacao in limitacoes_gerador():
        assert limitacao in html
    for limitacao in relatorio_completo.limitacoes_gerador():
        assert limitacao in html
