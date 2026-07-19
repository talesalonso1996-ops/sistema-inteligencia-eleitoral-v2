from src.economic_analysis import (
    _classificar_tendencia,
    carregar_perfil_economico_municipio,
    resolver_codigo_municipio_rais,
)


def test_resolver_codigo_municipio_rais_sao_paulo(candidatura_sp):
    codigo = resolver_codigo_municipio_rais(candidatura_sp)
    assert codigo == "355030", "codigo RAIS de Sao Paulo capital deveria ser 355030 (IBGE 3550308 sem digito verificador)"


def test_carregar_perfil_economico_sao_paulo(candidatura_sp):
    perfil = carregar_perfil_economico_municipio(candidatura_sp)
    assert perfil.disponivel
    # Sao Paulo e a maior cidade do Brasil - deve ter mais de 1 milhao de vinculos ativos.
    assert perfil.vinculos_ativos_total > 1_000_000
    assert perfil.estabelecimentos_ativos > 100_000
    assert perfil.saldo_caged_2024 is not None
    assert perfil.tendencia in {"crescimento", "estavel", "retracao"}


def test_classificar_tendencia_limites():
    assert _classificar_tendencia(saldo=10_000, vinculos_ativos=100_000) == "crescimento"
    assert _classificar_tendencia(saldo=-10_000, vinculos_ativos=100_000) == "retracao"
    assert _classificar_tendencia(saldo=100, vinculos_ativos=100_000) == "estavel"
    assert _classificar_tendencia(saldo=100, vinculos_ativos=0) == "indisponivel"


def test_perfil_economico_indisponivel_para_municipio_desconhecido():
    from dataclasses import replace

    from src.candidate_finder import buscar_candidaturas

    candidaturas = buscar_candidaturas(15900)
    alvo = candidaturas[0]
    # municipio inexistente/invalido - malha de setores nao vai encontrar
    falso = replace(alvo, municipio="MUNICIPIO_QUE_NAO_EXISTE_XYZ")
    perfil = carregar_perfil_economico_municipio(falso)
    assert not perfil.disponivel
    assert perfil.tendencia == "indisponivel"
