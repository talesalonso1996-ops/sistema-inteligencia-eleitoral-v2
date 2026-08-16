"""Testes de src/questionnaire/persistence.py - dado ficticio, nenhuma
pessoa real. Isola do disco/rede reais: `resolve_path` e monkeypatchado
para um `tmp_path` e `requests.put`/`_github_token` sao mockados (nunca
bate na API real do GitHub num teste)."""
import json

import pytest

from src.questionnaire import persistence
from src.questionnaire.candidate_questionnaire import IdentificacaoAnalise, RespostaQuestionario
from src.questionnaire.policy_questionnaire import PropostaPauta


def _resposta_ficticia() -> RespostaQuestionario:
    return RespostaQuestionario(
        identificacao=IdentificacaoAnalise(
            cargo_pretendido="Vereador", uf="SP", municipio_base="Municipio Ficticio",
        )
    )


@pytest.fixture(autouse=True)
def _isolar_disco(tmp_path, monkeypatch):
    def _resolve(relative: str):
        return tmp_path / relative

    monkeypatch.setattr(persistence, "resolve_path", _resolve)
    yield tmp_path


def test_salvar_resposta_local_grava_json_valido(tmp_path):
    resposta = _resposta_ficticia()
    caminho = persistence.salvar_resposta_local(resposta)

    assert caminho.exists()
    assert caminho.name == f"{resposta.id_analise}.json"
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    assert conteudo["resposta"]["identificacao"]["cargo_pretendido"] == "Vereador"
    assert conteudo["resposta"]["id_analise"] == resposta.id_analise
    assert conteudo["propostas_pauta"] == []


def test_salvar_resposta_local_inclui_propostas_pauta():
    resposta = _resposta_ficticia()
    proposta = PropostaPauta(pauta_id="saude", cargo_analisado="Vereador", problema_central="Fila de espera")
    caminho = persistence.salvar_resposta_local(resposta, [proposta])

    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    assert len(conteudo["propostas_pauta"]) == 1
    assert conteudo["propostas_pauta"][0]["pauta_id"] == "saude"
    assert conteudo["propostas_pauta"][0]["problema_central"] == "Fila de espera"


def test_commitar_no_github_sem_token_retorna_false(monkeypatch):
    monkeypatch.setattr(persistence, "_github_token", lambda: None)
    resposta = _resposta_ficticia()
    caminho = persistence.salvar_resposta_local(resposta)

    assert persistence.commitar_no_github(caminho, resposta) is False


def test_commitar_no_github_sucesso(monkeypatch):
    monkeypatch.setattr(persistence, "_github_token", lambda: "token-ficticio")
    monkeypatch.setattr(persistence, "_github_repo", lambda: "owner/repo-ficticio")

    chamadas = []

    class _RespostaFalsa:
        status_code = 201
        text = ""

    def _put_falso(url, headers=None, json=None, timeout=None):
        chamadas.append((url, headers, json))
        return _RespostaFalsa()

    monkeypatch.setattr(persistence.requests, "put", _put_falso)

    resposta = _resposta_ficticia()
    caminho = persistence.salvar_resposta_local(resposta)
    assert persistence.commitar_no_github(caminho, resposta) is True
    assert len(chamadas) == 1
    url, headers, payload = chamadas[0]
    assert "owner/repo-ficticio" in url
    assert headers["Authorization"] == "Bearer token-ficticio"
    assert payload["content"]  # base64 nao vazio


def test_commitar_no_github_falha_http_retorna_false(monkeypatch):
    monkeypatch.setattr(persistence, "_github_token", lambda: "token-ficticio")

    class _RespostaFalsaErro:
        status_code = 409
        text = "conflito"

    monkeypatch.setattr(persistence.requests, "put", lambda *a, **k: _RespostaFalsaErro())

    resposta = _resposta_ficticia()
    caminho = persistence.salvar_resposta_local(resposta)
    assert persistence.commitar_no_github(caminho, resposta) is False


def test_commitar_no_github_excecao_de_rede_retorna_false(monkeypatch):
    monkeypatch.setattr(persistence, "_github_token", lambda: "token-ficticio")

    def _put_com_erro(*a, **k):
        raise persistence.requests.exceptions.ConnectionError("sem rede")

    monkeypatch.setattr(persistence.requests, "put", _put_com_erro)

    resposta = _resposta_ficticia()
    caminho = persistence.salvar_resposta_local(resposta)
    assert persistence.commitar_no_github(caminho, resposta) is False


def test_salvar_e_sincronizar_sem_token_ainda_salva_local(monkeypatch):
    monkeypatch.setattr(persistence, "_github_token", lambda: None)
    resposta = _resposta_ficticia()
    caminho, sincronizado = persistence.salvar_e_sincronizar(resposta)
    assert caminho.exists()
    assert sincronizado is False


def test_listar_respostas_salvas_vazio_quando_pasta_nao_existe():
    assert persistence.listar_respostas_salvas() == []


def test_listar_respostas_salvas_ordena_por_timestamp_desc():
    r1 = RespostaQuestionario(
        identificacao=IdentificacaoAnalise(cargo_pretendido="Vereador", uf="SP", municipio_base="A"),
    )
    r2 = RespostaQuestionario(
        identificacao=IdentificacaoAnalise(cargo_pretendido="Prefeito", uf="RJ", municipio_base="B"),
    )
    # forca r2 ser mais recente que r1 independente da ordem de execucao do teste
    from datetime import timedelta

    r1.timestamp = r2.timestamp - timedelta(hours=1)

    persistence.salvar_resposta_local(r1)
    persistence.salvar_resposta_local(r2)

    resumos = persistence.listar_respostas_salvas()
    assert len(resumos) == 2
    assert resumos[0]["id_analise"] == r2.id_analise
    assert resumos[1]["id_analise"] == r1.id_analise
    assert resumos[0]["cargo_pretendido"] == "Prefeito"


def test_listar_respostas_salvas_ignora_arquivo_corrompido(tmp_path):
    resposta = _resposta_ficticia()
    persistence.salvar_resposta_local(resposta)
    pasta = tmp_path / persistence._DIR_RESPOSTAS
    (pasta / "corrompido.json").write_text("{ isso nao e json valido", encoding="utf-8")

    resumos = persistence.listar_respostas_salvas()
    assert len(resumos) == 1
    assert resumos[0]["id_analise"] == resposta.id_analise


def test_carregar_resposta_bruta_round_trip():
    resposta = _resposta_ficticia()
    caminho = persistence.salvar_resposta_local(resposta)
    bruto = persistence.carregar_resposta_bruta(caminho)
    assert bruto["resposta"]["id_analise"] == resposta.id_analise
