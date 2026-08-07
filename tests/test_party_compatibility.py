from src.candidate_finder import buscar_candidatos_disputa
from src.parties.party_compatibility import avaliar_compatibilidade_partidaria


def test_partido_sem_candidato_na_disputa_reporta_aviso_sem_fabricar_dado():
    resultado = avaliar_compatibilidade_partidaria("ZZZ_SIGLA_INEXISTENTE", "Governador", "AC", "")
    assert resultado.n_candidatos_partido == 0
    assert resultado.n_eleitos_partido == 0
    assert resultado.melhor_colocacao_partido is None
    assert resultado.avisos
    assert "nao lancou candidato" in resultado.avisos[0]


def test_cargo_nao_reconhecido_retorna_aviso_sem_quebrar():
    resultado = avaliar_compatibilidade_partidaria("PT", "Cargo Inexistente", "AC", "")
    assert resultado.candidatos_partido == []
    assert resultado.avisos
    assert "nao reconhecido" in resultado.avisos[0]


def test_partido_real_calcula_historico_a_partir_do_mesmo_dado_da_disputa():
    """Cross-check: tudo que avaliar_compatibilidade_partidaria calcula deve
    bater exatamente com o que buscar_candidatos_disputa (fonte real ja
    usada pelo resto do SIET) retorna para o mesmo partido - sem nenhum
    valor extra inventado pelo modulo novo."""
    candidatos_reais = buscar_candidatos_disputa(2022, "GOVERNADOR", uf="AC", turno=1)
    sigla_alvo = candidatos_reais[0].partido_sigla

    esperado_do_partido = [c for c in candidatos_reais if c.partido_sigla.strip().upper() == sigla_alvo.strip().upper()]
    esperado_eleitos = [c for c in esperado_do_partido if c.resultado_final.upper().startswith("ELEITO")]
    esperado_eleitos_geral = [c for c in candidatos_reais if c.resultado_final.upper().startswith("ELEITO")]
    esperado_piso = min(c.total_votos for c in esperado_eleitos_geral) if esperado_eleitos_geral else None
    esperado_melhor = max(esperado_do_partido, key=lambda c: c.total_votos)

    resultado = avaliar_compatibilidade_partidaria(sigla_alvo, "Governador", "AC", "")

    assert resultado.n_candidatos_partido == len(esperado_do_partido)
    assert resultado.n_eleitos_partido == len(esperado_eleitos)
    assert resultado.votos_melhor_candidato_partido == esperado_melhor.total_votos
    assert resultado.piso_real_da_disputa == esperado_piso
    assert resultado.taxa_sucesso_partido == round(len(esperado_eleitos) / len(esperado_do_partido), 3)
    assert {c.numero for c in resultado.candidatos_partido} == {c.numero for c in esperado_do_partido}


def test_municipio_nao_encontrado_impede_avaliacao_e_reporta_aviso():
    resultado = avaliar_compatibilidade_partidaria("PT", "Vereador", "SP", "MUNICIPIO_QUE_NAO_EXISTE_TESTE_XYZ")
    assert resultado.candidatos_partido == []
    assert resultado.avisos
