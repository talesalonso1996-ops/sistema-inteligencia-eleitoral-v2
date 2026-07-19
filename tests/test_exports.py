import pandas as pd

from src.excel_exporter import exportar_excel


def test_exportar_excel_cria_arquivo_com_todas_as_abas(tmp_path):
    planilhas = {
        "Resumo": pd.DataFrame({"metrica": ["votos"], "valor": [100]}),
        "Ranking": pd.DataFrame({"nome": ["A", "B"], "votos": [50, 30]}),
    }
    destino = tmp_path / "teste.xlsx"
    caminho = exportar_excel(destino, planilhas)

    assert caminho.exists()
    lido = pd.read_excel(caminho, sheet_name=None)
    assert set(lido.keys()) == {"Resumo", "Ranking"}
    assert len(lido["Ranking"]) == 2


def test_exportar_excel_aba_vazia_nao_quebra(tmp_path):
    planilhas = {"Vazia": pd.DataFrame()}
    destino = tmp_path / "teste_vazio.xlsx"
    caminho = exportar_excel(destino, planilhas)
    assert caminho.exists()
