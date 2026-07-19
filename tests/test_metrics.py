from src.electoral_metrics import desempenho_territorial, indice_concentracao_hhi, resultado_geral
from src.potential_index import calcular_indice_performance
from src.competitor_analysis import zonas_de_disputa


def test_resultado_geral_consistencia(candidatura_sp, dados_disputa):
    vc, vd, rd = dados_disputa
    rg = resultado_geral(candidatura_sp, vd, rd)

    assert rg.total_votos == candidatura_sp.total_votos
    assert 1 <= rg.colocacao_geral <= rg.total_concorrentes
    assert 0 <= rg.pct_votos_validos <= 100
    assert rg.votos_primeiro_colocado >= rg.total_votos
    assert rg.total_eleitos > 0


def test_desempenho_territorial_soma_bate_com_total_do_candidato(candidatura_sp, dados_disputa):
    vc, vd, rd = dados_disputa
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, "NR_ZONA")
    assert int(terr["votos_candidato"].sum()) == candidatura_sp.total_votos


def test_hhi_entre_zero_e_um(candidatura_sp, dados_disputa):
    vc, vd, rd = dados_disputa
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, "NR_ZONA")
    hhi = indice_concentracao_hhi(terr)
    assert 0 <= hhi <= 1


def test_indice_performance_dentro_de_0_100(candidatura_sp, dados_disputa):
    vc, vd, rd = dados_disputa
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, "NR_ZONA")
    hhi = indice_concentracao_hhi(terr)
    terr_class = zonas_de_disputa(terr, vd, rd, candidatura_sp, "NR_ZONA")
    indice = calcular_indice_performance(terr_class, hhi)

    assert indice["indice_performance"].between(0, 100).all()
    assert indice["classificacao"].notna().all()
