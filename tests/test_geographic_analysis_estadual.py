"""Testes das variantes ESTADUAIS (UF inteira) de geographic_analysis.py -
Governador SP 2022 (piloto real, ja usado nos demais testes da V2)."""
import pytest

from src.candidate_finder import (
    buscar_candidatos_disputa,
    registro_candidatos_disputa_generalizado,
    votos_da_candidatura_generalizado,
    votos_da_disputa_generalizado,
)
from src.demographic_analysis import perfil_demografico_do_territorio, perfil_demografico_por_setor
from src.electoral_metrics import desempenho_territorial
from src.geographic_analysis import (
    atribuir_setor_e_bairro_uf,
    carregar_coordenadas_uf,
    carregar_malha_municipios_uf,
    juntar_votos_com_coordenadas,
    normalizar_nome_municipio,
    total_votos_validos_por_territorio,
)
from src.maps import mapa_choropleth_territorio


@pytest.fixture(scope="module")
def dados_governador_sp_enriquecido():
    tarcisio = buscar_candidatos_disputa(2022, "GOVERNADOR", uf="SP", turno=1, numero=10)[0]
    vc = votos_da_candidatura_generalizado(tarcisio)
    vd = votos_da_disputa_generalizado(tarcisio)
    rd = registro_candidatos_disputa_generalizado(tarcisio)
    coords = carregar_coordenadas_uf("SP")
    pontos = juntar_votos_com_coordenadas(vc, coords)
    enriquecido, avisos = atribuir_setor_e_bairro_uf(pontos, "SP")
    return tarcisio, vc, vd, rd, enriquecido, avisos


def test_coordenadas_uf_cobrem_multiplos_municipios():
    coords = carregar_coordenadas_uf("SP")
    assert coords["CD_MUNICIPIO"].nunique() > 500  # SP tem 645 municipios


def test_atribuir_setor_e_bairro_uf_cobre_muitos_municipios(dados_governador_sp_enriquecido):
    _, _, _, _, enriquecido, _ = dados_governador_sp_enriquecido
    assert enriquecido["CD_MUNICIPIO"].nunique() > 500
    # a maioria dos locais com coordenada deve ter recebido um setor censitario
    com_coordenada = enriquecido.dropna(subset=["latitude", "longitude"])
    assert enriquecido["CD_SETOR"].notna().sum() / len(com_coordenada) > 0.9


def test_total_votos_validos_por_territorio_nao_colide_cd_municipio(dados_governador_sp_enriquecido):
    """Regressao: votos_disputa ja tem sua PROPRIA coluna CD_MUNICIPIO -
    usar nivel='CD_MUNICIPIO' nao pode gerar CD_MUNICIPIO_x/_y (colisao)."""
    _, _, vd, _, enriquecido, _ = dados_governador_sp_enriquecido
    resultado = total_votos_validos_por_territorio(vd, enriquecido, "CD_MUNICIPIO")
    assert "CD_MUNICIPIO" in resultado.columns
    assert "votos_validos_territorio" in resultado.columns
    assert (resultado["votos_validos_territorio"] > 0).all()


def test_perfil_demografico_por_municipio_funciona(dados_governador_sp_enriquecido):
    _, _, _, _, enriquecido, _ = dados_governador_sp_enriquecido
    setores = set(enriquecido["CD_SETOR"].dropna().unique())
    perfil_setor = perfil_demografico_por_setor(setores)
    perfil_mun = perfil_demografico_do_territorio(enriquecido, perfil_setor, "CD_MUNICIPIO")
    assert len(perfil_mun) > 500
    assert "renda_media_responsavel" in perfil_mun.columns


def test_malha_municipios_uf_tem_uma_linha_por_municipio():
    malha = carregar_malha_municipios_uf("SP")
    assert malha is not None
    assert len(malha) > 600  # SP tem 645 municipios
    assert "NM_MUN" in malha.columns
    assert "geometry" in malha.columns


def test_mapa_coropletico_estadual_gera_sem_erro(dados_governador_sp_enriquecido):
    tarcisio, vc, vd, rd, _, _ = dados_governador_sp_enriquecido
    terr_mun = desempenho_territorial(tarcisio, vc, vd, rd, "CD_MUNICIPIO")
    terr_mun = terr_mun.merge(
        vd[["CD_MUNICIPIO", "NM_MUNICIPIO"]].drop_duplicates(), on="CD_MUNICIPIO", how="left"
    )
    terr_mun["_nome_norm"] = terr_mun["NM_MUNICIPIO"].apply(normalizar_nome_municipio)

    malha_mun = carregar_malha_municipios_uf("SP")
    malha_mun = malha_mun.copy()
    malha_mun["_nome_norm"] = malha_mun["NM_MUN"].apply(normalizar_nome_municipio)

    # a maioria dos municipios da malha deve casar por nome com o terr_mun
    sem_match = malha_mun.merge(terr_mun, on="_nome_norm", how="left")["votos_candidato"].isna().sum()
    assert sem_match < len(malha_mun) * 0.05

    mapa = mapa_choropleth_territorio(
        malha_mun, terr_mun, "_nome_norm", "_nome_norm", "votos_candidato", tarcisio.nome_urna, zoom_start=6,
    )
    assert mapa is not None
