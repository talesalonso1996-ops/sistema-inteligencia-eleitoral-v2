import numpy as np
from conftest import VARIAVEIS_DEMOGRAFICAS

from src.projections.monte_carlo import (
    cenario_agregado_votos,
    simular_regressao_linear,
    simular_regressao_logistica,
)
from src.regression_models import regressao_linear_votos, regressao_logistica_bom_desempenho

_NIVEL = "local_votacao_id"


def test_simulacao_linear_gera_uma_linha_por_territorio_com_dado_completo(base_territorio_sp):
    reg, _ = regressao_linear_votos(base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS)
    assert reg is not None
    sim = simular_regressao_linear(reg, base_territorio_sp, _NIVEL, n_simulacoes=500)
    assert sim is not None
    dados_completos = base_territorio_sp.dropna(subset=reg.variaveis_utilizadas)
    assert len(sim.territorios) == len(dados_completos)
    assert sim.matriz_simulacoes.shape == (500, len(dados_completos))


def test_simulacao_linear_p5_menor_ou_igual_p95(base_territorio_sp):
    reg, _ = regressao_linear_votos(base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS)
    sim = simular_regressao_linear(reg, base_territorio_sp, _NIVEL, n_simulacoes=500)
    assert (sim.territorios["p5"] <= sim.territorios["p95"]).all()
    assert (sim.territorios["mediana_simulada"] >= sim.territorios["p5"]).all()
    assert (sim.territorios["mediana_simulada"] <= sim.territorios["p95"]).all()


def test_simulacao_linear_respeita_limites_0_100(base_territorio_sp):
    reg, _ = regressao_linear_votos(base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS)
    sim = simular_regressao_linear(reg, base_territorio_sp, _NIVEL, n_simulacoes=500)
    assert (sim.matriz_simulacoes >= 0).all() and (sim.matriz_simulacoes <= 100).all()


def test_simulacao_linear_e_reprodutivel_com_mesma_seed(base_territorio_sp):
    reg, _ = regressao_linear_votos(base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS)
    sim_a = simular_regressao_linear(reg, base_territorio_sp, _NIVEL, n_simulacoes=300, seed=7)
    sim_b = simular_regressao_linear(reg, base_territorio_sp, _NIVEL, n_simulacoes=300, seed=7)
    assert np.array_equal(sim_a.matriz_simulacoes, sim_b.matriz_simulacoes)


def test_simulacao_linear_seeds_diferentes_dao_resultado_diferente(base_territorio_sp):
    reg, _ = regressao_linear_votos(base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS)
    sim_a = simular_regressao_linear(reg, base_territorio_sp, _NIVEL, n_simulacoes=300, seed=1)
    sim_b = simular_regressao_linear(reg, base_territorio_sp, _NIVEL, n_simulacoes=300, seed=2)
    assert not np.array_equal(sim_a.matriz_simulacoes, sim_b.matriz_simulacoes)


def test_simulacao_linear_retorna_none_se_variavel_do_modelo_nao_esta_nos_dados(base_territorio_sp):
    reg, _ = regressao_linear_votos(base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS)
    dados_incompletos = base_territorio_sp.drop(columns=[reg.variaveis_utilizadas[0]])
    assert simular_regressao_linear(reg, dados_incompletos, _NIVEL, n_simulacoes=200) is None


def test_simulacao_logistica_probabilidades_entre_0_e_1(base_territorio_sp):
    modelo, _ = regressao_logistica_bom_desempenho(base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS)
    assert modelo is not None
    assert "erro_padrao" in modelo.coeficientes.columns
    sim = simular_regressao_logistica(modelo, base_territorio_sp, _NIVEL, n_simulacoes=500)
    assert sim is not None
    assert (sim.territorios["p5"] >= 0).all() and (sim.territorios["p95"] <= 1).all()
    assert (sim.territorios["p5"] <= sim.territorios["p95"]).all()


def test_cenario_agregado_conservador_menor_ou_igual_otimista(base_territorio_sp):
    reg, _ = regressao_linear_votos(base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS)
    sim = simular_regressao_linear(reg, base_territorio_sp, _NIVEL, n_simulacoes=1000, seed=42)
    cenario = cenario_agregado_votos(sim, base_territorio_sp, _NIVEL, "votos_validos_territorio")
    assert cenario is not None
    assert cenario.conservador <= cenario.mediano <= cenario.otimista
    assert cenario.n_territorios == len(sim.territorios)
    assert cenario.votos_reais_atuais is not None and cenario.votos_reais_atuais > 0


def test_cenario_agregado_bate_com_soma_direta_da_matriz_de_simulacoes(base_territorio_sp):
    """Guarda de regressao central deste modulo: `cenario_agregado_votos`
    precisa de fato somar territorio a territorio DENTRO de cada simulacao
    (preservando a correlacao real entre territorios que vem do mesmo
    sorteio de coeficientes) antes de tirar os percentis - nao pode, por
    engano, virar uma soma de percentis marginais (que nao corresponde a
    nenhum percentil real da soma). Verifica recalculando a soma por
    simulacao diretamente da matriz e comparando os percentis."""
    reg, _ = regressao_linear_votos(base_territorio_sp, "pct_votos_validos_territorio", VARIAVEIS_DEMOGRAFICAS)
    sim = simular_regressao_linear(reg, base_territorio_sp, _NIVEL, n_simulacoes=1000, seed=42)
    cenario = cenario_agregado_votos(sim, base_territorio_sp, _NIVEL, "votos_validos_territorio")

    votos_validos = (
        base_territorio_sp.set_index(_NIVEL)["votos_validos_territorio"]
        .reindex(sim.territorios[_NIVEL])
        .to_numpy()
    )
    soma_por_simulacao_esperada = (sim.matriz_simulacoes / 100.0) @ votos_validos
    esperado_conservador = round(float(np.percentile(soma_por_simulacao_esperada, 5)), 0)
    esperado_mediano = round(float(np.percentile(soma_por_simulacao_esperada, 50)), 0)
    esperado_otimista = round(float(np.percentile(soma_por_simulacao_esperada, 95)), 0)

    assert cenario.conservador == esperado_conservador
    assert cenario.mediano == esperado_mediano
    assert cenario.otimista == esperado_otimista
