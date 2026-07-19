import pandas as pd
import pytest

from conftest import VARIAVEIS_DEMOGRAFICAS

from src.clustering import gerar_narrativa_clusters, segmentar_territorios


def test_segmentar_territorios_k10_produz_10_clusters(base_territorio_sp):
    resultado, issues = segmentar_territorios(base_territorio_sp, VARIAVEIS_DEMOGRAFICAS, k=10)
    assert resultado is not None, f"clustering falhou: {issues}"
    assert resultado.k_escolhido == 10
    assert resultado.perfil_clusters["cluster"].nunique() == 10


def test_segmentar_territorios_k_maior_que_amostra_e_limitado():
    # 8 linhas: acima do minimo de amostra (6) mas abaixo de k=10, entao o
    # cap k<=n-1 deve entrar em acao (nao a validacao de amostra minima).
    df_pequeno = pd.DataFrame({
        "votos_candidato": [10, 20, 30, 40, 50, 60, 70, 80],
        "renda_media_responsavel": [100, 200, 300, 400, 500, 600, 700, 800],
    })
    resultado, issues = segmentar_territorios(df_pequeno, ["renda_media_responsavel"], k=10)
    assert resultado is not None, f"clustering falhou: {issues}"
    assert resultado.k_escolhido <= len(df_pequeno) - 1
    assert any(i.severidade == "aviso" for i in issues)


def test_gerar_narrativa_clusters_uma_linha_por_cluster(base_territorio_sp):
    resultado, _ = segmentar_territorios(base_territorio_sp, VARIAVEIS_DEMOGRAFICAS, k=10)
    narrativa = gerar_narrativa_clusters(resultado, "votos_candidato")
    assert len(narrativa) == resultado.perfil_clusters.shape[0]
    assert set(narrativa["rotulo_acao"].unique()) <= {"Fortaleza", "Consolidar", "Alto potencial", "Baixa prioridade"}
    assert narrativa["resumo"].str.len().gt(0).all()
