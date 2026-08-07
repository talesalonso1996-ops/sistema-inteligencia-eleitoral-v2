from src.candidate_finder import buscar_candidatos_disputa, registro_candidatos_disputa, votos_da_candidatura, votos_da_disputa
from src.candidate_history import montar_comparativo_historico
from src.electoral_metrics import resultado_geral
from src.potential_index import calcular_indice_performance
from src.electoral_metrics import desempenho_territorial
from src.report_generator import DadosRelatorio
from src.reports.relatorio_comparativo import gerar_relatorio_comparativo_html, limitacoes_gerador

_NIVEL = "NR_ZONA"


def _dados_relatorio_com_comparativo(candidatura, vc, vd, rd, ranking) -> DadosRelatorio:
    rg = resultado_geral(candidatura, vd, rd)
    terr = desempenho_territorial(candidatura, vc, vd, rd, _NIVEL)
    indice_terr = calcular_indice_performance(terr, 0.1)
    comparativo = montar_comparativo_historico(candidatura, vc, vd, rd)
    return DadosRelatorio(
        candidatura=candidatura, resultado_geral=rg, ranking=ranking,
        territorial_indice=indice_terr, bairros_agg=None, correlacoes=None,
        comparativo_historico=comparativo,
    ), comparativo


def test_comparativo_encontra_segunda_disputa_real_e_gera_secao_de_continuidade(ranking_sp):
    """Caso real conhecido: GARRY DERALUS disputou Deputado Estadual/SP em
    2022 (numero 13100, PT, suplente) e Vereador/Sao Paulo em 2024 (numero
    13010, PT, suplente) - mesmo nome, mesma UF, sem homonimo. Precisa
    achar o comparativo real com dado territorial (54 zonas em comum,
    correlacao ~0.79 - conferido manualmente antes deste teste)."""
    candidatos = buscar_candidatos_disputa(2024, "VEREADOR", "SP", municipio_codigo=71072, turno=1, numero=13010)
    candidatura = candidatos[0]
    vc = votos_da_candidatura(candidatura)
    vd = votos_da_disputa(candidatura)
    rd = registro_candidatos_disputa(candidatura)

    dados, comparativo = _dados_relatorio_com_comparativo(candidatura, vc, vd, rd, ranking_sp)
    assert comparativo.candidatura_comparavel is not None
    assert comparativo.candidatura_comparavel.ano_eleicao == 2022
    assert comparativo.n_zonas_comuns > 0
    assert comparativo.correlacao_territorial is not None

    html = gerar_relatorio_comparativo_html(dados)
    assert "Duas disputas reais" in html
    assert "Zona a zona" in html
    assert "2022" in html and "2024" in html


def test_comparativo_degrada_graciosamente_quando_nao_encontra_segunda_disputa(candidatura_sp, dados_disputa, ranking_sp):
    """ALINE TORRES (15900) nao tem segunda candidatura real conhecida em
    2022/SP - o relatorio precisa explicar isso, nunca inventar uma
    trajetoria ou quebrar."""
    vc, vd, rd = dados_disputa
    dados, comparativo = _dados_relatorio_com_comparativo(candidatura_sp, vc, vd, rd, ranking_sp)
    assert comparativo.candidatura_comparavel is None

    html = gerar_relatorio_comparativo_html(dados)
    assert "Segunda candidatura nao encontrada" in html
    assert candidatura_sp.nome_urna in html
    assert "Duas disputas reais" not in html
    assert "Zona a zona" not in html


def test_limitacoes_gerador_e_sempre_incluida_no_html(candidatura_sp, dados_disputa, ranking_sp):
    vc, vd, rd = dados_disputa
    dados, _ = _dados_relatorio_com_comparativo(candidatura_sp, vc, vd, rd, ranking_sp)
    html = gerar_relatorio_comparativo_html(dados)
    for limitacao in limitacoes_gerador():
        assert limitacao in html


def test_gerar_relatorio_comparativo_funciona_sem_campo_preenchido(candidatura_sp, dados_disputa, ranking_sp):
    """comparativo_historico=None (campo aditivo nunca preenchido) precisa
    degradar graciosamente, igual a quando a busca roda e nao acha nada."""
    vc, vd, rd = dados_disputa
    rg = resultado_geral(candidatura_sp, vd, rd)
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, _NIVEL)
    indice_terr = calcular_indice_performance(terr, 0.1)
    dados = DadosRelatorio(
        candidatura=candidatura_sp, resultado_geral=rg, ranking=ranking_sp,
        territorial_indice=indice_terr, bairros_agg=None, correlacoes=None,
    )
    html = gerar_relatorio_comparativo_html(dados)
    assert candidatura_sp.nome_urna in html
    assert html.count('class="page') >= 3
