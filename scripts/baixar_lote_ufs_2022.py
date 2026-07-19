"""Baixa/converte votacao_secao_2022 para uma lista de UFs, sequencialmente,
com log de progresso e tolerancia a falha individual (uma UF que falhar nao
interrompe as demais). Uso: python scripts/baixar_lote_ufs_2022.py UF1 UF2 ...
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.uf_data_bootstrap import garantir_dados_uf, caminho_votacao_secao


def main(ufs: list[str]) -> None:
    for uf in ufs:
        destino = caminho_votacao_secao(uf, ano=2022)
        if destino.exists():
            print(f"[{uf}] ja existe ({destino.stat().st_size/1e6:.1f} MB) - pulando")
            continue
        print(f"[{uf}] baixando/convertendo votacao_secao_2022...")
        t0 = time.time()
        ok = garantir_dados_uf(uf, ano=2022)
        dt = time.time() - t0
        if ok:
            tam = destino.stat().st_size / 1e6
            print(f"[{uf}] OK em {dt:.1f}s - {tam:.1f} MB")
        else:
            print(f"[{uf}] FALHOU apos {dt:.1f}s")


if __name__ == "__main__":
    main([u.upper() for u in sys.argv[1:]])
