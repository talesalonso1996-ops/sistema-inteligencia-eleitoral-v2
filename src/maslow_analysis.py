"""Reinterpretacao, sob a lente da Piramide de Maslow, dos coeficientes/odds
ratios JA CALCULADOS por regression_models.py (secao "Estatistica Avancada").

Maslow e uma teoria de motivacao INDIVIDUAL - nao e mensuravel diretamente a
partir de dados agregados por territorio. Este modulo NAO computa nenhuma
estatistica nova: ele apenas reclassifica, conforme
config/indicators.yaml:piramide_maslow, as mesmas variaveis demograficas que
ja alimentam a regressao/clusterizacao, e reaproveita o estilo de
interpretacao ja usado em regression_models.py. Niveis sem proxy defensavel
na base de dados (Social/Pertencimento, Autorrealizacao) sao explicitamente
sinalizados como lacuna - nunca preenchidos com uma variavel fraca so para
completar a piramide.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from .utils import indicators_config

_COLUNAS_TIERS_MAPEADOS = [
    "tier", "label", "variavel", "tipo_efeito", "valor_efeito", "magnitude",
    "significativo", "p_valor", "rationale", "interpretacao", "status",
]


@dataclass
class ResultadoMaslow:
    fonte_efeito: str  # "regressao_logistica" | "regressao_linear" | "correlacao" | "indisponivel"
    tiers_mapeados: pd.DataFrame
    tiers_sem_proxy: pd.DataFrame
    variaveis_pendentes: pd.DataFrame
    variaveis_sem_correspondencia: pd.DataFrame
    narrativa: list[str]
    disclaimer: str
    ordem_tiers: list[str]


def _tabela_vazia() -> pd.DataFrame:
    return pd.DataFrame(columns=_COLUNAS_TIERS_MAPEADOS)


def _magnitude(valor: float, tipo_efeito: str) -> float:
    """Tamanho do efeito, comparavel entre tipos. Para odds ratio usa
    log-odds (simetrico em torno de OR=1 = "sem efeito"; abs(valor-1) trataria
    OR=0.5 como efeito mais fraco que OR=2, o que e estatisticamente errado)."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return 0.0
    if tipo_efeito == "odds_ratio":
        return abs(math.log(valor)) if valor > 0 else 0.0
    return abs(valor)


def _frase_efeito(variavel: str, valor: float, tipo_efeito: str, significativo) -> str:
    """Reaproveita o estilo de interpretacao ja usado em
    ResultadoRegressaoLogistica.interpretacoes (regression_models.py), com
    equivalentes para coeficiente linear e correlacao - nunca inventa um
    novo estilo de texto."""
    aviso_sig = " (nao significativo a p<0.05 - interpretar com cautela)" if significativo is False else ""

    if tipo_efeito == "odds_ratio":
        direcao = "aumenta" if valor > 1 else "reduz"
        return (
            f"Cada aumento de 1 ponto percentual em '{variavel}' multiplica as chances de "
            f"boa votacao por {valor:.2f}x ({direcao} a chance){aviso_sig}."
        )
    if tipo_efeito == "coeficiente_linear":
        direcao = "aumenta" if valor > 0 else "reduz"
        return (
            f"Cada aumento de 1 ponto percentual em '{variavel}' esta associado a uma "
            f"variacao de {valor:+.3f} pontos percentuais no percentual de votos do candidato "
            f"no territorio ({direcao}){aviso_sig}."
        )
    polaridade = "positiva" if valor > 0 else "negativa"
    return (
        f"'{variavel}' tem correlacao {polaridade} de {valor:.2f} com o desempenho eleitoral "
        f"do candidato no territorio{aviso_sig}."
    )


def _mapa_variavel_para_tiers(cfg: dict) -> dict[str, list[tuple[str, str, str]]]:
    """nome_variavel -> lista de (tier_key, label, rationale). Uma variavel
    pode aparecer em mais de um tier adjacente (ex.: renda em Fisiologico e
    Seguranca) - isso e intencional, nao um bug."""
    mapa: dict[str, list[tuple[str, str, str]]] = {}
    for tier_key, tier in cfg["tiers"].items():
        if tier["status"] != "mapeado":
            continue
        for var in tier.get("variaveis", []):
            mapa.setdefault(var["nome"], []).append(
                (tier_key, tier["label"], var["rationale"].strip())
            )
    return mapa


