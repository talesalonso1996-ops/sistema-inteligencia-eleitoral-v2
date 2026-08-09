"""Testes de regressao: downloads com conteudo invalido nao podem ficar
cacheados permanentemente (bug real corrigido em uf_data_bootstrap.py e
cloud_data_bootstrap.py - ver comentarios nas duas funcoes). Mocka a rede
(requests) - nunca bate na internet de verdade."""
from unittest.mock import patch

import src.cloud_data_bootstrap as cloud_data_bootstrap
import src.uf_data_bootstrap as uf_data_bootstrap


class _RespostaFalsa:
    def __init__(self, conteudo: bytes):
        self.content = conteudo
        self._conteudo = conteudo

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=1024 * 1024):
        yield self._conteudo


def test_fallback_2018_descarta_download_corrompido(tmp_path):
    """Resposta HTTP 200 mas com corpo invalido (ex.: pagina HTML de erro
    de um proxy, nao o parquet de verdade) precisa ser descartada - nunca
    gravada em `destino` (senao fica corrompida ali para sempre, ja que
    chamadas futuras so checam destino.exists())."""
    destino = tmp_path / "votacao_secao_2018_SP.parquet"
    with patch.object(uf_data_bootstrap, "_baixar", return_value=b"<html>erro 200 falso</html>"):
        ok = uf_data_bootstrap._garantir_votacao_secao_2018_fallback("SP", destino)
    assert ok is False
    assert not destino.exists()
    assert not destino.with_suffix(".tmp").exists()


def test_garantir_dados_cloud_descarta_download_corrompido(tmp_path, monkeypatch):
    destino_dir = tmp_path / "data" / "raw"
    monkeypatch.setattr(cloud_data_bootstrap, "resolve_path", lambda rel: destino_dir)
    with patch("src.cloud_data_bootstrap.requests.get", return_value=_RespostaFalsa(b"nao sou um parquet")):
        try:
            cloud_data_bootstrap._baixar("arquivo_falso.parquet", "https://exemplo.invalido/base")
            falhou = False
        except ValueError:
            falhou = True
    assert falhou is True
    assert not (destino_dir / "arquivo_falso.parquet").exists()
    assert not (destino_dir / "arquivo_falso.parquet.tmp").exists()
