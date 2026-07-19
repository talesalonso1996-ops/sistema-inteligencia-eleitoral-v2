import pandas as pd
from conftest import VARIAVEIS_DEMOGRAFICAS

from src.regression_models import regressao_linear_votos, regressao_logistica_bom_desempenho


def test_regressao_logistica_pseudo_r2_entre_0_e_1(base_territorio_sp):
    modelo, issues = regressao_logistica_bom_desempenho(
        base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS
    )
    assert modelo is not None, f"modelo nao ajustado: {issues}"
    assert 0 <= modelo.pseudo_r2_mcfadden <= 1


def test_regressao_logistica_odds_ratio_sempre_positivo(base_territorio_sp):
    modelo, _ = regressao_logistica_bom_desempenho(
        base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS
    )
    assert (modelo.coeficientes["odds_ratio"] > 0).all()


def test_regressao_logistica_matriz_confusao_soma_bate(base_territorio_sp):
    modelo, _ = regressao_logistica_bom_desempenho(
        base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS
    )
    assert modelo.matriz_confusao.values.sum() == modelo.n_positivos + modelo.n_negativos


def test_regressao_logistica_classes_aproximadamente_balanceadas(base_territorio_sp):
    """O limiar default (mediana do proprio candidato) deve gerar uma
    divisao proxima de 50/50 entre territorios de boa/fraca votacao."""
    modelo, _ = regressao_logistica_bom_desempenho(
        base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS
    )
    total = modelo.n_positivos + modelo.n_negativos
    assert abs(modelo.n_positivos - modelo.n_negativos) <= max(2, total * 0.1)


def test_regressao_logistica_cluster_ativa_erro_padrao_robusto(base_territorio_sp):
    """Quando coluna_cluster e informada (secoes de um mesmo local de
    votacao compartilham perfil demografico - nao sao independentes), o
    modelo deve sinalizar erro_padrao_cluster=True e continuar produzindo
    coeficientes validos."""
    base = base_territorio_sp.copy()
    # simula 2 secoes por "predio" repetindo cada linha (mesmo perfil
    # demografico, cluster identifica o par duplicado)
    base["predio_id"] = base.index
    duplicado = pd.concat([base, base], ignore_index=True)
    modelo, issues = regressao_logistica_bom_desempenho(
        duplicado, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS,
        coluna_cluster="predio_id",
    )
    assert modelo is not None, f"modelo nao ajustado: {issues}"
    assert modelo.erro_padrao_cluster is True
    assert "robusto a cluster" in modelo.limitacoes


def test_regressao_logistica_sem_cluster_mantem_comportamento_padrao(base_territorio_sp):
    modelo, _ = regressao_logistica_bom_desempenho(
        base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS
    )
    assert modelo.erro_padrao_cluster is False
    assert "robusto a cluster" not in modelo.limitacoes


def test_regressao_linear_cluster_ativa_erro_padrao_robusto(base_territorio_sp):
    base = base_territorio_sp.copy()
    base["predio_id"] = base.index
    duplicado = pd.concat([base, base], ignore_index=True)
    modelo, issues = regressao_linear_votos(
        duplicado, "votos_candidato", VARIAVEIS_DEMOGRAFICAS, coluna_cluster="predio_id",
    )
    assert modelo is not None, f"modelo nao ajustado: {issues}"
    assert modelo.erro_padrao_cluster is True


def test_regressao_logistica_exclui_variavel_sem_variancia(base_territorio_sp):
    """Uma variavel constante (mesmo valor em todos os territorios, ex.:
    municipio 100% urbanizado) somada ao intercepto causa colinearidade
    perfeita (matriz singular) - deve ser excluida automaticamente, com
    aviso, em vez de derrubar a regressao inteira."""
    base = base_territorio_sp.copy()
    base["pct_constante"] = 100.0
    variaveis = VARIAVEIS_DEMOGRAFICAS + ["pct_constante"]
    modelo, issues = regressao_logistica_bom_desempenho(
        base, "pct_votos_validos_territorio", variaveis
    )
    assert modelo is not None, f"modelo nao ajustado: {issues}"
    assert "pct_constante" not in modelo.variaveis_utilizadas
    assert any("pct_constante" in i.mensagem for i in issues)


def test_regressao_linear_exclui_variavel_sem_variancia(base_territorio_sp):
    base = base_territorio_sp.copy()
    base["pct_constante"] = 100.0
    variaveis = VARIAVEIS_DEMOGRAFICAS + ["pct_constante"]
    modelo, issues = regressao_linear_votos(base, "votos_candidato", variaveis)
    assert modelo is not None, f"modelo nao ajustado: {issues}"
    assert "pct_constante" not in modelo.variaveis_utilizadas
    assert any("pct_constante" in i.mensagem for i in issues)


def test_regressao_logistica_amostra_insuficiente_retorna_none():
    import pandas as pd

    df_pequeno = pd.DataFrame({
        "pct_votos_validos_territorio": [1.0, 2.0, 3.0],
        "renda_media_responsavel": [100, 200, 300],
    })
    modelo, issues = regressao_logistica_bom_desempenho(
        df_pequeno, "pct_votos_validos_territorio", ["renda_media_responsavel"]
    )
    assert modelo is None
    assert len(issues) > 0
