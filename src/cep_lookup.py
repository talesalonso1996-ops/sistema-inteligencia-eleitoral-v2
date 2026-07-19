"""Resolucao de bairro por CEP - fallback usado quando o join espacial nao
encontra um bairro oficial do IBGE para um local de votacao (municipio sem
malha de bairro publicada, ou ponto fora de todos os poligonos mesmo apos
o fallback de poligono mais proximo - ver geographic_analysis.py).

O CEP em si vem do proprio TSE (NR_CEP, dado oficial ja presente no
arquivo de eleitorado por local de votacao) - so o BAIRRO associado a esse
CEP e resolvido aqui, via o ViaCEP (https://viacep.com.br), servico
publico gratuito e sem autenticacao que consulta a base de enderecos dos
Correios. Diferente de TSE/IBGE, o ViaCEP NAO e uma fonte primaria oficial
de governo - e um servico de terceiros, com as limitacoes que isso implica
(pode ficar fora do ar, mudar de comportamento, ter rate limit). Por isso
toda falha (timeout, CEP invalido, servico indisponivel) degrada
graciosamente retornando None - nunca trava o sistema nem inventa um
bairro. Resultado cacheado em disco por CEP para nunca repetir a mesma
consulta."""
from __future__ import annotations

import json

import requests

from .utils import get_logger, resolve_path

logger = get_logger(__name__)

_TIMEOUT_S = 5
_CACHE_ARQUIVO = "data/cache/cep_bairro.json"


def _cache_path():
    caminho = resolve_path(_CACHE_ARQUIVO)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return caminho


def _carregar_cache() -> dict:
    caminho = _cache_path()
    if caminho.exists():
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Cache de CEP->bairro corrompido em %s - ignorando.", caminho)
    return {}


def _salvar_cache(cache: dict) -> None:
    try:
        _cache_path().write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.warning("Falha ao gravar cache de CEP->bairro - resultado desta sessao nao sera persistido.")


def _consultar_viacep(cep_limpo: str) -> str | None:
    try:
        resp = requests.get(f"https://viacep.com.br/ws/{cep_limpo}/json/", timeout=_TIMEOUT_S)
        resp.raise_for_status()
        dados = resp.json()
    except Exception:
        logger.warning("Falha ao consultar CEP %s no ViaCEP - bairro nao resolvido.", cep_limpo)
        return None
    if dados.get("erro"):
        return None
    return dados.get("bairro") or None


def bairros_por_ceps(ceps: list, max_novas_consultas: int | None = None) -> dict:
    """Resolve o bairro de uma lista de CEPs via ViaCEP, com cache em
    disco (nunca repete uma consulta ja feita para o mesmo CEP - nem
    dentro da mesma sessao, nem entre execucoes). Retorna um dict
    cep_original -> bairro (ou None quando nao foi possivel resolver) -
    CEPs presentes no cache SEMPRE entram no resultado, independente do
    limite. Nunca lanca excecao.

    `max_novas_consultas` (opcional): limite de consultas de REDE (CEPs
    ainda nao cacheados) nesta chamada - protege contra travar a analise
    em municipios com muitos CEPs distintos e nada em cache ainda. CEPs
    que excederem o limite simplesmente nao entram no resultado desta vez
    (ficam disponiveis para uma proxima chamada, quando podem ja estar
    cacheados de outra analise)."""
    cache = _carregar_cache()
    resultado: dict = {}
    alterou = False
    novas_consultas = 0

    for cep_original in ceps:
        if not cep_original:
            continue
        cep_limpo = "".join(ch for ch in str(cep_original) if ch.isdigit())
        if len(cep_limpo) != 8:
            continue
        if cep_limpo in cache:
            resultado[cep_original] = cache[cep_limpo]
            continue
        if max_novas_consultas is not None and novas_consultas >= max_novas_consultas:
            continue
        bairro = _consultar_viacep(cep_limpo)
        cache[cep_limpo] = bairro
        resultado[cep_original] = bairro
        novas_consultas += 1
        alterou = True

    if alterou:
        _salvar_cache(cache)
    return resultado
