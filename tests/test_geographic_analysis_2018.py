"""Testes da integracao geografica de 2018 (fonte alternativa via BigQuery,
ver scripts/converter_coordenadas_secao_2018_bigquery.py e
scripts/converter_votacao_secao_2018_bigquery.py) - Governador SP 2018
(Doria, resultado real conhecido: 6.431.555 votos no 1o turno)."""
import pytest

from src.candidate_finder import buscar_candidatos_disputa, votos_da_candidatura_generalizado
from src.demographic_analysis import perfil_demografico_do_territorio, perfil_demografico_por_setor
from src.geographic_analysis import (
    atribuir_setor_e_bairro_uf,
    carregar_coordenadas_uf,
    juntar_votos_com_coordenadas_secao,
)
from src.regression_models import regressao_linear_votos


@pytest.fixture(scope="module")
def dados_doria_2018_enriquecido():
    doria = buscar_candidatos_disputa(2018, "GOVERNADOR", uf="SP", turno=1, numero=45)[0]
    vc = votos_da_candidatura_generalizado(doria)
    coords = carregar_coordenadas_uf("SP", 2018)
    pontos = juntar_votos_com_coordenadas_secao(vc, coords)
    enriquecido, avisos = atribuir_setor_e_bairro_uf(pontos, "SP")
    return doria, vc, enriquecido, avisos


def test_candidatura_2018_bate_com_resultado_real_conhecido(dados_doria_2018_enriquecido):
    doria, vc, _, _ = dados_doria_2018_enriquecido
    assert doria.total_votos == 6431555
    assert vc["QT_VOTOS"].sum() == 6431555


def test_coordenadas_uf_2018_usa_fonte_alternativa_com_nr_secao_como_local():
    """A fonte de 2018 nao tem NR_LOCAL_VOTACAO real (nao existe
    eleitorado_local_votacao para esse ano) - NR_SECAO e usado como
    NR_LOCAL_VOTACAO sintetico, consistente entre votacao_secao_2018 e
    coordenadas_secao_2018 (ver nota metodologica nos scripts de
    conversao)."""
    coords = carregar_coordenadas_uf("SP", 2018)
    assert not coords.empty
    assert coords["CD_MUNICIPIO"].nunique() > 500  # SP tem 645 municipios
    assert set(coords.columns) >= {
        "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_LOCAL_VOTACAO",
        "NM_LOCAL_VOTACAO", "latitude", "longitude",
    }


def test_atribuir_setor_e_bairro_uf_funciona_para_2018(dados_doria_2018_enriquecido):
    """Achado real desta integracao: a fonte alternativa de coordenadas
    (dataset br_tse_eleicoes/local_secao) cobre ~87,5% das secoes de 2018
    nacionalmente - o join espacial precisa continuar funcionando para a
    maioria das secoes COM coordenada, e nunca descartar as sem coordenada
    (aparecem como 'nao identificado', preservando o total de votos)."""
    _, _, enriquecido, avisos = dados_doria_2018_enriquecido
    com_coordenada = enriquecido.dropna(subset=["latitude", "longitude"])
    assert len(com_coordenada) / len(enriquecido) > 0.8
    assert enriquecido["CD_SETOR"].notna().sum() / len(com_coordenada) > 0.9
    # nenhum voto e descartado, mesmo os sem coordenada
    assert enriquecido["votos_candidato"].sum() == 6431555


def test_regressao_com_censo_funciona_para_2018(dados_doria_2018_enriquecido):
    """Prova de que a analise demografica/estatistica completa (Censo IBGE
    2022 cruzado com voto) agora funciona para 2018 - antes desta
    integracao, so o voto por zona estava disponivel (sem dado
    geografico/demografico nenhum)."""
    _, _, enriquecido, _ = dados_doria_2018_enriquecido
    setores = set(enriquecido["CD_SETOR"].dropna().unique())
    assert len(setores) > 1000  # SP tem muitos setores censitarios reais

    perfil_setor = perfil_demografico_por_setor(setores)
    assert not perfil_setor.empty

    base = perfil_demografico_do_territorio(enriquecido, perfil_setor, "secao_id")
    votos_terr = enriquecido.groupby("secao_id", as_index=False)["votos_candidato"].sum()
    base = votos_terr.merge(base, on="secao_id", how="inner")
    assert base["renda_media_responsavel"].notna().sum() > 0
    validos = base["pct_alfabetizado_15mais"].dropna()
    assert not validos.empty
    assert validos.between(0, 100, inclusive="both").all()

    reg, _ = regressao_linear_votos(
        base, "votos_candidato",
        ["pct_alfabetizado_15mais", "renda_media_responsavel", "pct_masculino"],
    )
    assert reg is not None
    assert reg.n_observacoes > 1000
