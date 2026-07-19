"""Analise de concorrentes (secao 7 do briefing).

Recebe os mesmos dataframes ja carregados via candidate_finder
(votos_da_disputa, registro_candidatos_disputa) e produz rankings,
comparacoes diretas e matrizes candidato x territorio.

Atencao ao "voto de legenda": no arquivo de votacao por secao, o voto de
legenda aparece como uma linha com NM_VOTAVEL = NOME DO PARTIDO e
NR_VOTAVEL = NUMERO DO PARTIDO (nao de um candidato). Se nao for excluido
antes de agrupar por NR_VOTAVEL, ele aparece como uma "candidatura fantasma"
de votacao alta. E valido para o total de votos validos e para o total do
partido, mas nao para o ranking individual de candidatos. A identificacao
usa o conjunto de numeros de partido do registro (consulta_cand), nao um
rotulo textual fixo (o texto observado e o proprio nome do partido).
"""
from __future__ import annotations

import pandas as pd
from scipy import stats

from .candidate_finder import Candidatura
from .data_validation import validar_amostra_minima
from .utils import DataIssue
from .vote_filtering import votos_legenda as _votos_legenda
from .vote_filtering import votos_nominais as _votos_nominais
from .vote_filtering import votos_validos as _votos_validos


def ranking_disputa(votos_disputa: pd.DataFrame, registro_disputa: pd.DataFrame) -> pd.DataFrame:
    """Ranking completo de todos os candidatos nominais da disputa (exclui
    voto de legenda), com partido, situacao e resultado final. O percentual
    e calculado sobre o total de votos validos (nominais + legenda)."""
    total_validos = int(_votos_validos(votos_disputa)["QT_VOTOS"].sum())
    nominais = _votos_nominais(votos_disputa, registro_disputa)

    ranking = (
        nominais.groupby("NR_VOTAVEL", as_index=False)["QT_VOTOS"]
        .sum()
        .rename(columns={"QT_VOTOS": "total_votos"})
        .merge(
            registro_disputa[
                ["numero", "nome_completo", "nome_urna", "partido_sigla", "partido_nome",
                 "situacao_candidatura", "resultado_final"]
            ],
            left_on="NR_VOTAVEL",
            right_on="numero",
            how="left",
        )
        .sort_values("total_votos", ascending=False)
        .reset_index(drop=True)
    )
    ranking["colocacao"] = ranking.index + 1
    ranking["pct_votos_validos"] = (
        100 * ranking["total_votos"] / total_validos
    ).round(2) if total_validos else 0.0
    ranking["eleito"] = ranking["resultado_final"].str.upper().str.startswith("ELEITO", na=False)
    return ranking.drop(columns=["numero"])


def votos_legenda_por_partido(
    votos_disputa: pd.DataFrame, registro_disputa: pd.DataFrame
) -> pd.DataFrame:
    """Total de votos de legenda (sem candidato) por partido - usado para
    compor o total real do partido junto com os votos nominais."""
    legenda = _votos_legenda(votos_disputa, registro_disputa)
    if legenda.empty:
        return pd.DataFrame(columns=["numero_partido", "votos_legenda"])
    partidos = registro_disputa[["numero_partido", "partido_sigla", "partido_nome"]].drop_duplicates()
    agregado = legenda.groupby("NR_VOTAVEL", as_index=False)["QT_VOTOS"].sum().rename(
        columns={"NR_VOTAVEL": "numero_partido", "QT_VOTOS": "votos_legenda"}
    )
    return agregado.merge(partidos, on="numero_partido", how="left")


def ranking_partidos(
    ranking: pd.DataFrame, votos_disputa: pd.DataFrame, registro_disputa: pd.DataFrame
) -> pd.DataFrame:
    """Agrega o desempenho por partido: votos nominais + votos de legenda,
    numero de candidatos, numero de eleitos - contextualiza a forca da
    legenda do candidato."""
    nominal_partido = ranking.groupby(["partido_sigla", "partido_nome"], as_index=False).agg(
        votos_nominais=("total_votos", "sum"),
        n_candidatos=("NR_VOTAVEL", "count"),
        n_eleitos=("eleito", "sum"),
    )
    legenda = votos_legenda_por_partido(votos_disputa, registro_disputa)
    legenda_agg = legenda.groupby(["partido_sigla", "partido_nome"], as_index=False)["votos_legenda"].sum()

    agregado = nominal_partido.merge(legenda_agg, on=["partido_sigla", "partido_nome"], how="outer")
    agregado[["votos_nominais", "votos_legenda", "n_candidatos", "n_eleitos"]] = agregado[
        ["votos_nominais", "votos_legenda", "n_candidatos", "n_eleitos"]
    ].fillna(0)
    agregado["votos_totais"] = agregado["votos_nominais"] + agregado["votos_legenda"]

    total_geral = agregado["votos_totais"].sum()
    agregado["pct_votos_validos"] = (
        100 * agregado["votos_totais"] / total_geral
    ).round(2) if total_geral else 0.0
    agregado["colocacao_partido"] = agregado["votos_totais"].rank(ascending=False, method="min").astype(int)
    return agregado.sort_values("votos_totais", ascending=False).reset_index(drop=True)


