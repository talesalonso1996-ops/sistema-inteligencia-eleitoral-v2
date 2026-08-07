"""Os 4 indices de desempenho eleitoral REAL (IDP/IVE/IEC/QEC) - config em
config/indicators.yaml: indice_idp/indice_ive/indice_iec/indice_qec.

Diferente de candidate_indices.py (20 indices de AUTOAVALIACAO de uma nova
candidatura, via questionario), estes 4 sao calculados a partir do
resultado eleitoral REAL de uma candidatura JA DISPUTADA - reaproveitam
funcoes ja existentes e testadas (electoral_metrics.resultado_geral,
state_scope_indicators.calcular_presenca_eleitoral/
calcular_concentracao_territorial, competitor_analysis.zonas_de_disputa),
nunca recalculando a logica de base.

Funcionam identicamente para o candidato-alvo e para qualquer rival da
MESMA disputa: `votos_disputa`/`registro_disputa` sao os mesmos para todos
os concorrentes de uma disputa (ja carregados uma unica vez pelo chamador)
- so `votos_candidatura` muda (filtra vd por outro NR_VOTAVEL). Isso e o
que viabiliza um radar comparando candidato x rivais sem nenhum download/
calculo adicional caro (sem geocodificacao, clustering ou regressao)."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..candidate_finder import Candidatura
from ..competitor_analysis import zonas_de_disputa
from ..electoral_metrics import ResultadoGeral, desempenho_territorial, resultado_geral
from ..state_scope_indicators import (
    ConcentracaoTerritorial,
    PresencaEleitoral,
    calcular_concentracao_territorial,
    calcular_presenca_eleitoral,
)
from ..utils import get_logger, indicators_config

logger = get_logger(__name__)


@dataclass
class ResultadoIndice:
    nome: str
    nome_completo: str
    valor: float
    cobertura_pct: float
    classificacao: str
    nota_alta_e_pior: bool = False


@dataclass
class IndicesDesempenhoReal:
    idp: ResultadoIndice
    ive: ResultadoIndice
    iec: ResultadoIndice
    qec: ResultadoIndice

    def valores(self) -> dict[str, float]:
        return {"IDP": self.idp.valor, "IVE": self.ive.valor, "IEC": self.iec.valor, "QEC": self.qec.valor}


def _normalizar(valor: float, minimo: float, maximo: float) -> float:
    if maximo == minimo:
        return 50.0
    return max(0.0, min(100.0, 100 * (valor - minimo) / (maximo - minimo)))


def _classificar(valor: float, limites: dict[str, int]) -> str:
    ordenado = sorted(limites.items(), key=lambda kv: kv[1], reverse=True)
    for nome, minimo in ordenado:
        if valor >= minimo:
            return nome
    return ordenado[-1][0]


def _combinar(componentes: dict[str, float | None], pesos: dict[str, float]) -> tuple[float, float]:
    """Soma ponderada com redistribuicao de peso entre os componentes
    disponiveis (mesmo padrao usado em todo o SIET: nunca preenche um
    componente ausente com um valor inventado)."""
    disponiveis = {k: v for k, v in componentes.items() if v is not None}
    pesos_disponiveis = {k: pesos[k] for k in disponiveis}
    soma_pesos_total = sum(pesos.values())
    soma_pesos_disp = sum(pesos_disponiveis.values())
    cobertura_pct = round(100.0 * soma_pesos_disp / soma_pesos_total, 1) if soma_pesos_total else 0.0
    if soma_pesos_disp == 0:
        return 0.0, cobertura_pct
    valor = sum(disponiveis[k] * (peso / soma_pesos_disp) for k, peso in pesos_disponiveis.items())
    return round(max(0.0, min(100.0, valor)), 1), cobertura_pct


def _calcular_idp(candidatura: Candidatura, rg: ResultadoGeral, cfg: dict) -> ResultadoIndice:
    pesos = cfg["indice_idp"]["pesos"]

    colocacao_relativa = None
    if rg.colocacao_geral and rg.total_concorrentes:
        colocacao_relativa = 100 * (rg.total_concorrentes - rg.colocacao_geral + 1) / rg.total_concorrentes

    proximidade_eleicao = None
    if candidatura.resultado_final.upper().startswith("ELEITO"):
        proximidade_eleicao = 100.0
    elif rg.votos_ultimo_eleito:
        proximidade_eleicao = 100 * min(1.0, rg.total_votos / rg.votos_ultimo_eleito)

    forca_no_partido = rg.pct_candidato_sobre_partido if rg.votos_partido_total else None

    componentes = {
        "colocacao_relativa": colocacao_relativa,
        "proximidade_eleicao": proximidade_eleicao,
        "forca_no_partido": forca_no_partido,
    }
    valor, cobertura = _combinar(componentes, pesos)
    return ResultadoIndice(
        "IDP", cfg["indice_idp"]["nome_completo"], valor, cobertura,
        _classificar(valor, cfg["indice_idp"]["limites_classificacao"]),
    )


def _calcular_ive(
    candidatura: Candidatura, rg: ResultadoGeral, concentracao: ConcentracaoTerritorial,
    zonas: pd.DataFrame,
    cfg: dict,
) -> ResultadoIndice:
    pesos = cfg["indice_ive"]["pesos"]

    componente_hhi = _normalizar(concentracao.hhi, 0, 1)

    distancias = [d for d in (rg.distancia_concorrente_acima, rg.distancia_concorrente_abaixo) if d is not None]
    proximidade_rival = None
    if distancias and rg.total_votos:
        distancia_relativa = min(abs(d) for d in distancias) / rg.total_votos
        proximidade_rival = 100 * (1 - min(1.0, distancia_relativa))

    territorios_expostos = None
    com_voto = zonas[zonas["situacao"] != "sem_votos_no_territorio"]
    if not com_voto.empty:
        expostos = com_voto["situacao"].isin(["disputa_acirrada", "desvantagem"]).sum()
        territorios_expostos = 100 * expostos / len(com_voto)

    componentes = {
        "concentracao_hhi": componente_hhi,
        "proximidade_rival_direto": proximidade_rival,
        "territorios_expostos": territorios_expostos,
    }
    valor, cobertura = _combinar(componentes, pesos)
    return ResultadoIndice(
        "IVE", cfg["indice_ive"]["nome_completo"], valor, cobertura,
        _classificar(valor, cfg["indice_ive"]["limites_classificacao"]), nota_alta_e_pior=True,
    )


def _calcular_iec(presenca: PresencaEleitoral, cfg: dict) -> ResultadoIndice:
    pesos = cfg["indice_iec"]["pesos"]

    cobertura_universo = presenca.pct_cobertura if presenca.n_municipios_universo else None
    consistencia = None
    if presenca.n_municipios_com_votos:
        consistencia = 100 * presenca.n_municipios_acima_media / presenca.n_municipios_com_votos

    componentes = {"cobertura_do_universo": cobertura_universo, "consistencia_acima_da_propria_media": consistencia}
    valor, cob = _combinar(componentes, pesos)
    return ResultadoIndice(
        "IEC", cfg["indice_iec"]["nome_completo"], valor, cob,
        _classificar(valor, cfg["indice_iec"]["limites_classificacao"]),
    )


def _calcular_qec(
    territorial: pd.DataFrame, zonas: pd.DataFrame, presenca: PresencaEleitoral,
    nivel: str, cfg: dict,
) -> ResultadoIndice:
    pesos = cfg["indice_qec"]["pesos"]

    dominados = zonas[zonas["situacao"].isin(["dominio", "dominio_absoluto"])]
    margem_media = None
    alcance = None
    if not dominados.empty:
        votos_por_territorio = territorial.set_index(nivel)["votos_candidato"]
        pesos_voto = dominados[nivel].map(votos_por_territorio).fillna(0)
        if pesos_voto.sum() > 0:
            margem_media = float((dominados["margem_pct"] * pesos_voto).sum() / pesos_voto.sum())
            margem_media = max(0.0, min(100.0, margem_media))
        if presenca.n_municipios_universo:
            alcance = 100 * len(dominados) / presenca.n_municipios_universo

    componentes = {"margem_media_nos_dominios": margem_media, "alcance_do_dominio": alcance}
    valor, cob = _combinar(componentes, pesos)
    return ResultadoIndice(
        "QEC", cfg["indice_qec"]["nome_completo"], valor, cob,
        _classificar(valor, cfg["indice_qec"]["limites_classificacao"]),
    )


def calcular_indices_desempenho_real(
    candidatura: Candidatura,
    votos_candidatura: pd.DataFrame,
    votos_disputa: pd.DataFrame,
    registro_disputa: pd.DataFrame,
    nivel: str,
) -> IndicesDesempenhoReal:
    """Ponto de entrada principal: calcula IDP/IVE/IEC/QEC para UMA
    candidatura (alvo ou rival) a partir do resultado eleitoral real dela
    na disputa. `nivel` e a coluna territorial (CD_MUNICIPIO para cargos
    estaduais, NR_ZONA para municipais - a mesma granularidade ja usada
    pelo resto da secao que chama esta funcao)."""
    cfg = indicators_config()
    rg = resultado_geral(candidatura, votos_disputa, registro_disputa)
    territorial = desempenho_territorial(candidatura, votos_candidatura, votos_disputa, registro_disputa, nivel)
    # calcular_presenca_eleitoral espera uma coluna de "nome" SEPARADA da
    # coluna de codigo territorial (NM_MUNICIPIO != CD_MUNICIPIO), presente
    # tanto no dataframe territorial quanto em votos_disputa - niveis sem
    # nome proprio (NR_ZONA, NR_SECAO) nao tem essa segunda coluna;
    # sintetiza uma (mesmo valor, coluna com outro nome) nos DOIS
    # dataframes, so para nao colidir 2 colunas identicas (quebraria o
    # `set(universo[coluna_municipio])` interno daquela funcao).
    territorial_rotulado = territorial.assign(_rotulo_territorio=territorial[nivel].astype(str))
    votos_disputa_rotulado = votos_disputa.assign(_rotulo_territorio=votos_disputa[nivel].astype(str))
    presenca = calcular_presenca_eleitoral(
        territorial_rotulado, votos_disputa_rotulado, coluna_municipio=nivel, coluna_municipio_nome="_rotulo_territorio",
    )
    concentracao = calcular_concentracao_territorial(territorial)
    zonas = zonas_de_disputa(territorial, votos_disputa, registro_disputa, candidatura, nivel)

    return IndicesDesempenhoReal(
        idp=_calcular_idp(candidatura, rg, cfg),
        ive=_calcular_ive(candidatura, rg, concentracao, zonas, cfg),
        iec=_calcular_iec(presenca, cfg),
        qec=_calcular_qec(territorial, zonas, presenca, nivel, cfg),
    )
