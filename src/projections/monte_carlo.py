"""Cenarios/projecoes Monte Carlo (secao 19 do briefing de expansao SIET).

METODOLOGIA (o que isto e, e o que isto NAO e): esta e uma simulacao de
Monte Carlo PARAMETRICA que propaga a INCERTEZA ESTATISTICA REAL ja
estimada por `src/regression_models.py` - cada coeficiente de um modelo JA
AJUSTADO sobre dado eleitoral real (`regressao_linear_votos`/
`regressao_logistica_bom_desempenho`) tem um erro-padrao real, calculado
pelo proprio ajuste estatistico. Em vez de fabricar uma taxa de
crescimento ou uma pesquisa hipotetica para gerar cenarios "conservador/
moderado/otimista", este modulo sorteia repetidamente (`n_simulacoes`
vezes) um conjunto de coeficientes de uma distribuicao Normal(coeficiente,
erro_padrao) - a mesma distribuicao amostral que a teoria da regressao
OLS/logit ja assume para esses coeficientes - e aplica cada sorteio aos
dados REAIS de cada territorio, produzindo uma distribuicao de previsoes.

O que a simulacao propaga: incerteza de ESTIMACAO dos coeficientes de um
modelo ja ajustado sobre uma eleicao ja ocorrida.

O que a simulacao NAO propaga (limitacao declarada, nao escondida):
turnout futuro, comportamento de rivais, mudanca de cenario politico, ou
qualquer evento de uma eleicao ainda nao ocorrida. Um territorio com banda
estreita entre p5 e p95 e um territorio cuja previsao O MODELO ESTIMA COM
MAIS CONFIANCA, nao um territorio "seguro" no sentido eleitoral coloquial.

O intercepto e tratado como fixo na simulacao (os objetos
ResultadoRegressao/ResultadoRegressaoLogistica nao expoem o erro-padrao do
intercepto) - simplificacao real, declarada em `limitacoes`."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .. import regression_models as _rm
from ..utils import get_logger

logger = get_logger(__name__)

_LIMITACOES_LINEAR = (
    "Simulacao de Monte Carlo PARAMETRICA: propaga a incerteza real de estimacao dos "
    "coeficientes (erro-padrao) de uma regressao linear JA AJUSTADA sobre dado eleitoral "
    "real, sorteando de Normal(coeficiente, erro_padrao) - nao simula turnout futuro, "
    "comportamento de rivais, nem qualquer evento de uma eleicao ainda nao ocorrida. "
    "O intercepto e tratado como fixo (o modelo nao expoe seu erro-padrao). Previsoes "
    "sao limitadas ao intervalo [0, 100] por serem percentuais de votos validos."
)
_LIMITACOES_LOGISTICA = (
    "Simulacao de Monte Carlo PARAMETRICA: propaga a incerteza real de estimacao dos "
    "coeficientes (erro-padrao) de uma regressao logistica JA AJUSTADA sobre dado "
    "eleitoral real, sorteando de Normal(coeficiente, erro_padrao) - nao simula turnout "
    "futuro, comportamento de rivais, nem qualquer evento de uma eleicao ainda nao "
    "ocorrida. O intercepto e tratado como fixo (o modelo nao expoe seu erro-padrao)."
)


@dataclass
class ResultadoSimulacaoLinear:
    territorios: pd.DataFrame  # coluna_territorio, valor_observado, mediana_simulada, p5, p95
    matriz_simulacoes: np.ndarray = field(repr=False)  # (n_simulacoes, n_territorios), percentual 0-100
    variaveis_utilizadas: list[str] = field(default_factory=list)
    n_simulacoes: int = 0
    seed: int = 0
    limitacoes: str = _LIMITACOES_LINEAR


@dataclass
class ResultadoSimulacaoLogistica:
    territorios: pd.DataFrame  # coluna_territorio, mediana_simulada, p5, p95 (probabilidade 0-1)
    matriz_simulacoes: np.ndarray = field(repr=False)  # (n_simulacoes, n_territorios), probabilidade 0-1
    variaveis_utilizadas: list[str] = field(default_factory=list)
    n_simulacoes: int = 0
    seed: int = 0
    limitacoes: str = _LIMITACOES_LOGISTICA


@dataclass
class ResultadoCenarioAgregado:
    n_territorios: int
    unidade: str
    conservador: float
    mediano: float
    otimista: float
    votos_reais_atuais: float | None
    limitacoes: str = (
        "Cenarios (conservador=p5, mediano=p50, otimista=p95) calculados somando, DENTRO "
        "de cada simulacao, a previsao de todos os territorios incluidos - e so DEPOIS "
        "extraindo os percentis da soma. E a unica forma matematicamente valida de "
        "caracterizar a distribuicao de uma SOMA de territorios cujas previsoes sao "
        "correlacionadas (todos usam o MESMO sorteio de coeficientes em cada simulacao, "
        "por vir do mesmo modelo ajustado) - somar percentis calculados independentemente "
        "por territorio nao corresponde a nenhum percentil real da soma (pode subestimar "
        "OU superestimar a banda, dependendo da estrutura de correlacao; nao ha uma "
        "direcao de erro garantida a priori)."
    )


def _coeficientes_na_ordem(coeficientes: pd.DataFrame, variaveis: list[str]) -> pd.DataFrame:
    """Reordena/filtra o dataframe de coeficientes para a mesma ordem de
    `variaveis` (que e a ordem usada para montar a matriz X) - nunca confia
    na ordem de iteracao original do dataframe."""
    return coeficientes.set_index("variavel").loc[variaveis].reset_index()


def simular_regressao_linear(
    resultado: _rm.ResultadoRegressao,
    dados: pd.DataFrame,
    coluna_territorio: str,
    coluna_valor_observado: str = "pct_votos_validos_territorio",
    n_simulacoes: int = 2000,
    seed: int = 42,
) -> ResultadoSimulacaoLinear | None:
    """Simula `n_simulacoes` previsoes de `coluna_valor_observado` por
    territorio, sorteando os coeficientes reais de `resultado` de
    Normal(coeficiente, erro_padrao). Retorna None se as variaveis do
    modelo nao estiverem disponiveis em `dados` - mesmo padrao de
    degradacao graciosa do resto do SIET, nunca simula sobre dado
    ausente."""
    variaveis = resultado.variaveis_utilizadas
    colunas_necessarias = [coluna_territorio] + variaveis
    faltantes = [c for c in colunas_necessarias if c not in dados.columns]
    if faltantes:
        logger.warning("simular_regressao_linear: colunas ausentes em `dados`: %s", faltantes)
        return None

    dados_validos = dados.dropna(subset=variaveis).reset_index(drop=True)
    if dados_validos.empty:
        return None

    coefs = _coeficientes_na_ordem(resultado.coeficientes, variaveis)
    rng = np.random.default_rng(seed)
    sorteios = rng.normal(
        coefs["coeficiente"].to_numpy(), coefs["erro_padrao"].to_numpy(),
        size=(n_simulacoes, len(variaveis)),
    )
    x = dados_validos[variaveis].to_numpy(dtype=float)
    matriz = resultado.intercepto + sorteios @ x.T
    matriz = np.clip(matriz, 0.0, 100.0)

    territorios = pd.DataFrame({coluna_territorio: dados_validos[coluna_territorio]})
    territorios["valor_observado"] = (
        dados_validos[coluna_valor_observado] if coluna_valor_observado in dados_validos.columns else None
    )
    territorios["mediana_simulada"] = np.round(np.percentile(matriz, 50, axis=0), 2)
    territorios["p5"] = np.round(np.percentile(matriz, 5, axis=0), 2)
    territorios["p95"] = np.round(np.percentile(matriz, 95, axis=0), 2)

    return ResultadoSimulacaoLinear(
        territorios=territorios, matriz_simulacoes=matriz, variaveis_utilizadas=variaveis,
        n_simulacoes=n_simulacoes, seed=seed,
    )


def simular_regressao_logistica(
    resultado: _rm.ResultadoRegressaoLogistica,
    dados: pd.DataFrame,
    coluna_territorio: str,
    n_simulacoes: int = 2000,
    seed: int = 42,
) -> ResultadoSimulacaoLogistica | None:
    """Mesma logica de `simular_regressao_linear`, para a regressao
    logistica - a previsao simulada e uma PROBABILIDADE (0-1) de 'boa
    votacao', via sigmoide sobre o sorteio de coeficientes."""
    variaveis = resultado.variaveis_utilizadas
    if "erro_padrao" not in resultado.coeficientes.columns:
        logger.warning("simular_regressao_logistica: modelo sem erro_padrao nos coeficientes - versao desatualizada.")
        return None
    colunas_necessarias = [coluna_territorio] + variaveis
    faltantes = [c for c in colunas_necessarias if c not in dados.columns]
    if faltantes:
        logger.warning("simular_regressao_logistica: colunas ausentes em `dados`: %s", faltantes)
        return None

    dados_validos = dados.dropna(subset=variaveis).reset_index(drop=True)
    if dados_validos.empty:
        return None

    coefs = _coeficientes_na_ordem(resultado.coeficientes, variaveis)
    rng = np.random.default_rng(seed)
    sorteios = rng.normal(
        coefs["coeficiente"].to_numpy(), coefs["erro_padrao"].to_numpy(),
        size=(n_simulacoes, len(variaveis)),
    )
    x = dados_validos[variaveis].to_numpy(dtype=float)
    logit = resultado.intercepto + sorteios @ x.T
    matriz = 1.0 / (1.0 + np.exp(-np.clip(logit, -700, 700)))  # clip evita overflow de exp, mesmo espirito do fix em regression_models.py

    territorios = pd.DataFrame({coluna_territorio: dados_validos[coluna_territorio]})
    territorios["mediana_simulada"] = np.round(np.percentile(matriz, 50, axis=0), 4)
    territorios["p5"] = np.round(np.percentile(matriz, 5, axis=0), 4)
    territorios["p95"] = np.round(np.percentile(matriz, 95, axis=0), 4)

    return ResultadoSimulacaoLogistica(
        territorios=territorios, matriz_simulacoes=matriz, variaveis_utilizadas=variaveis,
        n_simulacoes=n_simulacoes, seed=seed,
    )


