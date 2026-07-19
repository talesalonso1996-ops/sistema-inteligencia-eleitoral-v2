"""Testa zona_uf_composta (src/vote_filtering.py) - usada pela "Regressao
Geral" de cargos estaduais (V2) quando o usuario escolhe granularidade de
Zona eleitoral. Ver descoberta documentada no plano da Fase 4: NR_ZONA
sozinho NAO e unico dentro de uma UF (uma zona eleitoral e uma comarca que
costuma cobrir varios municipios pequenos ao mesmo tempo) - verificado com
dados reais do Acre (Governador 2022, disputa inteira da UF)."""
import pytest

from src.candidate_finder import buscar_candidatos_disputa, votos_da_disputa_generalizado
from src.vote_filtering import zona_uf_composta


@pytest.fixture(scope="module")
def votos_governador_ac_2022():
    gladson = buscar_candidatos_disputa(2022, "GOVERNADOR", uf="AC", turno=1, numero=11)[0]
    return votos_da_disputa_generalizado(gladson)


def test_nr_zona_sozinho_nao_e_unico_entre_municipios_do_acre(votos_governador_ac_2022):
    """Confirma empiricamente a premissa que motivou zona_uf_composta: pelo
    menos uma zona do Acre e compartilhada por mais de 1 municipio."""
    vd = votos_governador_ac_2022
    municipios_por_zona = vd.groupby("NR_ZONA")["CD_MUNICIPIO"].nunique()
    assert (municipios_por_zona > 1).any()


def test_zona_uf_composta_e_unica_por_municipio_mesmo_com_zona_repetida(votos_governador_ac_2022):
    """zona_uf_composta (CD_MUNICIPIO + NR_ZONA) nao deve colidir entre
    municipios diferentes - uma unica zona_uf_composta so pode conter
    votos de UM municipio."""
    vd = votos_governador_ac_2022.copy()
    vd["zona_uf_composta"] = zona_uf_composta(vd)
    municipios_por_zona_composta = vd.groupby("zona_uf_composta")["CD_MUNICIPIO"].nunique()
    assert (municipios_por_zona_composta == 1).all()


def test_zona_uf_composta_cobre_todos_os_municipios_do_acre(votos_governador_ac_2022):
    vd = votos_governador_ac_2022.copy()
    vd["zona_uf_composta"] = zona_uf_composta(vd)
    assert vd["zona_uf_composta"].nunique() >= vd["CD_MUNICIPIO"].nunique()
