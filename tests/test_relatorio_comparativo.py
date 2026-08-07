from src.candidate_finder import (
    buscar_candidatos_disputa,
    registro_candidatos_disputa,
    registro_candidatos_disputa_generalizado,
    votos_da_candidatura,
    votos_da_candidatura_generalizado,
    votos_da_disputa,
    votos_da_disputa_generalizado,
)
from src.candidate_history import montar_comparativo_historico
from src.electoral_metrics import resultado_geral
from src.potential_index import calcular_indice_performance
from src.electoral_metrics import desempenho_territorial
from src.report_generator import DadosRelatorio
from src.reports.relatorio_comparativo import _fmt, gerar_relatorio_comparativo_html, limitacoes_gerador

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


def test_comparativo_usa_fonte_alternativa_munzona_para_2018(ranking_sp):
    """Caso real conhecido: SANDERSON RIBEIRO CORREIA DE LIMA disputou
    Deputado Estadual/SP em 2018 (numero 70444, AVANTE, suplente) e
    Deputado Federal/SP em 2022 (numero 2814, PRTB, nao eleito) - mesmo
    nome, mesma UF, sem homonimo. votacao_secao_2018 nao existe (o TSE
    bloqueia o download oficial) - precisa achar o comparativo via
    votacao_candidato_munzona_2018_BR.parquet (fonte alternativa, ja
    convertida e publicada) e nao mais cair no caminho "sem territorio"."""
    candidatos = buscar_candidatos_disputa(2022, "DEPUTADO FEDERAL", "SP", turno=1, numero=2814)
    candidatura = candidatos[0]
    vc = votos_da_candidatura_generalizado(candidatura)
    vd = votos_da_disputa_generalizado(candidatura)
    rd = registro_candidatos_disputa_generalizado(candidatura)

    resultado = montar_comparativo_historico(candidatura, vc, vd, rd, ano_alvo=2018)
    assert resultado.candidatura_comparavel is not None
    assert resultado.candidatura_comparavel.ano_eleicao == 2018
    assert resultado.n_zonas_comuns > 0
    assert resultado.correlacao_territorial is not None
    assert resultado.votos_totais_comparavel is not None and resultado.votos_totais_comparavel > 0

    dados = DadosRelatorio(
        candidatura=candidatura, resultado_geral=resultado_geral(candidatura, vd, rd), ranking=ranking_sp,
        territorial_indice=calcular_indice_performance(desempenho_territorial(candidatura, vc, vd, rd, _NIVEL), 0.1),
        bairros_agg=None, correlacoes=None, comparativo_historico=resultado,
    )
    html = gerar_relatorio_comparativo_html(dados)
    assert "Duas disputas reais" in html
    assert "2018" in html
    # o total de votos de 2018 precisa vir do dado real ja carregado (via
    # votos_totais_comparavel), nunca do campo Candidatura.total_votos (que
    # fica 0 para 2018, ja que so e preenchido por uma checagem de
    # votacao_secao que sempre falha para este ano).
    assert resultado.candidatura_comparavel.total_votos == 0
    assert _fmt(resultado.votos_totais_comparavel) in html


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