def concorrentes_diretos(
    candidatura: Candidatura, ranking: pd.DataFrame, n: int = 5
) -> pd.DataFrame:
    """Retorna os N concorrentes com votacao mais proxima do candidato
    (acima e abaixo na classificacao) - quem disputa a mesma faixa de voto."""
    linha = ranking[ranking["NR_VOTAVEL"] == candidatura.numero]
    if linha.empty:
        return ranking.iloc[0:0]
    colocacao = int(linha["colocacao"].iloc[0])
    faixa = ranking[
        (ranking["colocacao"] >= colocacao - n) & (ranking["colocacao"] <= colocacao + n)
    ].copy()
    faixa["e_o_candidato"] = faixa["NR_VOTAVEL"] == candidatura.numero
    return faixa.sort_values("colocacao").reset_index(drop=True)


def matriz_candidato_territorio(
    candidatura: Candidatura,
    votos_disputa: pd.DataFrame,
    ranking: pd.DataFrame,
    nivel: str,
    top_n_concorrentes: int = 5,
) -> pd.DataFrame:
    """Tabela territorio x candidato (o proprio + top N concorrentes),
    com votos absolutos - base para heatmap comparativo (secao 7.3)."""
    top_concorrentes = ranking[ranking["colocacao"] <= top_n_concorrentes]["NR_VOTAVEL"].tolist()
    numeros_interesse = list(set(top_concorrentes + [candidatura.numero]))

    subset = votos_disputa[votos_disputa["NR_VOTAVEL"].isin(numeros_interesse)]
    pivot = subset.pivot_table(
        index=nivel, columns="NR_VOTAVEL", values="QT_VOTOS", aggfunc="sum", fill_value=0
    )
    nomes = ranking.set_index("NR_VOTAVEL")["nome_urna"].to_dict()
    pivot = pivot.rename(columns=nomes)
    return pivot.reset_index()


def zonas_de_disputa(
    territorial: pd.DataFrame,
    votos_disputa: pd.DataFrame,
    registro_disputa: pd.DataFrame,
    candidatura: Candidatura,
    nivel: str,
    margem_relativa: float = 0.15,
) -> pd.DataFrame:
    """Classifica cada territorio pela margem entre o candidato e o maior
    concorrente NAQUELE territorio: dominio (candidato bem a frente),
    disputa_acirrada (margem relativa <= margem_relativa), desvantagem
    (concorrente bem a frente) ou sem_votos_no_territorio."""
    nominais = _votos_nominais(votos_disputa, registro_disputa)
    por_territorio = nominais.groupby([nivel, "NR_VOTAVEL"], as_index=False)["QT_VOTOS"].sum()

    votos_candidato = por_territorio[por_territorio["NR_VOTAVEL"] == candidatura.numero].set_index(nivel)["QT_VOTOS"]
    maior_rival = (
        por_territorio[por_territorio["NR_VOTAVEL"] != candidatura.numero]
        .groupby(nivel)["QT_VOTOS"]
        .max()
    )

    territorios = set(por_territorio[nivel].unique())
    linhas = []
    for territorio in territorios:
        v_cand = int(votos_candidato.get(territorio, 0))
        v_rival = int(maior_rival.get(territorio, 0))
        if v_cand == 0:
            linhas.append({nivel: territorio, "situacao": "sem_votos_no_territorio", "margem_pct": -100.0})
            continue
        if v_rival == 0:
            linhas.append({nivel: territorio, "situacao": "dominio_absoluto", "margem_pct": 100.0})
            continue
        margem = (v_cand - v_rival) / max(v_cand, v_rival)
        if margem >= margem_relativa:
            situacao = "dominio"
        elif margem <= -margem_relativa:
            situacao = "desvantagem"
        else:
            situacao = "disputa_acirrada"
        linhas.append({nivel: territorio, "situacao": situacao, "margem_pct": round(margem * 100, 2)})

    classificacao = pd.DataFrame(linhas)
    return territorial.merge(classificacao, on=nivel, how="left")


def delta_vs_rivais(
    matriz: pd.DataFrame, coluna_territorio: str, nome_candidato: str
) -> pd.DataFrame:
    """Delta de votos (candidato - rival) por territorio, para cada rival
    presente em `matriz` (saida de `matriz_candidato_territorio`). Formato
    longo: um registro por par (territorio, rival)."""
    rivais = [c for c in matriz.columns if c not in (coluna_territorio, nome_candidato)]
    linhas = []
    for _, row in matriz.iterrows():
        votos_cand = float(row[nome_candidato])
        for rival in rivais:
            votos_rival = float(row[rival])
            maior = max(votos_cand, votos_rival)
            delta_pct = round(100 * (votos_cand - votos_rival) / maior, 2) if maior else 0.0
            linhas.append({
                coluna_territorio: row[coluna_territorio],
                "rival": rival,
                "votos_candidato": votos_cand,
                "votos_rival": votos_rival,
                "delta": votos_cand - votos_rival,
                "delta_pct": delta_pct,
            })
    return pd.DataFrame(linhas)


