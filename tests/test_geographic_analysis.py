import geopandas as gpd
import pandas as pd
import pytest
import shapely

import src.geographic_analysis as geo
from src.candidate_finder import votos_da_candidatura
from src.geographic_analysis import (
    agregar_votos_por_bairro,
    atribuir_setor_e_bairro,
    carregar_coordenadas_locais,
    juntar_votos_com_coordenadas,
    juntar_votos_com_coordenadas_secao,
    uf_tem_malha_completa,
)
from src.utils import parse_tse_broken_decimal


def test_parse_tse_broken_decimal_latitude_santos():
    # Exemplo real do arquivo legado: latitude de Santos exportada com a
    # virgula decimal corrompida pelo Excel.
    assert parse_tse_broken_decimal("-239.669.088", integer_digits=2) == pytest.approx(-23.9669088)


def test_parse_tse_broken_decimal_longitude_santos():
    assert parse_tse_broken_decimal("-463.529.031", integer_digits=2) == pytest.approx(-46.3529031)


def test_parse_tse_broken_decimal_valor_ausente():
    assert parse_tse_broken_decimal("-1", integer_digits=2) is None
    assert parse_tse_broken_decimal(None, integer_digits=2) is None


def test_uf_com_malha_completa_sp():
    assert uf_tem_malha_completa("SP") is True


def test_uf_sem_malha_completa_retorna_false_e_nao_quebra():
    assert uf_tem_malha_completa("XX") is False


def test_join_espacial_atribui_setor_para_maioria_dos_locais(candidatura_sp):
    vc = votos_da_candidatura(candidatura_sp)
    coords = carregar_coordenadas_locais(candidatura_sp)
    pontos = juntar_votos_com_coordenadas(vc, coords)
    enriquecido, avisos = atribuir_setor_e_bairro(pontos, candidatura_sp)

    com_setor = enriquecido["CD_SETOR"].notna().sum()
    assert com_setor / len(enriquecido) > 0.9, "mais de 90% dos locais devem cair em algum setor"


def test_agregar_votos_por_bairro_soma_bate(candidatura_sp):
    vc = votos_da_candidatura(candidatura_sp)
    coords = carregar_coordenadas_locais(candidatura_sp)
    pontos = juntar_votos_com_coordenadas(vc, coords)
    enriquecido, _ = atribuir_setor_e_bairro(pontos, candidatura_sp)
    bairros_agg = agregar_votos_por_bairro(enriquecido)

    assert int(bairros_agg["votos_candidato"].sum()) == int(enriquecido["votos_candidato"].sum())


def test_juntar_votos_com_coordenadas_secao_tem_mais_linhas_que_por_predio(candidatura_sp):
    """Um local de votacao tem em media varias secoes - a versao por secao
    deve ter mais linhas que a versao por predio, preservando o total de
    votos (nenhum voto perdido/duplicado ao desagregar)."""
    vc = votos_da_candidatura(candidatura_sp)
    coords = carregar_coordenadas_locais(candidatura_sp)
    pontos_predio = juntar_votos_com_coordenadas(vc, coords)
    pontos_secao = juntar_votos_com_coordenadas_secao(vc, coords)

    assert len(pontos_secao) > len(pontos_predio)
    assert int(pontos_secao["votos_candidato"].sum()) == int(pontos_predio["votos_candidato"].sum())
    assert "secao_id" in pontos_secao.columns
    assert "local_votacao_id" in pontos_secao.columns
    assert pontos_secao["secao_id"].is_unique


def test_juntar_votos_com_coordenadas_secao_preserva_votos_apos_join_espacial(candidatura_sp):
    vc = votos_da_candidatura(candidatura_sp)
    coords = carregar_coordenadas_locais(candidatura_sp)
    pontos_secao = juntar_votos_com_coordenadas_secao(vc, coords)
    enriquecido, _ = atribuir_setor_e_bairro(pontos_secao, candidatura_sp)

    assert int(enriquecido["votos_candidato"].sum()) == int(pontos_secao["votos_candidato"].sum())
    # secoes do mesmo predio devem compartilhar o mesmo setor censitario
    grupos = enriquecido.dropna(subset=["CD_SETOR"]).groupby("local_votacao_id")["CD_SETOR"].nunique()
    assert (grupos == 1).all()


def _gdf_sintetico(n: int, cep: str | None = "74000000") -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "votos_candidato": [10] * n,
            "cep": [cep] * n,
            "NM_BAIRRO_IBGE": [None] * n,
        },
        geometry=[shapely.Point(-49.25 + i * 0.001, -16.68) for i in range(n)],
        crs="EPSG:4674",
    )


def test_preencher_bairro_via_cep_usa_ceplookup_mockado(monkeypatch):
    gdf = _gdf_sintetico(3)
    monkeypatch.setattr(
        geo, "bairros_por_ceps",
        lambda ceps, max_novas_consultas=None: {c: "Setor Central" for c in ceps},
    )

    recuperados, limite_excedido = geo._preencher_bairro_via_cep(gdf, pd.Series([True] * 3))

    assert recuperados == 3
    assert limite_excedido is False
    assert (gdf["NM_BAIRRO_IBGE"] == "Setor Central").all()


def test_preencher_bairro_via_cep_respeita_limite_maximo(monkeypatch):
    """bairros_por_ceps (mockado aqui) e quem de fato respeita
    max_novas_consultas - simula isso retornando so os 2 primeiros CEPs,
    como a implementacao real faria com CEPs ainda nao cacheados."""
    chamadas = {"max_novas_consultas": None}

    def _fake_bairros_por_ceps(ceps, max_novas_consultas=None):
        chamadas["max_novas_consultas"] = max_novas_consultas
        limite = max_novas_consultas if max_novas_consultas is not None else len(ceps)
        return {c: "Bairro Qualquer" for c in ceps[:limite]}

    monkeypatch.setattr(geo, "bairros_por_ceps", _fake_bairros_por_ceps)
    monkeypatch.setattr(geo, "_MAX_CEPS_POR_CONSULTA", 2)

    gdf = gpd.GeoDataFrame(
        {
            "votos_candidato": [10, 10, 10],
            "cep": ["74000001", "74000002", "74000003"],  # 3 CEPs distintos > limite de 2
            "NM_BAIRRO_IBGE": [None, None, None],
        },
        geometry=[shapely.Point(-49.25, -16.68)] * 3,
        crs="EPSG:4674",
    )
    recuperados, limite_excedido = geo._preencher_bairro_via_cep(gdf, pd.Series([True, True, True]))

    assert chamadas["max_novas_consultas"] == 2
    assert recuperados == 2
    assert limite_excedido is True
