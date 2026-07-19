import pytest

from src.rules.electoral_scope import EscopoInvalidoError, cargos_disponiveis, resolver_escopo


def test_prefeito_2024_e_municipal_e_identico_ao_v1():
    """Trava o comportamento herdado do V1: os 2 literais SQL hardcoded em
    candidate_finder.py (DS_ELEICAO ILIKE '%Eleições Municipais%',
    TP_ABRANGENCIA='MUNICIPAL') devem continuar saindo, byte a byte, do
    escopo resolvido - nenhuma regressao no caminho 2024 municipal."""
    escopo = resolver_escopo(2024, "PREFEITO", uf="SP", municipio="SANTOS")
    assert escopo.tipo_abrangencia == "MUNICIPAL"
    assert escopo.municipio_obrigatorio is True
    assert escopo.uf_e_filtro_analitico is False
    assert escopo.filtro_sql_ds_eleicao == "%Eleições Municipais%"
    assert escopo.filtro_sql_tp_abrangencia == "MUNICIPAL"
    assert escopo.permite_segundo_turno is True


def test_vereador_2024_nao_tem_segundo_turno():
    escopo = resolver_escopo(2024, "VEREADOR", uf="SP", municipio="SANTOS")
    assert escopo.tipo_abrangencia == "MUNICIPAL"
    assert escopo.permite_segundo_turno is False
    with pytest.raises(EscopoInvalidoError):
        resolver_escopo(2024, "VEREADOR", uf="SP", municipio="SANTOS", turno=2)


def test_prefeito_2024_exige_municipio():
    with pytest.raises(EscopoInvalidoError):
        resolver_escopo(2024, "PREFEITO", uf="SP")


@pytest.mark.parametrize(
    "cargo", ["GOVERNADOR", "SENADOR", "DEPUTADO FEDERAL", "DEPUTADO ESTADUAL"],
)
def test_cargos_estaduais_2022_nao_exigem_municipio(cargo):
    escopo = resolver_escopo(2022, cargo, uf="SP")
    assert escopo.tipo_abrangencia == "ESTADUAL"
    assert escopo.municipio_obrigatorio is False
    assert escopo.uf_obrigatoria is True
    assert "MUNICIPIO" in escopo.niveis_territoriais_disponiveis


def test_presidente_2022_e_nacional_e_uf_e_apenas_filtro_analitico():
    escopo = resolver_escopo(2022, "PRESIDENTE")
    assert escopo.tipo_abrangencia == "NACIONAL"
    assert escopo.uf_obrigatoria is False
    assert escopo.municipio_obrigatorio is False
    assert escopo.uf_e_filtro_analitico is True
    assert escopo.permite_segundo_turno is True


def test_deputado_distrital_so_existe_no_df():
    escopo = resolver_escopo(2022, "DEPUTADO DISTRITAL", uf="DF")
    assert escopo.tipo_abrangencia == "DISTRITAL"
    with pytest.raises(EscopoInvalidoError):
        resolver_escopo(2022, "DEPUTADO DISTRITAL", uf="SP")
    with pytest.raises(EscopoInvalidoError):
        resolver_escopo(2022, "DEPUTADO DISTRITAL")


@pytest.mark.parametrize("cargo", ["SENADOR", "DEPUTADO FEDERAL", "DEPUTADO ESTADUAL", "DEPUTADO DISTRITAL", "VEREADOR"])
def test_cargos_proporcionais_ou_sem_2o_turno_bloqueiam_turno_2(cargo):
    uf = "DF" if cargo == "DEPUTADO DISTRITAL" else "SP"
    municipio = "SANTOS" if cargo == "VEREADOR" else None
    ano = 2024 if cargo == "VEREADOR" else 2022
    with pytest.raises(EscopoInvalidoError):
        resolver_escopo(ano, cargo, uf=uf, municipio=municipio, turno=2)


def test_cargo_inexistente_no_ano():
    with pytest.raises(EscopoInvalidoError):
        resolver_escopo(2024, "PRESIDENTE")
    with pytest.raises(EscopoInvalidoError):
        resolver_escopo(2022, "PREFEITO", uf="SP", municipio="SANTOS")


def test_ano_nao_suportado():
    with pytest.raises(EscopoInvalidoError):
        resolver_escopo(2026, "PREFEITO", uf="SP", municipio="SANTOS")


def test_cargo_desconhecido():
    with pytest.raises(EscopoInvalidoError):
        resolver_escopo(2024, "IMPERADOR", uf="SP", municipio="SANTOS")


def test_cargos_disponiveis_filtra_deputado_distrital_por_uf():
    cargos_df = cargos_disponiveis(2022, uf="DF")
    cargos_sp = cargos_disponiveis(2022, uf="SP")
    assert "DEPUTADO DISTRITAL" in cargos_df
    assert "DEPUTADO DISTRITAL" not in cargos_sp
    assert cargos_disponiveis(2024) == ["PREFEITO", "VEREADOR"]


def test_turno_invalido_levanta_erro():
    with pytest.raises(EscopoInvalidoError):
        resolver_escopo(2024, "PREFEITO", uf="SP", municipio="SANTOS", turno=3)
