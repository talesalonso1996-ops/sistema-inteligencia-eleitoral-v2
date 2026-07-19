"""Regressao linear e logistica: desempenho eleitoral explicado por
variaveis demograficas do territorio (secao 10.2 do briefing).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .data_validation import validar_amostra_minima
from .utils import DataIssue, get_logger

logger = get_logger(__name__)

_AMOSTRA_MINIMA_POR_VARIAVEL = 10  # observacoes por variavel preditora, regra pratica


def _resolver_colunas_cluster(
    df: pd.DataFrame, coluna_cluster: str | list[str] | None, nome_analise: str,
) -> tuple[list[str], list[DataIssue]]:
    """Normaliza `coluna_cluster` (string simples, lista de ate 2 colunas,
    ou None) para uma lista validada de colunas realmente presentes em
    `df`. statsmodels (`cov_type='cluster'`) suporta no maximo 2 dimensoes
    de cluster simultaneas (`cov_cluster_2groups`) - mais de 2 colunas sao
    truncadas com aviso explicito, nunca descartadas silenciosamente."""
    if coluna_cluster is None:
        return [], []
    colunas = [coluna_cluster] if isinstance(coluna_cluster, str) else list(coluna_cluster)
    issues: list[DataIssue] = []
    if len(colunas) > 2:
        issues.append(DataIssue(
            etapa=nome_analise, severidade="aviso",
            mensagem=(
                f"Cluster com mais de 2 colunas informado ({', '.join(colunas)}) - "
                "statsmodels so suporta ate 2 dimensoes de cluster; usando apenas as "
                f"2 primeiras ({', '.join(colunas[:2])})."
            ),
        ))
        colunas = colunas[:2]
    colunas_validas = [c for c in colunas if c in df.columns]
    faltando = [c for c in colunas if c not in df.columns]
    if faltando:
        issues.append(DataIssue(
            etapa=nome_analise, severidade="aviso",
            mensagem=f"Coluna(s) de cluster ausente(s) nesta amostra, ignorada(s): {', '.join(faltando)}.",
        ))
    return colunas_validas, issues


def _grupos_cluster(dados: pd.DataFrame, colunas_cluster: list[str]):
    """Monta o argumento `groups` para `cov_kwds` do statsmodels. Para 1
    coluna, uma Series simples basta. Para 2 colunas (cluster de 2 vias,
    `cov_cluster_2groups`), o statsmodels exige um ndarray 2D HOMOGENEO e
    C-contiguo (ele faz `arr.view([('', arr.dtype)] * 2)` internamente,
    que falha com "Cannot change data-type for array of references" se o
    array for dtype=object - o que sempre acontece se as 2 colunas tiverem
    dtypes diferentes, ex.: `local_votacao_id` (string) + `CD_MUNICIPIO`
    (int), o caso real de uso desta funcao). Corrigido convertendo as 2
    colunas para string (dtype unicode de largura fixa, homogeneo) antes de
    montar o array."""
    if len(colunas_cluster) == 1:
        return dados[colunas_cluster[0]]
    arr = dados[colunas_cluster].astype(str).to_numpy(dtype=str)
    return np.ascontiguousarray(arr)


@dataclass
class ResultadoRegressao:
    r_quadrado: float
    r_quadrado_ajustado: float
    n_observacoes: int
    coeficientes: pd.DataFrame  # variavel, coeficiente, erro_padrao, p_valor, significativo
    intercepto: float
    variaveis_utilizadas: list[str]
    erro_padrao_cluster: bool = False
    colunas_cluster_utilizadas: list[str] = field(default_factory=list)
    limitacoes: str = (
        "Regressao com dados agregados por territorio (ecological regression): "
        "as relacoes encontradas valem para o territorio, nao permitem inferir "
        "comportamento de eleitores individuais (falacia ecologica)."
    )

    def __post_init__(self) -> None:
        if self.erro_padrao_cluster and len(self.colunas_cluster_utilizadas) == 2:
            self.limitacoes += (
                " A unidade de observacao e mais fina que o territorio agregado usual "
                f"(cluster de 2 vias: {self.colunas_cluster_utilizadas[0]} e "
                f"{self.colunas_cluster_utilizadas[1]}) - o erro-padrao usado e robusto "
                "a cluster nessas duas dimensoes simultaneamente, evitando superestimar "
                "a precisao dos coeficientes quando observacoes dentro do mesmo local de "
                "votacao E dentro do mesmo municipio nao sao independentes."
            )
        elif self.erro_padrao_cluster:
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
    df: pd.DataFrame, coluna_alvo: str, variaveis: list[str],
    coluna_cluster: str | list[str] | None = None,
) -> tuple[ResultadoRegressao | None, list[DataIssue]]:
    """Regressao OLS (minimos quadrados) do percentual de votos do
    candidato por territorio em funcao das variaveis demograficas
    informadas. Exige pelo menos 10 observacoes por variavel preditora.

    `coluna_cluster` (opcional): quando a unidade de observacao e mais fina
    que o local de votacao (ex.: secao/urna - varias secoes compartilham o
    mesmo local fisico e portanto o mesmo perfil demografico), informar a
    coluna que identifica o local fisico para usar erro-padrao robusto a
    cluster - sem isso, observacoes correlacionadas (mesmo predio)
    fariam a regressao parecer mais precisa do que realmente e. Tambem
    aceita uma LISTA de ate 2 colunas (cluster de 2 vias, ex.:
    `["local_votacao_id", "CD_MUNICIPIO"]`) - usado pela "Regressao Geral"
    de cargos estaduais (V2), onde observacoes tambem se agrupam por
    municipio, alem de por predio."""
    variaveis_validas = [v for v in variaveis if v in df.columns]
    colunas_cluster, issues_cluster = _resolver_colunas_cluster(df, coluna_cluster, "regressao_linear_votos")
    tem_cluster = bool(colunas_cluster)
    colunas = [coluna_alvo] + variaveis_validas + colunas_cluster
    dados = df[colunas].dropna(subset=[coluna_alvo] + variaveis_validas)

    variaveis_validas, issues_variancia = _remover_variaveis_sem_variancia(
        dados, variaveis_validas, "regressao_linear_votos"
    )

    minimo = _AMOSTRA_MINIMA_POR_VARIAVEL * max(len(variaveis_validas), 1)
    issues = validar_amostra_minima(len(dados), minimo, "regressao_linear_votos")
    if issues or not variaveis_validas:
        return None, issues_cluster + issues_variancia + issues

    x = sm.add_constant(dados[variaveis_validas])
    y = dados[coluna_alvo]
    if tem_cluster:
        grupos = _grupos_cluster(dados, colunas_cluster)
        modelo = sm.OLS(y, x).fit(cov_type="cluster", cov_kwds={"groups": grupos})
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
        colunas_cluster_utilizadas=colunas_cluster,
    )
    return resultado, issues_cluster + issues_variancia


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
    colunas_cluster_utilizadas: list[str] = field(default_factory=list)
    limitacoes: str = (
        "Regressao logistica com dados agregados por territorio (ecological "
        "regression): as relacoes encontradas valem para o territorio, nao "
        "permitem inferir o comportamento de eleitores individuais. Acuracia "
        "e matriz de confusao medidas dentro da propria amostra de ajuste "
        "(sem separacao treino/teste - amostra pequena nao comporta split)."
    )

    def __post_init__(self) -> None:
        if self.erro_padrao_cluster and len(self.colunas_cluster_utilizadas) == 2:
            self.limitacoes += (
                " A unidade de observacao e mais fina que o territorio agregado usual "
                f"(cluster de 2 vias: {self.colunas_cluster_utilizadas[0]} e "
                f"{self.colunas_cluster_utilizadas[1]}) - o erro-padrao usado e robusto "
                "a cluster nessas duas dimensoes simultaneamente, evitando superestimar "
                "a precisao dos coeficientes/p-valores quando observacoes dentro do "
                "mesmo local de votacao E dentro do mesmo municipio nao sao "
                "independentes."
            )
        elif self.erro_padrao_cluster:
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
    coluna_cluster: str | list[str] | None = None,
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
    fina que o local de votacao (secao/urna). Tambem aceita uma LISTA de
    ate 2 colunas (cluster de 2 vias)."""
    variaveis_validas = [v for v in variaveis if v in df.columns]
    colunas_cluster, issues_cluster = _resolver_colunas_cluster(
        df, coluna_cluster, "regressao_logistica_bom_desempenho"
    )
    tem_cluster = bool(colunas_cluster)
    colunas = [coluna_pct_votos] + variaveis_validas + colunas_cluster
    dados = df[colunas].dropna(subset=[coluna_pct_votos] + variaveis_validas)

    variaveis_validas, issues_variancia = _remover_variaveis_sem_variancia(
        dados, variaveis_validas, "regressao_logistica_bom_desempenho"
    )

    minimo = _AMOSTRA_MINIMA_POR_VARIAVEL * max(len(variaveis_validas), 1)
    issues = validar_amostra_minima(len(dados), minimo, "regressao_logistica_bom_desempenho")
    if issues or not variaveis_validas:
        return None, issues_cluster + issues_variancia + issues

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
            grupos = _grupos_cluster(dados, colunas_cluster)
            modelo = sm.Logit(alvo, x).fit(disp=0, cov_type="cluster", cov_kwds={"groups": grupos})
        else:
            modelo = sm.Logit(alvo, x).fit(disp=0)
    except Exception as exc:  # separacao perfeita ou nao-convergencia
        logger.warning("Regressao logistica nao convergiu: %s", exc)
        return None, issues_cluster + issues_variancia + [
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
        colunas_cluster_utilizadas=colunas_cluster,
    )
    return resultado, issues_cluster + issues_variancia
