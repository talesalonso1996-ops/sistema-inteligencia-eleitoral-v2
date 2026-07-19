import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from src.candidate_finder import (
    buscar_candidaturas,
    registro_candidatos_disputa,
    votos_da_candidatura,
    votos_da_disputa,
)
from src.competitor_analysis import ranking_disputa
from src.demographic_analysis import perfil_demografico_do_territorio, perfil_demografico_por_setor
from src.geographic_analysis import (
    atribuir_setor_e_bairro,
    carregar_coordenadas_locais,
    juntar_votos_com_coordenadas,
    total_votos_validos_por_territorio,
)

_NIVEL_DEMOGRAFICO = "local_votacao_id"


@pytest.fixture(scope="session")
def candidatura_sp():
    candidaturas = buscar_candidaturas(15900)
    return next(c for c in candidaturas if c.municipio == "SÃO PAULO")


@pytest.fixture(scope="session")
def dados_disputa(candidatura_sp):
    vc = votos_da_candidatura(candidatura_sp)
    vd = votos_da_disputa(candidatura_sp)
    rd = registro_candidatos_disputa(candidatura_sp)
    return vc, vd, rd


@pytest.fixture(scope="session")
def ranking_sp(dados_disputa):
    _, vd, rd = dados_disputa
    return ranking_disputa(vd, rd)


@pytest.fixture(scope="session")
def base_territorio_sp(candidatura_sp, dados_disputa):
    """Base por local de votacao (votos + perfil demografico + votos validos
    do territorio) - mesma montagem usada em app.py, reaproveitada pelos
    testes de regressao/clustering/potencial."""
    vc, vd, _ = dados_disputa
    coords = carregar_coordenadas_locais(candidatura_sp)
    pontos = juntar_votos_com_coordenadas(vc, coords)
    enriquecido, _ = atribuir_setor_e_bairro(pontos, candidatura_sp)

    setores = set(enriquecido["CD_SETOR"].dropna().unique())
    perfil_setor = perfil_demografico_por_setor(setores)
    perfil_territorio = perfil_demografico_do_territorio(enriquecido, perfil_setor, _NIVEL_DEMOGRAFICO)
    votos_territorio = enriquecido.groupby(_NIVEL_DEMOGRAFICO, as_index=False)["votos_candidato"].sum()
    total_validos = total_votos_validos_por_territorio(vd, enriquecido, _NIVEL_DEMOGRAFICO)

    base = (
        votos_territorio.merge(perfil_territorio, on=_NIVEL_DEMOGRAFICO, how="inner")
        .merge(total_validos, on=_NIVEL_DEMOGRAFICO, how="left")
    )
    base["pct_votos_validos_territorio"] = (
        100 * base["votos_candidato"] / base["votos_validos_territorio"]
    ).round(2)
    return base


VARIAVEIS_DEMOGRAFICAS = [
    "renda_media_responsavel", "pct_alfabetizado_15mais", "pct_preta_parda",
    "idade_media_aprox", "pct_masculino", "pct_amarela", "pct_indigena",
    "pct_domicilios_chefia_feminina", "pct_agua_encanada", "pct_esgoto_adequado",
    "pct_coleta_lixo",
]
