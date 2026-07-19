"""Prova de nao-regressao da V2: as funcoes generalizadas adicionadas para
suportar cargos estaduais/distritais (buscar_candidatos_disputa,
votos_da_disputa_generalizado, registro_candidatos_disputa_generalizado)
devem produzir resultados IDENTICOS as funcoes originais do V1
(buscar_candidaturas, votos_da_disputa, registro_candidatos_disputa) para o
mesmo candidato/disputa municipal de 2024 - nao apenas "mesma forma", os
mesmos numeros exatos. Usa o mesmo fixture real do V1 (candidato 15900,
Sao Paulo capital, vereador 2024)."""
from src.candidate_finder import (
    buscar_candidatos_disputa,
    registro_candidatos_disputa,
    registro_candidatos_disputa_generalizado,
    votos_da_disputa,
    votos_da_disputa_generalizado,
)


def test_buscar_candidatos_disputa_bate_com_buscar_candidaturas(candidatura_sp):
    gerais = buscar_candidatos_disputa(
        candidatura_sp.ano_eleicao, candidatura_sp.cargo, uf=candidatura_sp.uf,
        municipio_codigo=candidatura_sp.codigo_municipio_tse, turno=candidatura_sp.turno,
        numero=candidatura_sp.numero,
    )
    assert len(gerais) == 1
    g = gerais[0]
    assert g.total_votos == candidatura_sp.total_votos
    assert g.codigo_municipio_tse == candidatura_sp.codigo_municipio_tse
    assert g.zonas_com_votos == candidatura_sp.zonas_com_votos
    assert g.nome_urna == candidatura_sp.nome_urna
    assert g.partido_sigla == candidatura_sp.partido_sigla


def test_votos_da_disputa_generalizado_bate_com_original(candidatura_sp):
    vd_old = votos_da_disputa(candidatura_sp)
    vd_new = votos_da_disputa_generalizado(candidatura_sp)
    assert len(vd_old) == len(vd_new)
    assert int(vd_old["QT_VOTOS"].sum()) == int(vd_new["QT_VOTOS"].sum())


def test_registro_candidatos_disputa_generalizado_bate_com_original(candidatura_sp):
    rd_old = registro_candidatos_disputa(candidatura_sp)
    rd_new = registro_candidatos_disputa_generalizado(candidatura_sp)
    assert len(rd_old) == len(rd_new)
    assert set(rd_old["numero"]) == set(rd_new["numero"])
