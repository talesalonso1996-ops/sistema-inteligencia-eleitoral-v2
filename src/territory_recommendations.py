"""Territorios e Pautas Sugeridas (Modo 1, melhorias pos-Etapa 8) - para
uma candidatura HIPOTETICA (ainda sem voto real), responde duas perguntas
com o maximo de dado real possivel, sem nunca fabricar ou misturar sinais
de natureza diferente num unico numero:

1. "Onde fazer campanha?" - 3 sinais REAIS, sempre mostrados separados
   (nunca combinados num escore falso):
   a. Perfil demografico REAL por distrito/bairro do municipio-base
      (Censo IBGE 2022, mesma fonte ja usada em todo o SIET) cruzado com
      as pautas prioritarias que o candidato declarou - distritos com
      maior carencia/relevancia real no tema declarado = oportunidade
      real observavel (mesmo principio ja usado na Piramide de Maslow).
   b. Territorios reais onde o padrinho politico declarado (se houver e
      encontrado no TSE) teve seu melhor desempenho -
      src/godfather_analysis.py, "base eleitoral emprestada".
   c. Bairros que o proprio candidato declarou conhecer/ter presenca
      (BaseEleitoral.bairros_presenca_declarados) - dado declarado, nunca
      inferido.
2. "Quais pautas priorizar?" - reaproveita o indice ja calculado no Modo 3
   (aderencia_candidato_pauta/indice_geral_prioridade, quando o candidato
   tambem respondeu o questionario de pauta) OU, quando so as pautas
   prioritarias foram marcadas (sem passar pelo Modo 3), mostra so a
   carencia territorial real (item 1a) como justificativa.

NUNCA fabrica: pautas sem variavel real do Censo mapeada em
config/policy_territory_proxies.yaml ficam marcadas 'sem proxy
territorial' em vez de receber um numero inventado."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .geographic_analysis import carregar_malha
from .rivals.hypothetical_rivals import resolver_municipio
from .demographic_analysis import perfil_demografico_por_setor
from .utils import get_logger, load_yaml

logger = get_logger(__name__)

_ANO_REFERENCIA_MUNICIPIO = 2024
_NIVEL_TERRITORIO = "NM_DIST"  # distrito - sempre presente na malha de setores, mesmo fallback ja usado no resto do app quando bairro nao tem poligono proprio


def proxies_config() -> dict:
    return load_yaml("config/policy_territory_proxies.yaml")


@dataclass
class PerfilTerritorioFino:
    territorio: str
    populacao_total: float
    variaveis: dict[str, float | None] = field(default_factory=dict)


@dataclass
class ResultadoPerfilPorTerritorio:
    uf: str
    municipio: str
    nivel_territorial: str  # sempre "distrito" nesta versao
    territorios: pd.DataFrame  # 1 linha por territorio, colunas = variaveis do Censo + populacao_total
    avisos: list[str] = field(default_factory=list)


def perfil_por_territorio_municipio(uf: str, municipio_base: str) -> ResultadoPerfilPorTerritorio:
    """Perfil demografico REAL (Censo IBGE 2022), um valor por
    distrito/territorio fino do municipio-base - nao um unico valor
    agregado do municipio inteiro (essa versao mais grossa ja existe em
    src/integration/candidate_territory_policy_matrix.py, usada pelo Modo
    4). Media ponderada por POPULACAO real do setor (nao por voto - nao
    existe voto real para uma candidatura hipotetica)."""
    codigo_municipio_tse, municipio_real, aviso_municipio = resolver_municipio(
        _ANO_REFERENCIA_MUNICIPIO, uf, municipio_base,
    )
    if aviso_municipio:
        return ResultadoPerfilPorTerritorio(
            uf=uf, municipio=municipio_base, nivel_territorial="distrito",
            territorios=pd.DataFrame(), avisos=[aviso_municipio],
        )

    setores_gdf = carregar_malha("setores", municipio_real, uf)
    if setores_gdf is None or setores_gdf.empty or _NIVEL_TERRITORIO not in setores_gdf.columns:
        return ResultadoPerfilPorTerritorio(
            uf=uf, municipio=municipio_real, nivel_territorial="distrito",
            territorios=pd.DataFrame(),
            avisos=[f"Malha de setores censitarios indisponivel para {municipio_real}/{uf}."],
        )

    setores_ids = {str(s) for s in setores_gdf["CD_SETOR"].dropna().unique()}
    perfil_setores = perfil_demografico_por_setor(setores_ids)
    if perfil_setores.empty:
        return ResultadoPerfilPorTerritorio(
            uf=uf, municipio=municipio_real, nivel_territorial="distrito",
            territorios=pd.DataFrame(),
            avisos=[f"Perfil censitario indisponivel para os setores de {municipio_real}/{uf}."],
        )

    base = setores_gdf[["CD_SETOR", _NIVEL_TERRITORIO]].astype({"CD_SETOR": str}).merge(
        perfil_setores, on="CD_SETOR", how="inner",
    )
    if base.empty:
        return ResultadoPerfilPorTerritorio(
            uf=uf, municipio=municipio_real, nivel_territorial="distrito",
            territorios=pd.DataFrame(),
            avisos=[f"Nenhum setor censitario com perfil demografico casou com a malha de {municipio_real}/{uf}."],
        )

    variaveis = [c for c in perfil_setores.columns if c not in ("CD_SETOR", "populacao_total")]
    linhas = []
    for territorio, grupo in base.groupby(_NIVEL_TERRITORIO):
        pop_total = float(grupo["populacao_total"].fillna(0).sum())
        linha = {"territorio": territorio, "populacao_total": pop_total}
        for var in variaveis:
            validos = grupo[grupo[var].notna() & grupo["populacao_total"].notna() & (grupo["populacao_total"] > 0)]
            if validos.empty:
                linha[var] = None
            else:
                linha[var] = round(
                    float((validos[var] * validos["populacao_total"]).sum() / validos["populacao_total"].sum()), 2,
                )
        linhas.append(linha)

    territorios_df = pd.DataFrame(linhas).sort_values("populacao_total", ascending=False).reset_index(drop=True)
    return ResultadoPerfilPorTerritorio(
        uf=uf, municipio=municipio_real, nivel_territorial="distrito", territorios=territorios_df,
    )


@dataclass
class RankingPautaTerritorio:
    pauta_id: str
    tem_proxy_territorial: bool
    ranking: pd.DataFrame | None = None  # colunas: territorio, score_oportunidade (0-100), + variaveis usadas
    aviso: str | None = None


def ranking_territorios_por_pauta(perfil: ResultadoPerfilPorTerritorio, pauta_id: str) -> RankingPautaTerritorio:
    """Para uma pauta com proxy real declarado em
    config/policy_territory_proxies.yaml, ordena os territorios do
    municipio-base pelo score de oportunidade/relevancia real (normalizado
    min-max DENTRO do proprio municipio - nao existe teto de referencia
    absoluto defensavel para essas variaveis, diferente das perguntas
    numericas do questionario). Pautas sem proxy retornam
    tem_proxy_territorial=False, nunca um numero inventado."""
    cfg = proxies_config().get("pautas", {})
    if pauta_id not in cfg:
        return RankingPautaTerritorio(
            pauta_id=pauta_id, tem_proxy_territorial=False,
            aviso="Esta pauta nao tem variavel real do Censo IBGE mapeada como proxy territorial "
                  "(catalogo atual cobre saneamento, infraestrutura, educacao, emprego/renda, "
                  "combate a pobreza, assistencia social, mulheres, idosos, juventude, moradia e "
                  "habitacao) - nao e possivel sugerir territorios para ela sem inventar dado.",
        )
    if perfil.territorios.empty:
        return RankingPautaTerritorio(
            pauta_id=pauta_id, tem_proxy_territorial=True,
            aviso="Perfil territorial do municipio-base indisponivel (ver avisos do perfil).",
        )

    variaveis_cfg = cfg[pauta_id]["variaveis"]
    df = perfil.territorios.copy()
    scores_por_variavel = []
    variaveis_usadas = []
    for item in variaveis_cfg:
        nome = item["nome"]
        direcao = item["direcao"]
        if nome not in df.columns or df[nome].notna().sum() < 2:
            continue
        serie = df[nome]
        minimo, maximo = serie.min(), serie.max()
        if maximo == minimo:
            continue
        if direcao == "menor_pior":
            normalizado = 100 * (maximo - serie) / (maximo - minimo)
        else:  # maior_relevante
            normalizado = 100 * (serie - minimo) / (maximo - minimo)
        scores_por_variavel.append(normalizado)
        variaveis_usadas.append(nome)

    if not scores_por_variavel:
        return RankingPautaTerritorio(
            pauta_id=pauta_id, tem_proxy_territorial=True,
            aviso="Nenhuma das variaveis-proxy desta pauta tinha dado real suficiente neste municipio.",
        )

    df["score_oportunidade"] = pd.concat(scores_por_variavel, axis=1).mean(axis=1).round(1)
    colunas_saida = ["territorio", "score_oportunidade", "populacao_total"] + variaveis_usadas
    ranking = df[colunas_saida].sort_values("score_oportunidade", ascending=False).reset_index(drop=True)
    return RankingPautaTerritorio(pauta_id=pauta_id, tem_proxy_territorial=True, ranking=ranking)


@dataclass
class ResultadoTerritoriosSugeridos:
    perfil: ResultadoPerfilPorTerritorio
    rankings_por_pauta: list[RankingPautaTerritorio] = field(default_factory=list)
    bairros_declarados: list[str] = field(default_factory=list)
    limitacoes: list[str] = field(default_factory=list)


_LIMITACAO_GERAL = (
    "Nenhum dos 3 sinais abaixo e combinado num unico numero: perfil territorial real do "
    "Censo, territorios reais do padrinho politico (quando houver) e bairros que o proprio "
    "candidato declarou conhecer sao mostrados separados, cada um com sua propria fonte - "
    "misturar autoavaliacao/dado declarado com dado censitario real num unico escore "
    "fabricaria uma equivalencia que os dados nao sustentam."
)


def montar_territorios_sugeridos(
    uf: str, municipio_base: str, pautas_prioritarias: list[str], bairros_declarados: list[str],
) -> ResultadoTerritoriosSugeridos:
    """Ponto de entrada principal - perfil territorial real do
    municipio-base + ranking por cada pauta prioritaria declarada (quando
    tiver proxy real disponivel)."""
    perfil = perfil_por_territorio_municipio(uf, municipio_base)
    rankings = [ranking_territorios_por_pauta(perfil, pauta_id) for pauta_id in pautas_prioritarias]
    return ResultadoTerritoriosSugeridos(
        perfil=perfil, rankings_por_pauta=rankings, bairros_declarados=list(bairros_declarados),
        limitacoes=[_LIMITACAO_GERAL],
    )