def cenario_agregado_votos(
    simulacao: ResultadoSimulacaoLinear,
    dados: pd.DataFrame,
    coluna_territorio: str,
    coluna_votos_validos_territorio: str,
    coluna_votos_candidato: str = "votos_candidato",
) -> ResultadoCenarioAgregado | None:
    """Converte a simulacao de PERCENTUAL (`simular_regressao_linear`) em
    CENARIOS DE VOTOS somando, territorio a territorio, dentro de cada
    simulacao (preserva a correlacao real entre territorios - ver
    docstring do modulo) - nunca soma percentis calculados
    independentemente por territorio."""
    base = dados[[coluna_territorio, coluna_votos_validos_territorio]].drop_duplicates(coluna_territorio)
    alinhado = simulacao.territorios[[coluna_territorio]].merge(base, on=coluna_territorio, how="left")
    if alinhado[coluna_votos_validos_territorio].isna().any():
        logger.warning("cenario_agregado_votos: territorios sem votos_validos_territorio correspondente - excluidos.")
    votos_validos = alinhado[coluna_votos_validos_territorio].to_numpy(dtype=float)
    validos = ~np.isnan(votos_validos)
    if not validos.any():
        return None

    matriz_votos = (simulacao.matriz_simulacoes[:, validos] / 100.0) * votos_validos[validos]
    soma_por_simulacao = matriz_votos.sum(axis=1)

    votos_reais = None
    if coluna_votos_candidato in dados.columns:
        base_votos = dados[[coluna_territorio, coluna_votos_candidato]].drop_duplicates(coluna_territorio)
        alinhado_votos = simulacao.territorios[[coluna_territorio]].merge(base_votos, on=coluna_territorio, how="left")
        votos_reais = float(alinhado_votos[coluna_votos_candidato].fillna(0).sum())

    return ResultadoCenarioAgregado(
        n_territorios=int(validos.sum()),
        unidade="votos",
        conservador=round(float(np.percentile(soma_por_simulacao, 5)), 0),
        mediano=round(float(np.percentile(soma_por_simulacao, 50)), 0),
        otimista=round(float(np.percentile(soma_por_simulacao, 95)), 0),
        votos_reais_atuais=votos_reais,
    )
