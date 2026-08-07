from src.candidate_finder import buscar_candidatos_disputa
from src.questionnaire.candidate_questionnaire import IdentificacaoAnalise
from src.rivals.hypothetical_rivals import (
    CARGO_ANO_COMPARAVEL,
    CARGO_LABEL_PARA_TSE,
    identificar_rivais_projetados,
    resolver_disputa_comparavel,
    resolver_municipio,
    rivals_weights_config,
)


def _identificacao(cargo_pretendido="Governador", uf="AC", municipio_base="", partido_sigla=None):
    return IdentificacaoAnalise(
        cargo_pretendido=cargo_pretendido,
        uf=uf,
        municipio_base=municipio_base,
        partido_sigla=partido_sigla,
    )


def test_todo_cargo_do_modulo_candidato_tem_ano_comparavel_mapeado():
    """Guarda de regressao: se um cargo for adicionado a CARGO_LABEL_PARA_TSE
    sem entrada correspondente em CARGO_ANO_COMPARAVEL, identificar_rivais_projetados
    quebraria com KeyError em vez de reportar um aviso."""
    for cargo_tse in CARGO_LABEL_PARA_TSE.values():
        assert cargo_tse in CARGO_ANO_COMPARAVEL, f"{cargo_tse} sem ano comparavel mapeado"


def test_pesos_do_indice_de_rivalidade_somam_1():
    pesos = rivals_weights_config()["indice_rivalidade"]["pesos"]
    assert abs(sum(pesos.values()) - 1.0) < 1e-9


def test_cargo_nao_reconhecido_retorna_aviso_sem_quebrar():
    disputa = resolver_disputa_comparavel(_identificacao(cargo_pretendido="Cargo Inexistente"))
    assert disputa.candidatos == []
    assert disputa.avisos
    assert "nao reconhecido" in disputa.avisos[0]


def test_resolver_municipio_nao_encontrado_retorna_aviso_claro_sem_fuzzy():
    codigo, nome, aviso = resolver_municipio(2024, "SP", "MUNICIPIO_QUE_NAO_EXISTE_TESTE_XYZ")
    assert codigo is None
    assert nome is None
    assert aviso is not None and "nao encontrado" in aviso


def test_disputa_estadual_real_encontra_candidatos_e_nao_precisa_de_municipio():
    """GOVERNADOR/AC 2022 e' usado por varios outros testes do projeto (dado
    ja disponivel localmente) - reaproveitado aqui para nao exigir download
    extra so para este teste."""
    disputa = resolver_disputa_comparavel(_identificacao(cargo_pretendido="Governador", uf="AC"))
    assert disputa.ano == 2022
    assert disputa.cargo_tse == "GOVERNADOR"
    assert disputa.municipio_codigo is None
    assert len(disputa.candidatos) > 1
    assert not disputa.avisos


def test_identificar_rivais_projetados_com_dado_real_de_governador_ac():
    resultado = identificar_rivais_projetados(_identificacao(cargo_pretendido="Governador", uf="AC"), top_n=5)
    assert resultado.rivais, "deveria identificar ao menos um rival real"
    assert len(resultado.rivais) <= 5

    colocacoes = [r.colocacao for r in resultado.rivais]
    assert colocacoes == sorted(colocacoes)
    assert colocacoes[0] == 1

    votos_por_colocacao = [r.candidatura.total_votos for r in resultado.rivais]
    assert votos_por_colocacao == sorted(votos_por_colocacao, reverse=True), "rivais devem vir ordenados por votos reais"

    for rival in resultado.rivais:
        assert 0.0 <= rival.indice_rivalidade <= 100.0
        assert rival.classificacao in {"muito_alto", "alto", "moderado", "baixo", "critico"}
        assert rival.tipos

    lider = resultado.rivais[0]
    assert "rival_direto" in lider.tipos or "rival_dominante" in lider.tipos


def test_rival_do_mesmo_partido_do_candidato_recebe_tipo_rival_partidario():
    candidatos_reais = buscar_candidatos_disputa(2022, "GOVERNADOR", uf="AC", turno=1)
    partido_de_algum_rival = candidatos_reais[0].partido_sigla

    resultado = identificar_rivais_projetados(
        _identificacao(cargo_pretendido="Governador", uf="AC", partido_sigla=partido_de_algum_rival), top_n=10
    )

    rivais_do_partido = [
        r for r in resultado.rivais if r.candidatura.partido_sigla.strip().upper() == partido_de_algum_rival.strip().upper()
    ]
    assert rivais_do_partido, "o candidato usado para montar o partido deve aparecer nos rivais buscados"
    for rival in rivais_do_partido:
        assert "rival_partidario" in rival.tipos


def test_municipio_nao_encontrado_impede_identificar_rivais_e_reporta_aviso():
    resultado = identificar_rivais_projetados(
        _identificacao(cargo_pretendido="Vereador", uf="SP", municipio_base="MUNICIPIO_QUE_NAO_EXISTE_TESTE_XYZ")
    )
    assert resultado.rivais == []
    assert resultado.disputa.avisos
