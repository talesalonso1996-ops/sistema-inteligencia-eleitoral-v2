"""Testes de src/territory_recommendations.py (Territorios e Pautas
Sugeridas, Modo 1 - melhorias pos-Etapa 8). Usa Pitangueiras/SP (cidade
pequena do interior, mesma fixture ja usada em
test_candidate_territory_policy_matrix.py) para manter os testes rapidos."""
from src.territory_recommendations import (
    montar_territorios_sugeridos,
    perfil_por_territorio_municipio,
    proxies_config,
    ranking_territorios_por_pauta,
)

_UF_TESTE = "SP"
_MUNICIPIO_TESTE = "Pitangueiras"


def test_proxies_config_so_lista_pautas_com_variavel_valida():
    """Cada pauta mapeada precisa referenciar variaveis do Censo que
    realmente existem em demographic_analysis.perfil_demografico_por_setor
    - nunca uma variavel inventada/digitada errado."""
    from src.demographic_analysis import _COLUNAS_PERFIL_DEMOGRAFICO_SETOR

    cfg = proxies_config()["pautas"]
    for pauta_id, dados in cfg.items():
        for item in dados["variaveis"]:
            assert item["nome"] in _COLUNAS_PERFIL_DEMOGRAFICO_SETOR, (
                f"pauta '{pauta_id}' referencia variavel '{item['nome']}' que nao existe "
                f"em perfil_demografico_por_setor"
            )
            assert item["direcao"] in ("menor_pior", "maior_relevante")


def test_perfil_por_territorio_municipio_real():
    resultado = perfil_por_territorio_municipio(_UF_TESTE, _MUNICIPIO_TESTE)
    assert resultado.municipio == "PITANGUEIRAS"
    assert not resultado.avisos
    assert not resultado.territorios.empty
    assert "populacao_total" in resultado.territorios.columns
    assert "renda_media_responsavel" in resultado.territorios.columns


def test_perfil_por_territorio_municipio_nao_encontrado_degrada_graciosamente():
    resultado = perfil_por_territorio_municipio(_UF_TESTE, "MUNICIPIO_QUE_NAO_EXISTE_TESTE_XYZ")
    assert resultado.territorios.empty
    assert resultado.avisos


def test_ranking_pauta_com_proxy_real_ordena_por_oportunidade():
    perfil = perfil_por_territorio_municipio(_UF_TESTE, _MUNICIPIO_TESTE)
    resultado = ranking_territorios_por_pauta(perfil, "emprego_renda")
    assert resultado.tem_proxy_territorial is True
    if resultado.ranking is not None and not resultado.ranking.empty:
        valores = resultado.ranking["score_oportunidade"].tolist()
        assert valores == sorted(valores, reverse=True)
        assert (resultado.ranking["score_oportunidade"] >= 0).all()
        assert (resultado.ranking["score_oportunidade"] <= 100).all()


def test_ranking_pauta_sem_proxy_nunca_inventa_dado():
    """'cultura' nao tem variavel real do Censo mapeada - precisa avisar
    claramente, nunca fabricar um ranking."""
    perfil = perfil_por_territorio_municipio(_UF_TESTE, _MUNICIPIO_TESTE)
    resultado = ranking_territorios_por_pauta(perfil, "cultura")
    assert resultado.tem_proxy_territorial is False
    assert resultado.ranking is None
    assert resultado.aviso is not None


def test_montar_territorios_sugeridos_combina_os_3_sinais_sem_misturar():
    resultado = montar_territorios_sugeridos(
        _UF_TESTE, _MUNICIPIO_TESTE, ["emprego_renda", "cultura"], ["Centro", "Jardim Primavera"],
    )
    assert resultado.perfil.municipio == "PITANGUEIRAS"
    assert len(resultado.rankings_por_pauta) == 2
    assert resultado.rankings_por_pauta[0].pauta_id == "emprego_renda"
    assert resultado.rankings_por_pauta[1].pauta_id == "cultura"
    assert resultado.bairros_declarados == ["Centro", "Jardim Primavera"]
    assert resultado.limitacoes


def test_montar_territorios_sugeridos_funciona_sem_pautas_nem_bairros():
    """Nenhum dos 2 campos novos e obrigatorio - precisa degradar
    graciosamente, nunca quebrar."""
    resultado = montar_territorios_sugeridos(_UF_TESTE, _MUNICIPIO_TESTE, [], [])
    assert resultado.perfil.municipio == "PITANGUEIRAS"
    assert resultado.rankings_por_pauta == []
    assert resultado.bairros_declarados == []
