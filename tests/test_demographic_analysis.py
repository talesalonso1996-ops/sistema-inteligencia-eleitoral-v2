import pandas as pd
import pytest

from src.demographic_analysis import agregados_populacionais_municipio

_COLUNAS_PERCENTUAIS_NOVAS = [
    "pct_domicilios_chefia_feminina", "pct_agua_encanada", "pct_esgoto_adequado", "pct_coleta_lixo",
    "pct_populacao_15_24", "pct_populacao_60mais", "pct_sem_banheiro", "pct_esgoto_a_ceu_aberto",
]


@pytest.mark.parametrize("coluna", _COLUNAS_PERCENTUAIS_NOVAS)
def test_variaveis_parentesco_domicilio_ficam_em_0_100(base_territorio_sp, coluna):
    """variaveis_parentesco()/variaveis_domicilio() (src/demographic_analysis.py)
    sao percentuais (responsavel mulher, agua encanada, esgoto adequado,
    coleta de lixo) - precisam estar em [0, 100] onde houver dado de
    origem (setores sem match no censo ficam NaN, o que e esperado)."""
    assert coluna in base_territorio_sp.columns
    valores = base_territorio_sp[coluna].dropna()
    assert not valores.empty, f"{coluna} deveria ter pelo menos um valor nao nulo na amostra de teste"
    assert (valores >= 0).all() and (valores <= 100).all()


def test_renda_per_capita_aprox_sempre_menor_que_renda_media_responsavel(base_territorio_sp):
    """renda_per_capita_aprox usa n_moradores (mais pessoas por domicilio
    que responsaveis) - deve ficar sempre abaixo da renda media do
    RESPONSAVEL pelo domicilio."""
    assert "renda_per_capita_aprox" in base_territorio_sp.columns
    comparaveis = base_territorio_sp.dropna(subset=["renda_per_capita_aprox", "renda_media_responsavel"])
    assert not comparaveis.empty
    assert (comparaveis["renda_per_capita_aprox"] <= comparaveis["renda_media_responsavel"]).all()


def test_faixas_etarias_isoladas_coerentes_com_idade_media(base_territorio_sp):
    """pct_populacao_15_24 e pct_populacao_60mais sao faixas do MESMO
    calculo que ja produz idade_media_aprox (V01031-41) - nao podem, juntas,
    ultrapassar 100% da populacao do territorio."""
    df = base_territorio_sp.dropna(subset=["pct_populacao_15_24", "pct_populacao_60mais"])
    assert not df.empty
    assert (df["pct_populacao_15_24"] + df["pct_populacao_60mais"] <= 100.01).all()


def test_agregados_populacionais_municipio_dedup_por_local_antes_de_somar():
    """Regressao: 3 secoes do MESMO local de votacao (mesmo predio/setor)
    nao podem inflar a populacao do municipio por 3x - dedup por
    local_votacao_id precisa acontecer ANTES da soma."""
    pontos_com_setor = pd.DataFrame({
        # as 3 primeiras linhas sao SECOES diferentes do MESMO local de
        # votacao (predio) - local_votacao_id repete, so secao_id (nao usado
        # aqui) mudaria.
        "local_votacao_id": ["Escola A (Zona 1, Local 1)", "Escola A (Zona 1, Local 1)",
                              "Escola A (Zona 1, Local 1)", "Escola B (Zona 1, Local 2)"],
        "CD_SETOR": ["SETOR_1", "SETOR_1", "SETOR_1", "SETOR_2"],
        "CD_MUNICIPIO": [1001, 1001, 1001, 1001],
    })
    perfil_por_setor = pd.DataFrame({
        "CD_SETOR": ["SETOR_1", "SETOR_2"],
        "populacao_total": [1000, 500],
    })
    resultado = agregados_populacionais_municipio(pontos_com_setor, perfil_por_setor)
    assert len(resultado) == 1
    assert resultado.loc[0, "CD_MUNICIPIO"] == 1001
    assert resultado.loc[0, "populacao_total_municipio"] == 1500


def test_agregados_populacionais_municipio_separa_por_municipio():
    pontos_com_setor = pd.DataFrame({
        "local_votacao_id": ["Local A", "Local B"],
        "CD_SETOR": ["SETOR_1", "SETOR_2"],
        "CD_MUNICIPIO": [1001, 1002],
    })
    perfil_por_setor = pd.DataFrame({
        "CD_SETOR": ["SETOR_1", "SETOR_2"],
        "populacao_total": [1000, 2000],
    })
    resultado = agregados_populacionais_municipio(pontos_com_setor, perfil_por_setor)
    assert set(resultado["CD_MUNICIPIO"]) == {1001, 1002}
    assert resultado.set_index("CD_MUNICIPIO").loc[1001, "populacao_total_municipio"] == 1000
    assert resultado.set_index("CD_MUNICIPIO").loc[1002, "populacao_total_municipio"] == 2000
