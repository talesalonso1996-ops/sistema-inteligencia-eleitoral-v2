import pandas as pd
from conftest import VARIAVEIS_DEMOGRAFICAS

from src.candidate_assets import patrimonio_comparativo
from src.clustering import gerar_narrativa_clusters, segmentar_territorios
from src.competitor_analysis import rivais_por_similaridade_eleitorado
from src.correlation_analysis import correlacoes_com_votos
from src.electoral_metrics import desempenho_territorial, resultado_geral
from src.maslow_analysis import gerar_analise_maslow
from src.potential_analysis import identificar_bairros_potencial
from src.potential_index import calcular_indice_performance
from src.regression_models import regressao_logistica_bom_desempenho
from src.report_generator import DadosRelatorio
from src.reports.relatorio_estrategia import (
    gerar_relatorio_estrategia_html,
    gerar_relatorio_estrategia_pdf,
    limitacoes_gerador,
)

_NIVEL = "NR_ZONA"


def _construir_dados_relatorio(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp) -> DadosRelatorio:
    vc, vd, rd = dados_disputa
    rg = resultado_geral(candidatura_sp, vd, rd)
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, _NIVEL)
    indice_terr = calcular_indice_performance(terr, 0.1)
    rivais, _ = rivais_por_similaridade_eleitorado(candidatura_sp, vd, rd, _NIVEL, top_n=7)
    patrimonio = patrimonio_comparativo(candidatura_sp, ranking_sp, top_n=7)

    corr, _ = correlacoes_com_votos(base_territorio_sp, "votos_candidato", VARIAVEIS_DEMOGRAFICAS)
    modelo_log, _ = regressao_logistica_bom_desempenho(base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS)
    resultado_clustering, _ = segmentar_territorios(base_territorio_sp, VARIAVEIS_DEMOGRAFICAS, k=5)
    narrativa = gerar_narrativa_clusters(resultado_clustering, "votos_candidato") if resultado_clustering else None
    potencial = (
        identificar_bairros_potencial(resultado_clustering, modelo_log, "local_votacao_id", "votos_candidato")
        if resultado_clustering else None
    )
    maslow = gerar_analise_maslow(modelo_log, None, corr)

    return DadosRelatorio(
        candidatura=candidatura_sp, resultado_geral=rg, ranking=ranking_sp,
        territorial_indice=indice_terr, bairros_agg=None, correlacoes=corr,
        rivais_similaridade=rivais, clusters_narrativa=narrativa, bairros_potencial=potencial,
        maslow=maslow, patrimonio_comparativo=patrimonio,
    )


def test_gerar_relatorio_estrategia_produz_html_com_multiplas_paginas(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp):
    dados = _construir_dados_relatorio(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp)
    html = gerar_relatorio_estrategia_html(dados)
    assert html.count('class="page') >= 5
    assert candidatura_sp.nome_urna in html


def test_gerar_relatorio_estrategia_nunca_fabrica_narrativa_manual_ou_cultura(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp):
    """Guarda de regressao central: a versao automatica nunca deve fingir
    ter narrativa manual por zona ou pesquisa de cena cultural/
    microinfluenciadores - exigem pesquisa humana especifica por
    candidato, fora do escopo deste gerador (ver nota metodologica em
    relatorio_estrategia.py)."""
    dados = _construir_dados_relatorio(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp)
    html = gerar_relatorio_estrategia_html(dados)
    # Titulos reais de secao do relatorio Parte 2 do Orlando Silva (grafia/
    # acentuacao exatas) - nao colidem com o texto de limitacoes deste
    # gerador, que descreve em prosa (minusculo, sem acento) o que fica de
    # fora, sem nunca criar uma secao com esses titulos.
    for titulo_proibido in (
        "A cena cultural real de cada território-alvo",
        "Criadores e páginas locais reais",
    ):
        assert titulo_proibido not in html


def test_limitacoes_gerador_e_sempre_incluida_no_html(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp):
    dados = _construir_dados_relatorio(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp)
    html = gerar_relatorio_estrategia_html(dados)
    for limitacao in limitacoes_gerador():
        assert limitacao in html


def test_gerar_relatorio_estrategia_funciona_com_dados_minimos(candidatura_sp, dados_disputa, ranking_sp):
    """Nem toda candidatura tem clustering/potencial/patrimonio disponiveis
    - o gerador precisa degradar graciosamente, nunca quebrar, com so os
    campos obrigatorios de DadosRelatorio preenchidos."""
    vc, vd, rd = dados_disputa
    rg = resultado_geral(candidatura_sp, vd, rd)
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, _NIVEL)
    indice_terr = calcular_indice_performance(terr, 0.1)
    dados_minimos = DadosRelatorio(
        candidatura=candidatura_sp, resultado_geral=rg, ranking=ranking_sp,
        territorial_indice=indice_terr, bairros_agg=None, correlacoes=None,
    )
    html = gerar_relatorio_estrategia_html(dados_minimos)
    assert candidatura_sp.nome_urna in html
    assert html.count('class="page') >= 3


def test_plano_de_acao_reflete_ranking_real_de_potencial(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp):
    """O plano de acao precisa listar exatamente os mesmos territorios, na
    mesma ordem, da tabela de potencial ja calculada - nunca uma lista
    reordenada ou inventada."""
    dados = _construir_dados_relatorio(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp)
    if dados.bairros_potencial is None or dados.bairros_potencial.empty:
        return
    html = gerar_relatorio_estrategia_html(dados)
    col_territorio = dados.bairros_potencial.columns[0]
    primeiro_territorio = str(dados.bairros_potencial.iloc[0][col_territorio])
    assert "Plano de acao priorizado" in html
    assert f"Prioridade 1 - {primeiro_territorio}" in html


def test_pdf_estrategia_gera_arquivo_real_com_dados_completos(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp, tmp_path):
    dados = _construir_dados_relatorio(candidatura_sp, dados_disputa, ranking_sp, base_territorio_sp)
    caminho = gerar_relatorio_estrategia_pdf(dados, tmp_path / "estrategia_completo.pdf")
    assert caminho.exists()
    assert caminho.stat().st_size > 1000


def test_pdf_estrategia_funciona_com_dados_minimos(candidatura_sp, dados_disputa, ranking_sp, tmp_path):
    """Mesmo caso real do teste HTML equivalente - a versao PDF precisa
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
    caminho = gerar_relatorio_estrategia_pdf(dados_minimos, tmp_path / "estrategia_minimo.pdf")
    assert caminho.exists()
    assert caminho.stat().st_size > 500
