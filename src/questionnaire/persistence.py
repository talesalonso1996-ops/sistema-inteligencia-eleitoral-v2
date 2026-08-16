"""Persistencia das respostas do Modulo Candidato (Modo 1) + pautas
associadas (Modo 3), usadas pelo host dedicado `app_candidatos.py`.

Filosofia igual ao resto do projeto (e ao pipeline do Agregador de
Pesquisas Eleitorais, projeto irmao): dado persistido e ARQUIVO
VERSIONADO, nunca banco de dados novo. Grava sempre localmente em
`data/candidatos/respostas/` (funciona de graca quando roda local); quando
rodando no Streamlit Community Cloud (disco efemero, nao sobrevive a
restart/redeploy) tambem faz commit do mesmo JSON direto no GitHub via API
REST de Contents, usando um token em `st.secrets["GITHUB_TOKEN"]` - so
assim o SIET principal (rodando em outra maquina/processo) consegue
enxergar depois (`git pull`). Nunca lanca excecao por falha de rede/token
ausente - mesmo principio de `candidate_assets.carregar_patrimonio_candidato`:
o formulario sempre mostra o resultado calculado, mesmo se a sincronizacao
falhar."""
from __future__ import annotations

import base64
import json
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import requests

from .candidate_questionnaire import RespostaQuestionario
from .policy_questionnaire import PropostaPauta
from ..utils import get_logger, resolve_path

logger = get_logger(__name__)

_REPO_PADRAO = "talesalonso1996-ops/sistema-inteligencia-eleitoral-v2"
_BRANCH_PADRAO = "master"
_DIR_RESPOSTAS = "data/candidatos/respostas"


def _json_default(obj: Any):
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Tipo nao serializavel em JSON: {type(obj)!r}")


def caminho_resposta(id_analise: str) -> Path:
    return resolve_path(_DIR_RESPOSTAS) / f"{id_analise}.json"


def _serializar(resposta: RespostaQuestionario, propostas_pauta: list[PropostaPauta] | None) -> dict:
    return {
        "resposta": asdict(resposta),
        "propostas_pauta": [asdict(p) for p in (propostas_pauta or [])],
    }


def salvar_resposta_local(
    resposta: RespostaQuestionario, propostas_pauta: list[PropostaPauta] | None = None
) -> Path:
    """Grava o JSON completo (questionario + pautas prioritarias
    detalhadas) em disco. Nunca falha silenciosamente por diretorio
    ausente - cria a arvore se precisar (mesmo padrao de write_cache em
    src/utils.py)."""
    caminho = caminho_resposta(resposta.id_analise)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conteudo = _serializar(resposta, propostas_pauta)
    caminho.write_text(
        json.dumps(conteudo, default=_json_default, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return caminho


def _github_token() -> str | None:
    try:
        import streamlit as st

        return st.secrets.get("GITHUB_TOKEN")
    except Exception:
        return None


def _github_repo() -> str:
    try:
        import streamlit as st

        return st.secrets.get("GITHUB_REPO", _REPO_PADRAO)
    except Exception:
        return _REPO_PADRAO


def commitar_no_github(caminho: Path, resposta: RespostaQuestionario) -> bool:
    """Commita o mesmo JSON ja gravado localmente direto no repositorio via
    API REST de Contents do GitHub - unico jeito da versao PUBLICA
    (Streamlit Cloud, disco efemero) deixar o dado disponivel pro SIET
    local depois de um `git pull`. So roda quando ha token configurado;
    qualquer falha (rede, token invalido, conflito) vira aviso logado,
    nunca excecao - o formulario sempre mostra o resultado calculado
    independente do resultado da sincronizacao."""
    token = _github_token()
    if not token:
        logger.info("GITHUB_TOKEN nao configurado - resposta salva so localmente.")
        return False

    repo = _github_repo()
    caminho_repo = f"{_DIR_RESPOSTAS}/{caminho.name}"
    url = f"https://api.github.com/repos/{repo}/contents/{caminho_repo}"
    conteudo_b64 = base64.b64encode(caminho.read_bytes()).decode("ascii")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    try:
        payload = {
            "message": (
                f"Novo candidato analisado: {resposta.identificacao.cargo_pretendido}/"
                f"{resposta.identificacao.uf} ({resposta.id_analise[:8]})"
            ),
            "content": conteudo_b64,
            "branch": _BRANCH_PADRAO,
        }
        resp = requests.put(url, headers=headers, json=payload, timeout=15)
        if resp.status_code in (200, 201):
            return True
        logger.warning(
            "Falha ao commitar resposta no GitHub (status %s): %s", resp.status_code, resp.text[:300]
        )
        return False
    except requests.RequestException as exc:
        logger.warning("Falha ao commitar resposta no GitHub: %s", exc)
        return False


def salvar_e_sincronizar(
    resposta: RespostaQuestionario, propostas_pauta: list[PropostaPauta] | None = None
) -> tuple[Path, bool]:
    """Ponto de entrada unico usado por `app_candidatos.py`: grava local e
    tenta sincronizar via GitHub. Retorna o caminho local e se a
    sincronizacao remota funcionou (so informativo pra UI, nunca bloqueia
    o fluxo)."""
    caminho = salvar_resposta_local(resposta, propostas_pauta)
    sincronizado = commitar_no_github(caminho, resposta)
    return caminho, sincronizado


def listar_respostas_salvas() -> list[dict]:
    """Le todos os JSONs salvos localmente (apos `git pull`, inclui os que
    vieram da versao publica) - usado pela secao 'Candidatos analisados' do
    app grande. Retorna um resumo (nao o objeto completo) ordenado do mais
    recente pro mais antigo; nunca lanca excecao por arquivo corrompido -
    pula e loga."""
    pasta = resolve_path(_DIR_RESPOSTAS)
    if not pasta.exists():
        return []
    resumos = []
    for arquivo in sorted(pasta.glob("*.json"), reverse=True):
        try:
            dado = json.loads(arquivo.read_text(encoding="utf-8"))
            identificacao = dado["resposta"]["identificacao"]
            resumos.append({
                "id_analise": dado["resposta"]["id_analise"],
                "timestamp": dado["resposta"]["timestamp"],
                "cargo_pretendido": identificacao["cargo_pretendido"],
                "uf": identificacao["uf"],
                "municipio_base": identificacao["municipio_base"],
                "n_pautas_detalhadas": len(dado.get("propostas_pauta", [])),
                "arquivo": arquivo,
            })
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Resposta salva ilegivel (%s): %s", arquivo.name, exc)
    resumos.sort(key=lambda r: r["timestamp"], reverse=True)
    return resumos


def carregar_resposta_bruta(arquivo: Path) -> dict:
    """Retorna o dict cru salvo (resposta + propostas_pauta) - usado quando
    a UI precisa mostrar/reabrir uma analise salva, sem reconstruir as
    dataclasses (a exibicao hoje so precisa dos campos, nao dos metodos)."""
    return json.loads(arquivo.read_text(encoding="utf-8"))
