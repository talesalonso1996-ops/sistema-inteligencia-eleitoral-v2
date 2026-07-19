"""Exportacao para Excel multi-abas (secao 16 do briefing)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

_LIMITE_NOME_ABA = 31  # limite do Excel para nomes de planilha


def exportar_excel(caminho: str | Path, planilhas: dict[str, pd.DataFrame]) -> Path:
    """Exporta um dicionario {nome_da_aba: dataframe} para um unico
    arquivo .xlsx, com cabecalho formatado, colunas com largura ajustada
    e painel congelado na primeira linha."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(caminho, engine="xlsxwriter") as writer:
        workbook = writer.book
        formato_cabecalho = workbook.add_format(
            {"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1}
        )

        for nome, df in planilhas.items():
            aba = nome[:_LIMITE_NOME_ABA] if nome else "Dados"
            if df is None or df.empty:
                df = pd.DataFrame({"aviso": ["Sem dados disponiveis para esta secao."]})
            df.to_excel(writer, sheet_name=aba, index=False, startrow=0)
            planilha = writer.sheets[aba]

            for col_idx, col_nome in enumerate(df.columns):
                planilha.write(0, col_idx, col_nome, formato_cabecalho)
                largura = min(max(len(str(col_nome)), df[col_nome].astype(str).str.len().max() if len(df) else 10) + 2, 45)
                planilha.set_column(col_idx, col_idx, largura)

            planilha.freeze_panes(1, 0)

    return caminho
