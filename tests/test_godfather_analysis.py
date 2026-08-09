"""Testes do modulo de analise do padrinho politico
(src/godfather_analysis.py) - Item 3 das melhorias pos-Etapa 8. Casos
reais conhecidos, conferidos manualmente antes de escrever este arquivo:
TARCISIO GOMES DE FREITAS (Governador/SP 2022, 2o turno, 9.881.995 votos)
e MARIA APARECIDA DA SILVA (nome com 15 combinacoes numero+cargo
distintas em SP/2024 - homonimo real, nunca deve ser resolvido)."""
from src.godfather_analysis import LIMITACAO_MATCH_NOME, analisar_padrinho_politico


def test_padrinho_nao_declarado_retorna_none():
    assert analisar_padrinho_politico(None, "SP") is None
    assert analisar_padrinho_politico("", "SP") is None
    assert analisar_padrinho_politico("   ", "SP") is None


def test_padrinho_real_encontrado_calcula_idp():
    resultado = analisar_padrinho_politico("TARCISIO GOMES DE FREITAS", "SP")
    assert resultado.encontrado_no_tse is True
    assert resultado.anos_verificados == [2022]
    assert resultado.candidatura_encontrada is not None
    assert resultado.candidatura_encontrada.cargo.upper() == "GOVERNADOR"
    assert resultado.indice_forca_idp is not None
    assert 0.0 <= resultado.indice_forca_idp <= 100.0
    assert resultado.classificacao_forca is not None
    assert LIMITACAO_MATCH_NOME in resultado.limitacoes


def test_padrinho_nao_encontrado_degrada_graciosamente():
    resultado = analisar_padrinho_politico("FULANO DE TAL INEXISTENTE XPTO NUNCA CANDIDATO", "SP")
    assert resultado.encontrado_no_tse is False
    assert resultado.candidatura_encontrada is None
    assert resultado.indice_forca_idp is None
    assert resultado.anos_verificados == []
    assert LIMITACAO_MATCH_NOME in resultado.limitacoes


def test_padrinho_com_homonimo_real_nunca_escolhe():
    """MARIA APARECIDA DA SILVA tem 15 combinacoes numero+cargo distintas
    so em SP/2024 (conferido manualmente) - precisa ficar como
    'nao encontrado', nunca adivinhar qual delas e o padrinho declarado."""
    resultado = analisar_padrinho_politico("MARIA APARECIDA DA SILVA", "SP")
    assert resultado.encontrado_no_tse is False
    assert resultado.anos_verificados == []
