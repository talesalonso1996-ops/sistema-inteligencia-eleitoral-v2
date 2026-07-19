import pytest

_COLUNAS_PERCENTUAIS_NOVAS = [
    "pct_domicilios_chefia_feminina", "pct_agua_encanada", "pct_esgoto_adequado", "pct_coleta_lixo",
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
