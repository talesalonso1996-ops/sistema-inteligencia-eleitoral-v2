"""Testes do patrimonio declarado por candidato (TSE - bem_candidato) -
Fase 5, item C. Usa Governador SP 2022 (candidato 10, Tarcisio) - piloto
ja usado no resto do projeto, com patrimonio real conferivel."""
import pytest

from src.candidate_assets import carregar_patrimonio_candidato, patrimonio_comparativo
from src.candidate_finder import (
    buscar_candidatos_disputa,
    registro_candidatos_disputa_generalizado,
    votos_da_disputa_generalizado,
)
from src.competitor_analysis import ranking_disputa


@pytest.fixture(scope="module")
def candidato_governador_sp():
    return buscar_candidatos_disputa(2022, "GOVERNADOR", uf="SP", turno=1, numero=10)[0]


def test_carregar_patrimonio_candidato_governador_sp(candidato_governador_sp):
    perfil = carregar_patrimonio_candidato(candidato_governador_sp)
    assert perfil.disponivel
    assert perfil.valor_total_bens > 0
    assert perfil.n_itens_declarados > 0
    assert len(perfil.top_bens) <= 5
    assert set(perfil.top_bens.columns) >= {"tipo", "descricao", "valor"}
    # top_bens deve estar ordenado do maior para o menor valor
    assert perfil.top_bens["valor"].is_monotonic_decreasing


def test_carregar_patrimonio_candidato_numero_inexistente(candidato_governador_sp):
    from dataclasses import replace

    falso = replace(candidato_governador_sp, numero=999999)
    perfil = carregar_patrimonio_candidato(falso)
    assert not perfil.disponivel
    assert perfil.valor_total_bens is None
    assert perfil.n_itens_declarados == 0


def test_carregar_patrimonio_candidato_cache_preserva_colunas_do_top_bens(candidato_governador_sp):
    """Regressao: top_bens guardado como lista de dicts numa unica celula
    do cache nao sobrevivia ao round-trip via parquet (voltava como uma
    serie de dicts soltos numa coluna '0', perdendo tipo/descricao/valor).
    Corrigido cacheando top_bens como tabela propria
    ('candidate_assets_top_bens'). Este teste precisa da 2a chamada (cache
    hit) para pegar a regressao - a 1a chamada sempre funcionava."""
    primeira = carregar_patrimonio_candidato(candidato_governador_sp)
    segunda = carregar_patrimonio_candidato(candidato_governador_sp)
    assert list(segunda.top_bens.columns) == ["tipo", "descricao", "valor"]
    assert list(primeira.top_bens["tipo"]) == list(segunda.top_bens["tipo"])
    assert list(primeira.top_bens["valor"]) == list(segunda.top_bens["valor"])


def test_patrimonio_comparativo_inclui_candidato_e_rivais(candidato_governador_sp):
    vd = votos_da_disputa_generalizado(candidato_governador_sp)
    rd = registro_candidatos_disputa_generalizado(candidato_governador_sp)
    ranking = ranking_disputa(vd, rd)

    comparativo = patrimonio_comparativo(candidato_governador_sp, ranking, top_n=3)
    assert len(comparativo) == 4  # candidato + 3 rivais
    assert candidato_governador_sp.numero in comparativo["numero"].values
    assert comparativo["disponivel"].sum() >= 1
