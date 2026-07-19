import pandas as pd

from src.competitor_analysis import delta_vs_rivais, matriz_candidato_territorio, rivais_por_similaridade_eleitorado
from src.vote_filtering import votos_nominais, votos_validos


def test_ranking_disputa_percentual_nunca_excede_100(ranking_sp):
    """pct_votos_validos e uma fatia do total de votos validos da propria
    disputa - nunca pode passar de 100% (bug real ja corrigido: cache sem
    UF/versao podia servir votos de uma disputa diferente do registro)."""
    assert (ranking_sp["pct_votos_validos"] <= 100).all()


def test_soma_nominais_menor_ou_igual_total_validos(dados_disputa):
    _, vd, rd = dados_disputa
    assert votos_nominais(vd, rd)["QT_VOTOS"].sum() <= votos_validos(vd)["QT_VOTOS"].sum()


def test_rivais_por_similaridade_correlacao_em_intervalo_valido(candidatura_sp, dados_disputa):
    _, vd, rd = dados_disputa
    rivais, issues = rivais_por_similaridade_eleitorado(candidatura_sp, vd, rd, "NR_ZONA", top_n=3)
    assert rivais["correlacao_base_eleitoral"].between(-1, 1).all()


def test_rivais_por_similaridade_nunca_inclui_o_proprio_candidato(candidatura_sp, dados_disputa):
    _, vd, rd = dados_disputa
    rivais, _ = rivais_por_similaridade_eleitorado(candidatura_sp, vd, rd, "NR_ZONA", top_n=3)
    assert candidatura_sp.numero not in rivais["numero"].values


def test_rivais_por_similaridade_respeita_top_n(candidatura_sp, dados_disputa):
    _, vd, rd = dados_disputa
    rivais, _ = rivais_por_similaridade_eleitorado(candidatura_sp, vd, rd, "NR_ZONA", top_n=3)
    assert len(rivais) <= 3


def test_delta_vs_rivais_bate_com_calculo_manual():
    matriz = pd.DataFrame({
        "NR_ZONA": [1, 2],
        "Candidato": [100, 50],
        "Rival A": [80, 60],
    })
    delta = delta_vs_rivais(matriz, "NR_ZONA", "Candidato")
    linha_zona1 = delta[(delta["NR_ZONA"] == 1) & (delta["rival"] == "Rival A")].iloc[0]
    assert linha_zona1["delta"] == 20
    assert linha_zona1["delta_pct"] == 20.0

    linha_zona2 = delta[(delta["NR_ZONA"] == 2) & (delta["rival"] == "Rival A")].iloc[0]
    assert linha_zona2["delta"] == -10
    assert round(linha_zona2["delta_pct"], 2) == round(-10 / 60 * 100, 2)


def test_delta_vs_rivais_com_dados_reais(candidatura_sp, dados_disputa, ranking_sp):
    _, vd, _ = dados_disputa
    matriz = matriz_candidato_territorio(candidatura_sp, vd, ranking_sp, "NR_ZONA", top_n_concorrentes=3)
    delta = delta_vs_rivais(matriz, "NR_ZONA", candidatura_sp.nome_urna)
    rivais_na_matriz = set(matriz.columns) - {"NR_ZONA", candidatura_sp.nome_urna}
    assert set(delta["rival"].unique()) == rivais_na_matriz
