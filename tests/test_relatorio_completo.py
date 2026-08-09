import pandas as pd
from conftest import VARIAVEIS_DEMOGRAFICAS

from src.competitor_analysis import ranking_disputa, rivais_por_similaridade_eleitorado, zonas_de_disputa
from src.electoral_metrics import desempenho_territorial, resultado_geral
from src.potential_index import calcular_indice_performance
from src.projections.monte_carlo import cenario_agregado_votos, simular_regressao_linear
from src.regression_models import regressao_linear_votos
from src.report_generator import DadosRelatorio
from src.reports.relatorio_completo import (
    gerar_relatorio_completo_html,
    gerar_relatorio_resumido_html,
    limitacoes_gerador,
)
from src.state_scope_indicators import calcular_concentracao_territorial

_NIVEL = "NR_ZONA"


def _construir_dados_relatorio(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp) -> DadosRelatorio:
    vc, vd, rd = dados_disputa
    rg = resultado_geral(candidatura_sp, vd, rd)
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, _NIVEL)
    zonas_disp = zonas_de_disputa(terr, vd, rd, candidatura_sp, _NIVEL)
    concentracao = calcular_concentracao_territorial(terr)
    indice_terr = calcular_indice_performance(zonas_disp, concentracao.hhi)
    rivais, _ = rivais_por_similaridade_eleitorado(candidatura_sp, vd, rd, _NIVEL, top_n=5)

    reg, _ = regressao_linear_votos(base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS)
    cenario = None
    simulacao = None
    if reg is not None:
        simulacao = simular_regressao_linear(reg, base_territorio_sp, "local_votacao_id", n_simulacoes=300)
        if simulacao is not None:
            cenario = cenario_agregado_votos(simulacao, base_territorio_sp, "local_votacao_id", "votos_validos_territorio")

    return DadosRelatorio(
        candidatura=candidatura_sp, resultado_geral=rg, ranking=ranking_sp,
        territorial_indice=indice_terr, bairros_agg=None, correlacoes=None,
        rivais_similaridade=rivais, zonas_disputa=zonas_disp, concentracao_territorial=concentracao,
        regressao_linear=reg, cenario_monte_carlo=cenario, simulacao_monte_carlo=simulacao,
    )


def test_gerar_relatorio_completo_produz_html_com_multiplas_paginas(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp):
    dados = _construir_dados_relatorio(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp)
    html = gerar_relatorio_completo_html(dados)
    assert html.count('class="page') >= 6, "relatorio deveria ter pelo menos capa + varias secoes de dado real"
    assert candidatura_sp.nome_urna in html
    assert "plotly" in html.lower()


def test_gerar_relatorio_completo_nunca_fabrica_biografia_ou_midia(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp):
    """Guarda de regressao central deste modulo: um gerador automatico
    nunca deve fingir ter secoes de biografia/midia/trajetoria historica -
    essas exigem pesquisa real por candidato, fora do escopo deste
    modulo (ver nota metodologica em relatorio_completo.py)."""
    dados = _construir_dados_relatorio(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp)
    html = gerar_relatorio_completo_html(dados)
    for termo_proibido in ("Biografia", "Repercussão na mídia", "Trajetória eleitoral completa"):
        assert termo_proibido not in html


def test_limitacoes_gerador_e_sempre_incluida_no_html(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp):
    dados = _construir_dados_relatorio(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp)
    html = gerar_relatorio_completo_html(dados)
    for limitacao in limitacoes_gerador():
        assert limitacao in html


def test_gerar_relatorio_completo_funciona_com_dados_minimos(candidatura_sp, dados_disputa, ranking_sp):
    """Nem toda candidatura tem regressao/territorio/concentracao
    disponiveis (amostra pequena, malha ausente) - o gerador precisa
    degradar graciosamente, nunca quebrar, com so os campos obrigatorios
    de DadosRelatorio preenchidos."""
    vc, vd, rd = dados_disputa
    rg = resultado_geral(candidatura_sp, vd, rd)
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, _NIVEL)
    indice_terr = calcular_indice_performance(terr, 0.1)
    dados_minimos = DadosRelatorio(
        candidatura=candidatura_sp, resultado_geral=rg, ranking=ranking_sp,
        territorial_indice=indice_terr, bairros_agg=None, correlacoes=None,
    )
    html = gerar_relatorio_completo_html(dados_minimos)
    assert candidatura_sp.nome_urna in html
    assert html.count('class="page') >= 3


def test_cenario_monte_carlo_aparece_no_html_quando_disponivel(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp):
    dados = _construir_dados_relatorio(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp)
    html = gerar_relatorio_completo_html(dados)
    if dados.cenario_monte_carlo is not None:
        assert "Cenarios de votos (Monte Carlo)" in html
        assert "Simulacao de Monte Carlo PARAMETRICA" in html


def test_gerar_relatorio_resumido_e_bem_menor_que_o_completo(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp):
    """Item 1 das melhorias pos-Etapa 8: versao Resumida precisa ser
    genuinamente menor (1-2 paginas) que a Completa (~10+ paginas com
    dado real), nao um sinonimo do mesmo conteudo."""
    dados = _construir_dados_relatorio(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp)
    html_completo = gerar_relatorio_completo_html(dados)
    html_resumido = gerar_relatorio_resumido_html(dados)
    assert candidatura_sp.nome_urna in html_resumido
    assert html_resumido.count('<div class="page">') == 1  # capa + 1 pagina de conteudo
    assert html_resumido.count('<div class="page">') < html_completo.count('<div class="page">')
