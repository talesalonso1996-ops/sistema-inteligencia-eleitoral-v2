from conftest import VARIAVEIS_DEMOGRAFICAS

from src.clustering import segmentar_territorios
from src.potential_analysis import identificar_bairros_potencial
from src.regression_models import regressao_logistica_bom_desempenho


def test_bairros_potencial_so_inclui_gap_positivo(base_territorio_sp):
    resultado_clustering, _ = segmentar_territorios(base_territorio_sp, VARIAVEIS_DEMOGRAFICAS, k=10)
    potencial = identificar_bairros_potencial(
        resultado_clustering, None, "local_votacao_id", "votos_candidato", top_n=10
    )
    assert (potencial["gap_vs_cluster"] > 0).all()


def test_bairros_potencial_score_nao_negativo(base_territorio_sp):
    resultado_clustering, _ = segmentar_territorios(base_territorio_sp, VARIAVEIS_DEMOGRAFICAS, k=10)
    potencial = identificar_bairros_potencial(
        resultado_clustering, None, "local_votacao_id", "votos_candidato", top_n=10
    )
    assert (potencial["score_potencial"] >= 0).all()
    assert (potencial["score_potencial"] <= 100).all()


def test_bairros_potencial_com_modelo_logistico(base_territorio_sp):
    resultado_clustering, _ = segmentar_territorios(base_territorio_sp, VARIAVEIS_DEMOGRAFICAS, k=10)
    modelo_log, _ = regressao_logistica_bom_desempenho(
        base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS
    )
    potencial = identificar_bairros_potencial(
        resultado_clustering, modelo_log, "local_votacao_id", "votos_candidato", top_n=10
    )
    assert potencial["probabilidade_boa_votacao"].dropna().between(0, 1).all()


def test_bairros_potencial_respeita_top_n(base_territorio_sp):
    resultado_clustering, _ = segmentar_territorios(base_territorio_sp, VARIAVEIS_DEMOGRAFICAS, k=10)
    potencial = identificar_bairros_potencial(
        resultado_clustering, None, "local_votacao_id", "votos_candidato", top_n=5
    )
    assert len(potencial) <= 5