def _status_variaveis_nao_mapeadas(cfg: dict) -> dict[str, tuple[str, str]]:
    """nome_variavel -> (status, motivo) para variaveis com mapeamento
    pendente de decisao ou sem correspondencia teorica."""
    out: dict[str, tuple[str, str]] = {}
    for item in cfg.get("variaveis_pendentes_decisao", []):
        out[item["nome"]] = ("pendente", item.get("rationale", "").strip())
    for item in cfg.get("variaveis_sem_correspondencia_teorica", []):
        out[item["nome"]] = ("sem_correspondencia", item["motivo"].strip())
    return out


def mapear_coeficientes_para_tiers(
    coeficientes: pd.DataFrame, coluna_valor: str, tipo_efeito: str
) -> pd.DataFrame:
    """Para cada variavel em `coeficientes` (precisa ter colunas `variavel`
    e `coluna_valor`, e opcionalmente `significativo`/`p_valor`), produz 1+
    linhas com o(s) tier(s) onde ela esta mapeada em
    config/indicators.yaml:piramide_maslow. Variaveis sem nenhum tier
    mapeado NUNCA sao descartadas silenciosamente - aparecem com tier=None
    e status "pendente"/"sem_correspondencia"/"nao_classificado_no_config"."""
    cfg = indicators_config()["piramide_maslow"]
    mapa = _mapa_variavel_para_tiers(cfg)
    status_extra = _status_variaveis_nao_mapeadas(cfg)

    linhas = []
    for row in coeficientes.itertuples(index=False):
        variavel = row.variavel
        valor = getattr(row, coluna_valor)
        significativo = getattr(row, "significativo", None)
        p_valor = getattr(row, "p_valor", None)
        magnitude = _magnitude(valor, tipo_efeito)
        interpretacao = _frase_efeito(variavel, valor, tipo_efeito, significativo)

        if variavel in mapa:
            for tier_key, label, rationale in mapa[variavel]:
                linhas.append({
                    "tier": tier_key, "label": label, "variavel": variavel,
                    "tipo_efeito": tipo_efeito, "valor_efeito": valor, "magnitude": magnitude,
                    "significativo": significativo, "p_valor": p_valor,
                    "rationale": rationale, "interpretacao": interpretacao, "status": "mapeado",
                })
        else:
            status, motivo = status_extra.get(
                variavel, ("nao_classificado_no_config", "Variavel nao encontrada na configuracao da piramide de Maslow.")
            )
            linhas.append({
                "tier": None, "label": None, "variavel": variavel,
                "tipo_efeito": tipo_efeito, "valor_efeito": valor, "magnitude": magnitude,
                "significativo": significativo, "p_valor": p_valor,
                "rationale": motivo, "interpretacao": interpretacao, "status": status,
            })

    return pd.DataFrame(linhas, columns=_COLUNAS_TIERS_MAPEADOS) if linhas else _tabela_vazia()


def gerar_narrativa_maslow(tiers_mapeados: pd.DataFrame, ordem_tiers: list[str]) -> list[str]:
    """Uma frase por nivel que tem >=1 variavel mapeada, na ordem
    hierarquica (base->topo) - mesmo padrao de
    clustering.gerar_narrativa_clusters (um resumo em linguagem natural por
    grupo, nao so uma tabela de numeros)."""
    if tiers_mapeados.empty:
        return []
    mapeadas = tiers_mapeados[tiers_mapeados["status"] == "mapeado"]
    if mapeadas.empty:
        return []

    frases = []
    for tier_key in ordem_tiers:
        subset = mapeadas[mapeadas["tier"] == tier_key]
        if subset.empty:
            continue
        label = subset["label"].iloc[0]
        texto = "; ".join(subset["interpretacao"].tolist())
        frases.append(f"[Nivel {label}] {texto}")
    return frases


