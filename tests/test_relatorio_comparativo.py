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
from src.reports.relatorio_comparativo import (
    _fmt,
    gerar_relatorio_comparativo_html,
    gerar_relatorio_comparativo_pdf,
    gerar_relatorio_comparativo_resumido_html,
    limitacoes_gerador,
)

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


def test_comparativo_usa_fonte_alternativa_para_2018(ranking_sp):
    """Caso real conhecido: SANDERSON RIBEIRO CORREIA DE LIMA disputou
    Deputado Estadual/SP em 2018 (numero 70444, AVANTE, suplente) e
    Deputado Federal/SP em 2022 (numero 2814, PRTB, nao eleito) - mesmo
    nome, mesma UF, sem homonimo. votacao_secao_2018 nao existe no CDN
    oficial do TSE (bloqueado) - precisa achar o comparativo via
    votacao_secao_2018_{UF}.parquet (fonte alternativa via BigQuery, ja
    publicada e plugada em uf_data_bootstrap.py) e nao mais cair no caminho
    "sem territorio"."""
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
    # agora que votacao_secao_2018 existe de verdade (fallback via BigQuery),
    # ate o campo Candidatura.total_votos (preenchido pela checagem normal de
    # votacao_secao) fica correto para 2018 - nao mais preso em 0.
    assert resultado.candidatura_comparavel.total_votos > 0

    dados = DadosRelatorio(
        candidatura=candidatura, resultado_geral=resultado_geral(candidatura, vd, rd), ranking=ranking_sp,
        territorial_indice=calcular_indice_performance(desempenho_territorial(candidatura, vc, vd, rd, _NIVEL), 0.1),
        bairros_agg=None, correlacoes=None, comparativo_historico=resultado,
    )
    html = gerar_relatorio_comparativo_html(dados)
    assert "Duas disputas reais" in html
    assert "2018" in html
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


def test_relatorio_comparativo_resumido_cobre_os_3_cenarios(ranking_sp, tmp_path, candidatura_sp, dados_disputa):
    """Versao Resumida precisa cobrir as 3 situacoes reais possiveis (mesma
    logica ja testada na versao completa), sempre em 1-2 paginas."""
    # caso encontrado com territorio (Garry Deralus, 2024 vs 2022)
    candidatos = buscar_candidatos_disputa(2024, "VEREADOR", "SP", municipio_codigo=71072, turno=1, numero=13010)
    candidatura = candidatos[0]
    vc = votos_da_candidatura(candidatura)
    vd = votos_da_disputa(candidatura)
    rd = registro_candidatos_disputa(candidatura)
    dados_com_territorio, comparativo = _dados_relatorio_com_comparativo(candidatura, vc, vd, rd, ranking_sp)
    assert comparativo.candidatura_comparavel is not None
    html_com_territorio = gerar_relatorio_comparativo_resumido_html(dados_com_territorio)
    assert html_com_territorio.count('<div class="page">') == 1
    assert "Comparativo territorial real encontrado" in html_com_territorio

    # caso nao encontrado (Aline Torres)
    vc2, vd2, rd2 = dados_disputa
    dados_nao_encontrado, comparativo2 = _dados_relatorio_com_comparativo(candidatura_sp, vc2, vd2, rd2, ranking_sp)
    assert comparativo2.candidatura_comparavel is None
    html_nao_encontrado = gerar_relatorio_comparativo_resumido_html(dados_nao_encontrado)
    assert "Nenhuma segunda disputa comparavel encontrada" in html_nao_encontrado

    html_completo = gerar_relatorio_comparativo_html(dados_com_territorio)
    assert html_com_territorio.count('<div class="page">') < html_completo.count('<div class="page">')


def test_pdf_comparativo_com_territorio_gera_arquivo_real(ranking_sp, tmp_path):
    """Mesmo caso real do teste HTML (GARRY DERALUS, 2024 vs 2022, 54 zonas
    em comum) - a versao PDF (ReportLab) precisa gerar um arquivo real e
    nao vazio, cobrindo o ramo com comparativo territorial."""
    candidatos = buscar_candidatos_disputa(2024, "VEREADOR", "SP", municipio_codigo=71072, turno=1, numero=13010)
    candidatura = candidatos[0]
    vc = votos_da_candidatura(candidatura)
    vd = votos_da_disputa(candidatura)
    rd = registro_candidatos_disputa(candidatura)

    dados, comparativo = _dados_relatorio_com_comparativo(candidatura, vc, vd, rd, ranking_sp)
    assert comparativo.candidatura_comparavel is not None

    caminho = gerar_relatorio_comparativo_pdf(dados, tmp_path / "comparativo_com_territorio.pdf")
    assert caminho.exists()
    assert caminho.stat().st_size > 1000


def test_pdf_comparativo_degrada_graciosamente_quando_nao_encontra_segunda_disputa(
    candidatura_sp, dados_disputa, ranking_sp, tmp_path
):
    """Mesmo caso real do teste HTML (ALINE TORRES, sem segunda disputa) -
    a versao PDF precisa gerar um arquivo real, mesmo no ramo sem
    comparativo (nunca inventa trajetoria nem quebra)."""
    vc, vd, rd = dados_disputa
    dados, comparativo = _dados_relatorio_com_comparativo(candidatura_sp, vc, vd, rd, ranking_sp)
    assert comparativo.candidatura_comparavel is None

    caminho = gerar_relatorio_comparativo_pdf(dados, tmp_path / "comparativo_nao_encontrado.pdf")
    assert caminho.exists()
    assert caminho.stat().st_size > 500


def test_pdf_comparativo_funciona_sem_campo_preenchido(candidatura_sp, dados_disputa, ranking_sp, tmp_path):
    """comparativo_historico=None precisa degradar graciosamente na versao
    PDF tambem, igual a versao HTML."""
    vc, vd, rd = dados_disputa
    rg = resultado_geral(candidatura_sp, vd, rd)
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, _NIVEL)
    indice_terr = calcular_indice_performance(terr, 0.1)
    dados = DadosRelatorio(
        candidatura=candidatura_sp, resultado_geral=rg, ranking=ranking_sp,
        territorial_indice=indice_terr, bairros_agg=None, correlacoes=None,
    )
    caminho = gerar_relatorio_comparativo_pdf(dados, tmp_path / "comparativo_sem_campo.pdf")
    assert caminho.exists()
    assert caminho.stat().st_size > 500