def rivais_por_similaridade_eleitorado(
    candidatura: Candidatura,
    votos_disputa: pd.DataFrame,
    registro_disputa: pd.DataFrame,
    nivel: str,
    top_n: int = 3,
    minimo_territorios_comuns: int = 5,
) -> tuple[pd.DataFrame, list[DataIssue]]:
    """Encontra os rivais que mais disputam a MESMA base eleitoral do
    candidato - nao os mais proximos em volume de votos (ver
    `concorrentes_diretos`), mas os que tem a distribuicao geografica de
    votos mais parecida com a dele.

    Metodologia: para cada candidato nominal, constroi um vetor de
    PARTICIPACAO percentual dos proprios votos em cada territorio onde o
    candidato-alvo tem presenca (votos do candidato no territorio / total
    de votos do candidato em toda a disputa * 100). Calcula a correlacao
    de Pearson entre o vetor do candidato-alvo e o vetor de cada rival
    NESSES MESMOS territorios - isso mede se o rival tambem e forte
    exatamente onde o candidato-alvo e forte, independente do tamanho
    total de cada candidatura. So considera rivais com pelo menos
    `minimo_territorios_comuns` territorios em comum com votos > 0
    (correlacao com poucos pontos nao e confiavel)."""
    issues: list[DataIssue] = []
    nominais = _votos_nominais(votos_disputa, registro_disputa)
    por_territorio = nominais.groupby([nivel, "NR_VOTAVEL"], as_index=False)["QT_VOTOS"].sum()
    pivot = por_territorio.pivot_table(
        index=nivel, columns="NR_VOTAVEL", values="QT_VOTOS", fill_value=0
    )

    if candidatura.numero not in pivot.columns:
        return pd.DataFrame(), [
            DataIssue(
                etapa="rivais_por_similaridade_eleitorado", severidade="erro",
                mensagem="Candidato sem votos territorializados - similaridade nao calculada.",
            )
        ]

    territorios_candidato = pivot.index[pivot[candidatura.numero] > 0]
    if len(territorios_candidato) < minimo_territorios_comuns:
        return pd.DataFrame(), [
            DataIssue(
                etapa="rivais_por_similaridade_eleitorado", severidade="erro",
                mensagem=(
                    f"Candidato tem votos em apenas {len(territorios_candidato)} territorios "
                    f"(minimo exigido: {minimo_territorios_comuns}) - similaridade nao calculada."
                ),
            )
        ]

    subset = pivot.loc[territorios_candidato]
    total_candidato = subset[candidatura.numero].sum()
    participacao_candidato = subset[candidatura.numero] / total_candidato * 100

    registro_unico = registro_disputa.drop_duplicates("numero")
    linhas = []
    for numero_rival in subset.columns:
        if numero_rival == candidatura.numero:
            continue
        votos_rival_aqui = subset[numero_rival]
        n_overlap = int((votos_rival_aqui > 0).sum())
        if n_overlap < minimo_territorios_comuns:
            continue
        total_rival = float(pivot[numero_rival].sum())
        if not total_rival:
            continue
        participacao_rival = votos_rival_aqui / total_rival * 100
        r, p = stats.pearsonr(participacao_candidato, participacao_rival)
        linhas.append({
            "numero": numero_rival,
            "correlacao_base_eleitoral": round(float(r), 3),
            "p_valor": round(float(p), 4),
            "territorios_em_comum": n_overlap,
            "total_votos_rival": int(total_rival),
        })

    if not linhas:
        issues.append(
            DataIssue(
                etapa="rivais_por_similaridade_eleitorado", severidade="aviso",
                mensagem=(
                    f"Nenhum concorrente com pelo menos {minimo_territorios_comuns} territorios "
                    "em comum para calcular similaridade de base eleitoral."
                ),
            )
        )
        return pd.DataFrame(), issues

    resultado = (
        pd.DataFrame(linhas)
        .merge(registro_unico[["numero", "nome_urna", "partido_sigla"]], on="numero", how="left")
        .sort_values("correlacao_base_eleitoral", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    resultado["delta_total_votos"] = candidatura.total_votos - resultado["total_votos_rival"]

    sobreposicoes = []
    for numero_rival in resultado["numero"]:
        votos_rival_aqui = subset[numero_rival]
        participacao_rival_aqui = votos_rival_aqui / float(pivot[numero_rival].sum()) * 100
        comparativo = pd.DataFrame({
            "p_cand": participacao_candidato, "p_rival": participacao_rival_aqui,
        })
        comparativo["min_participacao"] = comparativo[["p_cand", "p_rival"]].min(axis=1)
        top3 = comparativo.sort_values("min_participacao", ascending=False).head(3).index.tolist()
        sobreposicoes.append(", ".join(str(t) for t in top3))
    resultado["territorios_maior_sobreposicao"] = sobreposicoes

    return resultado, issues