def _tabela_tiers_sem_proxy(cfg: dict) -> pd.DataFrame:
    linhas = [
        {"tier": k, "label": v["label"], "motivo": v.get("motivo_sem_proxy", "").strip()}
        for k, v in cfg["tiers"].items() if v["status"] == "sem_proxy"
    ]
    return pd.DataFrame(linhas, columns=["tier", "label", "motivo"])


def _tabela_pendentes(cfg: dict) -> pd.DataFrame:
    linhas = [
        {"nome": v["nome"], "tier_sugerido": v.get("tier_sugerido"), "rationale": v.get("rationale", "").strip()}
        for v in cfg.get("variaveis_pendentes_decisao", [])
    ]
    return pd.DataFrame(linhas, columns=["nome", "tier_sugerido", "rationale"])


def _tabela_sem_correspondencia(cfg: dict) -> pd.DataFrame:
    linhas = [
        {"nome": v["nome"], "motivo": v["motivo"].strip()}
        for v in cfg.get("variaveis_sem_correspondencia_teorica", [])
    ]
    return pd.DataFrame(linhas, columns=["nome", "motivo"])


def gerar_analise_maslow(
    modelo_logistico=None,
    modelo_linear=None,
    correlacoes: pd.DataFrame | None = None,
) -> ResultadoMaslow:
    """Ponto de entrada principal. Prioridade: regressao logistica (odds
    ratio) -> regressao linear -> correlacao simples -> indisponivel -
    coerente com o pedido de aferir "principalmente em odds ratio".

    NUNCA retorna None: "nenhum modelo estatistico disponivel" e um estado
    normal e exibivel (fonte_efeito="indisponivel" + narrativa explicando),
    nao um erro - mesmo espirito de identificar_bairros_potencial em
    potential_analysis.py, que tambem nunca retorna None."""
    cfg = indicators_config()["piramide_maslow"]

    if modelo_logistico is not None:
        tiers_df = mapear_coeficientes_para_tiers(modelo_logistico.coeficientes, "odds_ratio", "odds_ratio")
        fonte = "regressao_logistica"
    elif modelo_linear is not None:
        tiers_df = mapear_coeficientes_para_tiers(modelo_linear.coeficientes, "coeficiente", "coeficiente_linear")
        fonte = "regressao_linear"
    elif correlacoes is not None and not correlacoes.empty:
        tiers_df = mapear_coeficientes_para_tiers(correlacoes, "correlacao", "correlacao")
        fonte = "correlacao"
    else:
        tiers_df, fonte = _tabela_vazia(), "indisponivel"

    if fonte == "indisponivel":
        narrativa = [
            "Nenhum modelo estatistico (regressao logistica, linear ou correlacao) disponivel "
            "para esta candidatura (amostra insuficiente). A abordagem de Maslow depende de um "
            "resultado estatistico real ja calculado - sem ele, nao ha numero para reinterpretar."
        ]
    else:
        narrativa = gerar_narrativa_maslow(tiers_df, cfg["ordem_tiers"])
        if not narrativa:
            narrativa = [
                "Nenhuma das variaveis mapeadas na piramide de Maslow esta presente no modelo "
                "estatistico calculado para esta candidatura."
            ]
        elif fonte != "regressao_logistica":
            lente = "a regressao linear" if fonte == "regressao_linear" else "a correlacao simples"
            narrativa.insert(
                0,
                f"Aviso: regressao logistica indisponivel nesta candidatura - usando {lente} "
                "como lente substituta (menos robusta que odds ratio para medir chance de boa votacao).",
            )

    return ResultadoMaslow(
        fonte_efeito=fonte,
        tiers_mapeados=tiers_df,
        tiers_sem_proxy=_tabela_tiers_sem_proxy(cfg),
        variaveis_pendentes=_tabela_pendentes(cfg),
        variaveis_sem_correspondencia=_tabela_sem_correspondencia(cfg),
        narrativa=narrativa,
        disclaimer=cfg["aviso_metodologico"].strip(),
        ordem_tiers=cfg["ordem_tiers"],
    )
