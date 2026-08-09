import dataclasses

from src import charts
from src.economic_analysis import PerfilEconomicoMunicipio
from src.electoral_metrics import desempenho_territorial, resultado_geral
from src.potential_index import calcular_indice_performance
from src.report_generator import DadosRelatorio, gerar_relatorio_html, gerar_relatorio_pdf
from src.reports.relatorio_comparativo import gerar_relatorio_comparativo_pdf
from src.reports.relatorio_estrategia import gerar_relatorio_estrategia_pdf

_NIVEL = "NR_ZONA"


def _perfil_economico_disponivel_sem_caged() -> PerfilEconomicoMunicipio:
    """Caso real possivel: municipio com RAIS (vinculos formais) mas SEM
    linha no CAGED 2024 - disponivel=True (rais OU caged, nao "e"), mas
    saldo_caged_2024/admissoes_2024/desligamentos_2024 ficam None. Bug
    real corrigido: o format-spec ':+,' em None quebrava a geracao do
    relatorio (HTML/PDF) e do grafico inteiros para esse candidato."""
    return PerfilEconomicoMunicipio(
        codigo_municipio_rais="123456",
        vinculos_ativos_total=5000,
        estabelecimentos_ativos=300,
        saldo_caged_2024=None,
        admissoes_2024=None,
        desligamentos_2024=None,
        tendencia="indisponivel",
        disponivel=True,
    )


def _dados_minimos_com_perfil_economico(candidatura_sp, dados_disputa, ranking_sp, perfil_economico):
    vc, vd, rd = dados_disputa
    rg = resultado_geral(candidatura_sp, vd, rd)
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, _NIVEL)
    indice_terr = calcular_indice_performance(terr, 0.1)
    return DadosRelatorio(
        candidatura=candidatura_sp, resultado_geral=rg, ranking=ranking_sp,
        territorial_indice=indice_terr, bairros_agg=None, correlacoes=None,
        perfil_economico=perfil_economico,
    )


def test_gerar_relatorio_html_nao_quebra_com_saldo_caged_none(candidatura_sp, dados_disputa, ranking_sp):
    dados = _dados_minimos_com_perfil_economico(candidatura_sp, dados_disputa, ranking_sp, _perfil_economico_disponivel_sem_caged())
    html = gerar_relatorio_html(dados)
    assert "n/d" in html


def test_gerar_relatorio_pdf_nao_quebra_com_saldo_caged_none(candidatura_sp, dados_disputa, ranking_sp, tmp_path):
    dados = _dados_minimos_com_perfil_economico(candidatura_sp, dados_disputa, ranking_sp, _perfil_economico_disponivel_sem_caged())
    caminho = gerar_relatorio_pdf(dados, tmp_path / "relatorio_saldo_none.pdf")
    assert caminho.exists()
    assert caminho.stat().st_size > 500


def test_grafico_perfil_economico_nao_quebra_com_saldo_caged_none():
    fig = charts.grafico_perfil_economico_municipio(_perfil_economico_disponivel_sem_caged())
    assert "n/d" in fig.layout.annotations[0].text


def test_pdf_generators_nao_quebram_com_tag_malformada_no_partido(candidatura_sp, dados_disputa, ranking_sp, tmp_path):
    """ReportLab Paragraph interpreta um mini-XML e NAO escapa sozinho -
    confirmado manualmente que um "&"/"<"/">" isolado NAO quebra (o parser
    e tolerante a isso), mas um valor vindo do TSE que por acaso contenha
    algo que parece uma tag (ex.: um "</b>" literal dentro do texto, que
    colide com o "<b>...</b>" que o proprio gerador usa ao redor do nome)
    quebra a geracao do PDF inteiro com ValueError/parse error - testado
    e confirmado antes de escrever este teste. Testa os 3 geradores de
    PDF (Tipo 1/2/3) com um partido_sigla fabricado contendo essa tag."""
    candidatura_com_e = dataclasses.replace(candidatura_sp, partido_sigla="PSDB</b>PL")
    vc, vd, rd = dados_disputa
    rg = resultado_geral(candidatura_com_e, vd, rd)
    terr = desempenho_territorial(candidatura_com_e, vc, vd, rd, _NIVEL)
    indice_terr = calcular_indice_performance(terr, 0.1)
    dados = DadosRelatorio(
        candidatura=candidatura_com_e, resultado_geral=rg, ranking=ranking_sp,
        territorial_indice=indice_terr, bairros_agg=None, correlacoes=None,
    )

    for gerar, nome in (
        (gerar_relatorio_pdf, "tipo1.pdf"),
        (gerar_relatorio_estrategia_pdf, "tipo2.pdf"),
        (gerar_relatorio_comparativo_pdf, "tipo3.pdf"),
    ):
        caminho = gerar(dados, tmp_path / nome)
        assert caminho.exists()
        assert caminho.stat().st_size > 500
