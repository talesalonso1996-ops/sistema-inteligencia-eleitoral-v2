"""Regressao linear e logistica: desempenho eleitoral explicado por
variaveis demograficas do territorio (secao 10.2 do briefing).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd
import statsmodels.api as sm

from .data_validation import validar_amostra_minima
from .utils import DataIssue, get_logger

logger = get_logger(__name__)

_AMOSTRA_MINIMA_POR_VARIAVEL = 10  # observacoes por variavel preditora, regra pratica


@dataclass
class ResultadoRegressao:
    r_quadrado: float
    r_quadrado_ajustado: float
    n_observacoes: int
    coeficientes: pd.DataFrame  # variavel, coeficiente, erro_padrao, p_valor, significativo
    intercepto: float
    variaveis_utilizadas: list[str]
    erro_padrao_cluster: bool = False
    limitacoes: str = (
        "Regressao com dados agregados por territorio (ecological regression): "
        "as relacoes encontradas valem para o territorio, nao permitem inferir "
        "comportamento de eleitores individuais (falacia ecologica)."
    )

    def __post_init__(self) -> None:
        if self.erro_padrao_cluster:
            self.limitacoes += (
                " A unidade de observacao e a secao eleitoral (varias por local de "
                "votacao); secoes do mesmo local compartilham o mesmo perfil "
                "demografico (mesmo predio/coordenada), entao nao sao amostras "
                "independentes - o erro-padrao usado e robusto a cluster (agrupado "
                "por local de votacao), que evita superestimar a precisao dos "
                "coeficientes nessa situacao."
            )


def _remover_variaveis_sem_variancia(
    dados: pd.DataFrame, variaveis_validas: list[str], nome_analise: str,
) -> tuple[list[str], list[DataIssue]]:
    """Remove variaveis com variancia zero (mesmo valor em todas as
    observacoes) na amostra apos o dropna - situacao real e frequente
    (ex.: municipio 100% urbanizado onde todo territorio tem 100% de
    agua encanada). Uma coluna constante, somada ao intercepto da
    regressao, e uma combinacao linear exata e quebra o ajuste (matriz
    singular) - nao e um erro de dado, e uma propriedade da amostra."""
    sem_variancia = [v for v in variaveis_validas if dados[v].nunique(dropna=True) <= 1]
    if not sem_variancia:
        return variaveis_validas, []
    issue = DataIssue(
        etapa=nome_analise,
        severidade="aviso",
        mensagem=(
            f"Variavel(is) sem variacao nesta amostra (mesmo valor em todos os "
            f"territorios) excluida(s) da regressao: {', '.join(sem_variancia)}."
        ),
    )
    return [v for v in variaveis_validas if v not in sem_variancia], [issue]


def regressao_linear_votos(
    df: pd.DataFrame, coluna_alvo: str, variaveis: list[str], coluna_cluster: str | None = None,
) -> tuple[ResultadoRegressao | None, list[DataIssue]]:
    """Regressao OLS (minimos quadrados) do percentual de votos do
    candidato por territorio em funcao das variaveis demograficas
    informadas. Exige pelo menos 10 observacoes por variavel preditora.

    `coluna_cluster` (opcional): quando a unidade de observacao e mais fina
    que o local de votacao (ex.: secao/urna - varias secoes compartilham o
    mesmo local fisico e portanto o mesmo perfil demografico), informar a
    coluna que identifica o local fisico para usar erro-padrao robusto a
    cluster - sem isso, observacoes correlacionadas (mesmo predio)
    fariam a regressao parecer mais precisa do que realmente e."""
    variaveis_validas = [v for v in variaveis if v in df.columns]
    tem_cluster = coluna_cluster is not None and coluna_cluster in df.columns
    colunas = [coluna_alvo] + variaveis_validas + ([coluna_cluster] if tem_cluster else [])
    dados = df[colunas].dropna(subset=[coluna_alvo] + variaveis_validas)

    variaveis_validas, issues_variancia = _remover_variaveis_sem_variancia(
        dados, variaveis_validas, "regressao_linear_votos"
    )

    minimo = _AMOSTRA_MINIMA_POR_VARIAVEL * max(len(variaveis_validas), 1)
    issues = validar_amostra_minima(len(dados), minimo, "regressao_linear_votos")
    if issues or not variaveis_validas:
        return None, issues_variancia + issues

    x = sm.add_constant(dados[variaveis_validas])
    y = dados[coluna_alvo]
    if tem_cluster:
        modelo = sm.OLS(y, x).fit(cov_type="cluster", cov_kwds={"groups": dados[coluna_cluster]})
    else:
        modelo = sm.OLS(y, x).fit()

    coeficientes = pd.DataFrame(
        {
            "variavel": modelo.params.index,
            "coeficiente": modelo.params.values.round(4),
            "erro_padrao": modelo.bse.values.round(4),
            "p_valor": modelo.pvalues.values.round(4),
        }
    )
    coeficientes["significativo"] = coeficientes["p_valor"] < 0.05
    coeficientes = coeficientes[coeficientes["variavel"] != "const"].reset_index(drop=True)

    resultado = ResultadoRegressao(
        r_quadrado=round(float(modelo.rsquared), 3),
        r_quadrado_ajustado=round(float(modelo.rsquared_adj), 3),
        n_observacoes=int(modelo.nobs),
        coeficientes=coeficientes,
        intercepto=round(float(modelo.params.get("const", 0.0)), 4),
        variaveis_utilizadas=variaveis_validas,
        erro_padrao_cluster=tem_cluster,
    )
    return resultado, issues_variancia


@dataclass
class ResultadoRegressaoLogistica:
    limiar_usado: float
    n_positivos: int
    n_negativos: int
    pseudo_r2_mcfadden: float
    acuracia: float
    matriz_confusao: pd.DataFrame  # linhas=real, colunas=previsto (0/1)
    coeficientes: pd.DataFrame  # variavel, coeficiente, odds_ratio, p_valor, significativo
    intercepto: float
    interpretacoes: list[str]
    variaveis_utilizadas: list[str]
    erro_padrao_cluster: bool = False
    limitacoes: str = (
        "Regressao logistica com dados agregados por territorio (ecological "
        "regression): as relacoes encontradas valem para o territorio, nao "
        "permitem inferir o comportamento de eleitores individuais. Acuracia "
        "e matriz de confusao medidas dentro da propria amostra de ajuste "
        "(sem separacao treino/teste - amostra pequena nao comporta split)."
    )

    def __post_init__(self) -> None:
        if self.erro_padrao_cluster:
            self.limitacoes += (
                " A unidade de observacao e a secao eleitoral (varias por local de "
                "votacao); secoes do mesmo local compartilham o mesmo perfil "
                "demografico (mesmo predio/coordenada), entao nao sao amostras "
                "independentes - o erro-padrao usado e robusto a cluster (agrupado "
                "por local de votacao), que evita superestimar a precisao dos "
                "coeficientes/p-valores nessa situacao."
            )


def regressao_logistica_bom_desempenho(
    df: pd.DataFrame,
    coluna_pct_votos: str,
    variaveis: list[str],
    limiar: float | None = None,
    coluna_cluster: str | None = None,
) -> tuple[ResultadoRegressaoLogistica | None, list[DataIssue]]:
    """Classifica cada territorio como "boa votacao" (1) ou nao (0) e ajusta
    uma regressao logistica contra as variaveis demograficas informadas -
    responde "que caracteristicas demograficas aumentam a chance deste
    candidato ter uma boa votacao num territorio?".

    O limiar de "boa votacao" default e a MEDIANA do proprio candidato em
    `coluna_pct_votos` entre os territorios onde ele concorreu - ou seja,
    mede desempenho acima da propria mediana (equilibra a amostra ~50/50 e
    mede forca relativa do candidato, coerente com a mesma logica usada no
    indice de performance territorial).

    `coluna_cluster` (opcional): ver documentacao equivalente em
    regressao_linear_votos - usar quando a unidade de observacao e mais
    fina que o local de votacao (secao/urna)."""
    variaveis_validas = [v for v in variaveis if v in df.columns]
    tem_cluster = coluna_cluster is not None and coluna_cluster in df.columns
    colunas = [coluna_pct_votos] + variaveis_validas + ([coluna_cluster] if tem_cluster else [])
    dados = df[colunas].dropna(subset=[coluna_pct_votos] + variaveis_validas)

    variaveis_validas, issues_variancia = _remover_variaveis_sem_variancia(
        dados, variaveis_validas, "regressao_logistica_bom_desempenho"
    )

    minimo = _AMOSTRA_MINIMA_POR_VARIAVEL * max(len(variaveis_validas), 1)
    issues = validar_amostra_minima(len(dados), minimo, "regressao_logistica_bom_desempenho")
    if issues or not variaveis_validas:
        return None, issues_variancia + issues

    limiar_usado = limiar if limiar is not None else float(dados[coluna_pct_votos].median())
    alvo = (dados[coluna_pct_votos] >= limiar_usado).astype(int)
    n_positivos, n_negativos = int(alvo.sum()), int((1 - alvo).sum())
    if n_positivos < 3 or n_negativos < 3:
        issue = DataIssue(
            etapa="regressao_logistica_bom_desempenho",
            severidade="erro",
            mensagem=(
                f"Classes desbalanceadas demais para regressao logistica "
                f"({n_positivos} positivos / {n_negativos} negativos com limiar {limiar_usado:.2f})."
            ),
        )
        return None, [issue]

    x = sm.add_constant(dados[variaveis_validas])
    try:
        if tem_cluster:
            modelo = sm.Logit(alvo, x).fit(
                disp=0, cov_type="cluster", cov_kwds={"groups": dados[coluna_cluster]}
            )
        else:
            modelo = sm.Logit(alvo, x).fit(disp=0)
    except Exception as exc:  # separacao perfeita ou nao-convergencia
        logger.warning("Regressao logistica nao convergiu: %s", exc)
        return None, issues_variancia + [
            DataIssue(
                etapa="regressao_logistica_bom_desempenho",
                severidade="erro",
                mensagem=(
                    "O modelo nao convergiu (provavel separacao perfeita entre as "
                    "classes com esta amostra pequena) - regressao logistica nao "
                    "disponivel para esta candidatura."
                ),
            )
        ]

    coeficientes = pd.DataFrame(
        {
            "variavel": modelo.params.index,
            "coeficiente": modelo.params.values.round(4),
            "odds_ratio": [round(math.exp(c), 3) for c in modelo.params.values],
            "p_valor": modelo.pvalues.values.round(4),
        }
    )
    coeficientes["significativo"] = coeficientes["p_valor"] < 0.05
    intercepto = float(modelo.params.get("const", 0.0))
    coeficientes = coeficientes[coeficientes["variavel"] != "const"].reset_index(drop=True)

    interpretacoes = [
        (
            f"Cada aumento de 1 ponto percentual em '{row.variavel}' multiplica as "
            f"chances de boa votacao por {row.odds_ratio:.2f}x "
            f"({'aumenta' if row.odds_ratio > 1 else 'reduz'} a chance)."
        )
        for row in coeficientes[coeficientes["significativo"]].itertuples()
    ]
    if not interpretacoes:
        interpretacoes = [
            "Nenhuma variavel demografica teve efeito estatisticamente "
            "significativo (p<0.05) sobre a chance de boa votacao nesta amostra."
        ]

    previsto = (modelo.predict(x) >= 0.5).astype(int)
    acuracia = round(float((previsto == alvo).mean()), 3)
    matriz_confusao = pd.crosstab(
        alvo.rename("real"), previsto.rename("previsto")
    ).reindex(index=[0, 1], columns=[0, 1], fill_value=0)

    pseudo_r2 = round(float(1 - modelo.llf / modelo.llnull), 3) if modelo.llnull else 0.0

    resultado = ResultadoRegressaoLogistica(
        limiar_usado=round(limiar_usado, 2),
        n_positivos=n_positivos,
        n_negativos=n_negativos,
        pseudo_r2_mcfadden=pseudo_r2,
        acuracia=acuracia,
        matriz_confusao=matriz_confusao,
        coeficientes=coeficientes,
        intercepto=round(intercepto, 4),
        interpretacoes=interpretacoes,
        variaveis_utilizadas=variaveis_validas,
        erro_padrao_cluster=tem_cluster,
    )
    return resultado, issues_variancia
