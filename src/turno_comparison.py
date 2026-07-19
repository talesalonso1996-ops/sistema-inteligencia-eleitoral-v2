"""Comparacao entre 1o e 2o turno para cargos MAJORITARIOS com previsao de
2o turno (Presidente, Governador, Prefeito em municipios grandes).

NAO se aplica a cargos proporcionais (Vereador, Deputado Federal/Estadual/
Distrital) nem a Senador (majoritario, mas sem 2o turno previsto na
Constituicao) - o chamador deve conferir
`electoral_scope.resolver_escopo(...).permite_segundo_turno` antes de usar
este modulo (o proprio candidate_finder/electoral_scope ja bloqueiam
`turno=2` para esses cargos com EscopoInvalidoError).

Reaproveita a saida de electoral_metrics.desempenho_territorial (mesmo
formato ja usado em cada turno separadamente) - "territorio conquistado"/
"territorio perdido" e definido por MUDANCA DE LIDERANCA no territorio
(colocacao do candidato: 1o lugar vs. nao-1o-lugar entre T1 e T2), nao por
um limiar arbitrario de variacao percentual - criterio objetivo e ja
calculado (colocacao) em vez de inventar um novo.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class ComparacaoTurnos:
    votos_turno1: int
    votos_turno2: int
    variacao_absoluta: int
    variacao_percentual: float
    pct_validos_turno1: float
    pct_validos_turno2: float
    variacao_pct_validos: float
    n_territorios_comuns: int
    territorios_conquistados: list[str]  # nao era 1o lugar no T1, passou a ser no T2
    territorios_perdidos: list[str]  # era 1o lugar no T1, deixou de ser no T2
    comparecimento_turno1: float | None
    comparecimento_turno2: float | None
    variacao_comparecimento_pct: float | None
    detalhe_territorial: pd.DataFrame


def comparar_turnos(
    territorial_t1: pd.DataFrame,
    territorial_t2: pd.DataFrame,
    nivel: str,
    coluna_votos: str = "votos_candidato",
    coluna_pct: str = "pct_votos_validos_territorio",
    coluna_comparecimento: str = "comparecimento",
) -> ComparacaoTurnos:
    """`territorial_t1`/`territorial_t2`: saida de
    electoral_metrics.desempenho_territorial (opcionalmente ja passada por
    enriquecer_com_comparecimento_abstencao) para o MESMO candidato, T1 e
    T2 respectivamente, no MESMO `nivel` territorial."""
    votos_t1 = int(territorial_t1[coluna_votos].sum())
    votos_t2 = int(territorial_t2[coluna_votos].sum())
    variacao_absoluta = votos_t2 - votos_t1
    variacao_percentual = round(100 * variacao_absoluta / votos_t1, 2) if votos_t1 else 0.0

    pct_t1 = float(territorial_t1[coluna_pct].mean()) if coluna_pct in territorial_t1.columns else 0.0
    pct_t2 = float(territorial_t2[coluna_pct].mean()) if coluna_pct in territorial_t2.columns else 0.0

    detalhe = territorial_t1[[nivel, coluna_votos, coluna_pct, "colocacao"]].merge(
        territorial_t2[[nivel, coluna_votos, coluna_pct, "colocacao"]],
        on=nivel, how="outer", suffixes=("_t1", "_t2"),
    )
    detalhe[f"{coluna_votos}_t1"] = detalhe[f"{coluna_votos}_t1"].fillna(0)
    detalhe[f"{coluna_votos}_t2"] = detalhe[f"{coluna_votos}_t2"].fillna(0)
    detalhe["delta_votos"] = detalhe[f"{coluna_votos}_t2"] - detalhe[f"{coluna_votos}_t1"]
    detalhe["delta_pct_votos_validos"] = (
        detalhe[f"{coluna_pct}_t2"].fillna(0) - detalhe[f"{coluna_pct}_t1"].fillna(0)
    ).round(2)

    comuns = detalhe.dropna(subset=["colocacao_t1", "colocacao_t2"])
    conquistados = comuns[(comuns["colocacao_t1"] != 1) & (comuns["colocacao_t2"] == 1)][nivel].tolist()
    perdidos = comuns[(comuns["colocacao_t1"] == 1) & (comuns["colocacao_t2"] != 1)][nivel].tolist()

    comp_t1 = comp_t2 = variacao_comparecimento = None
    if coluna_comparecimento in territorial_t1.columns and coluna_comparecimento in territorial_t2.columns:
        if territorial_t1[coluna_comparecimento].notna().any() and territorial_t2[coluna_comparecimento].notna().any():
            comp_t1 = float(territorial_t1[coluna_comparecimento].sum())
            comp_t2 = float(territorial_t2[coluna_comparecimento].sum())
            variacao_comparecimento = round(100 * (comp_t2 - comp_t1) / comp_t1, 2) if comp_t1 else None

    return ComparacaoTurnos(
        votos_turno1=votos_t1,
        votos_turno2=votos_t2,
        variacao_absoluta=variacao_absoluta,
        variacao_percentual=variacao_percentual,
        pct_validos_turno1=round(pct_t1, 2),
        pct_validos_turno2=round(pct_t2, 2),
        variacao_pct_validos=round(pct_t2 - pct_t1, 2),
        n_territorios_comuns=len(comuns),
        territorios_conquistados=[str(t) for t in conquistados],
        territorios_perdidos=[str(t) for t in perdidos],
        comparecimento_turno1=comp_t1,
        comparecimento_turno2=comp_t2,
        variacao_comparecimento_pct=variacao_comparecimento,
        detalhe_territorial=detalhe,
    )


def comparar_turnos_vs_concorrente(
    delta_candidato_t1: pd.DataFrame, delta_candidato_t2: pd.DataFrame, nivel: str, nome_concorrente: str,
) -> pd.DataFrame:
    """Variacao do DELTA contra um concorrente especifico (saida de
    competitor_analysis.delta_vs_rivais, coluna 'delta') entre T1 e T2 -
    mostra onde o candidato melhorou/piorou frente a esse rival
    especificamente, territorio a territorio."""
    t1 = delta_candidato_t1[delta_candidato_t1["rival"] == nome_concorrente][[nivel, "delta"]].rename(
        columns={"delta": "delta_t1"}
    )
    t2 = delta_candidato_t2[delta_candidato_t2["rival"] == nome_concorrente][[nivel, "delta"]].rename(
        columns={"delta": "delta_t2"}
    )
    comparado = t1.merge(t2, on=nivel, how="outer")
    comparado["delta_t1"] = comparado["delta_t1"].fillna(0)
    comparado["delta_t2"] = comparado["delta_t2"].fillna(0)
    comparado["variacao_delta"] = comparado["delta_t2"] - comparado["delta_t1"]
    return comparado.sort_values("variacao_delta", ascending=False).reset_index(drop=True)
