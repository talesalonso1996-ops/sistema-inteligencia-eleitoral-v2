"""Comparativo historico automatico entre a candidatura selecionada e uma
POSSIVEL segunda disputa REAL da MESMA pessoa em outro ano carregado neste
projeto (Etapa 8, tipo 3 - Secao 28 do briefing de expansao SIET, mirando a
"Parte 3"/relatorio comparativo entregue como arquivo para candidatos reais
nesta sessao - Priante 2014-2022, Boulos 2022-2024).

NOTA METODOLOGICA CENTRAL - risco de falso-positivo por homonimo: as fontes
deste projeto (consulta_cand) NAO trazem CPF nem titulo de eleitor, so
NM_CANDIDATO (nome completo declarado). O cruzamento entre anos e feito por
nome completo normalizado + mesma UF - nunca um identificador unico. Por
isso o casamento e DELIBERADAMENTE conservador: so e aceito quando existe
EXATAMENTE UMA combinacao (numero, cargo) com aquele nome/UF no ano
comparavel; zero ou mais de uma combinacao => nenhum comparativo e
mostrado (nunca adivinha entre homonimos). Toda saida desta funcao carrega
esse aviso de forma explicita.

Cobertura de dado real desta versao (2026): consulta_cand existe para
2018/2022/2024, e votacao_secao TAMBEM existe para os 3 anos - 2018 usa uma
fonte alternativa real (dataset publico br_tse_eleicoes do Base dos Dados/
BigQuery, ja que o CDN oficial do TSE bloqueia o download de
votacao_secao_2018 com 403), convertida para o MESMO schema de
votacao_secao_2022/2024 (ver scripts/converter_votacao_secao_2018_bigquery.py
e a nota em config/data_sources.yaml) e publicada como fallback automatico
em src/uf_data_bootstrap.py - por isso 2018 flui pelas MESMAS funcoes
`_generalizado` usadas para 2022, sem nenhum caminho de carregamento
especial aqui. Unica limitacao real que sobrevive dessa fonte: so votos
NOMINAIS (sem legenda/branco/nulo) - ver `_LIMITACAO_VOTOS_NOMINAIS_2018`.
Quando nao ha dado territorial para o ano comparavel (falha de rede ao
baixar o fallback, por exemplo), o match e reportado como registro real
(cargo/partido/resultado) sem territorio, nunca fabricado."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .candidate_finder import (
    Candidatura,
    _conexao,
    _fonte_consulta_candidatos_ano,
    _scan_parquet,
    buscar_candidatos_disputa,
    registro_candidatos_disputa,
    registro_candidatos_disputa_generalizado,
    votos_da_candidatura,
    votos_da_candidatura_generalizado,
    votos_da_disputa,
    votos_da_disputa_generalizado,
)
from .electoral_metrics import desempenho_territorial
from .vote_filtering import secao_composta

_LIMITACAO_MATCH_NOME = (
    "O cruzamento entre eleicoes e feito por NOME DECLARADO ao TSE + mesma UF "
    "(consulta_cand nao traz CPF nem titulo de eleitor nas fontes deste "
    "projeto) - nao e um identificador unico. So e aceito quando existe "
    "EXATAMENTE uma combinacao (numero, cargo) com aquele nome nessa UF no "
    "ano comparavel; havendo ambiguidade (dois ou mais homonimos) ou nenhum "
    "resultado, nenhum comparativo e mostrado."
)

_LIMITACAO_ZONA_INSTAVEL = (
    "A comparacao usa NR_ZONA (zona eleitoral) como unidade comum entre os "
    "dois anos - zonas sao geograficas e votadas por todos os cargos "
    "simultaneamente, mas a numeracao pode mudar em redistritamentos raros "
    "entre ciclos; a comparacao usa so as zonas presentes nos dois anos."
)

_LIMITACAO_VOTOS_NOMINAIS_2018 = (
    "O dado de 2018 vem de uma fonte alternativa real (dataset publico "
    "br_tse_eleicoes, Base dos Dados/BigQuery) porque o TSE bloqueia o "
    "download oficial de votacao por secao desse ano - mesmo nivel de "
    "secao/zona de 2022 e 2024, mas so com voto NOMINAL (sem legenda, "
    "branco ou nulo): percentuais sobre votos validos podem ficar levemente "
    "diferentes dos de 2022/2024 para cargos proporcionais."
)

_ANO_FONTE_ALTERNATIVA = 2018


@dataclass
class ResultadoComparativoHistorico:
    candidatura_atual: Candidatura
    candidatura_comparavel: Candidatura | None
    territorial_atual: pd.DataFrame | None = None
    territorial_comparavel: pd.DataFrame | None = None
    votos_totais_comparavel: int | None = None  # soma real de vc_comp - fonte unica de verdade,
    # preferida a candidatura_comparavel.total_votos mesmo quando os dois já concordam.
    comparativo_zonas: pd.DataFrame | None = None
    correlacao_territorial: float | None = None
    n_zonas_comuns: int = 0
    limitacoes: list[str] = field(default_factory=list)


def ano_comparavel_padrao(ano_eleicao: int) -> int | None:
    """Ano com votacao_secao real disponivel localmente para tentar o
    comparativo, dado o ano da candidatura atual - so 2022 e 2024 tem esse
    dado carregado neste projeto (ver nota do modulo)."""
    if ano_eleicao == 2024:
        return 2022
    if ano_eleicao == 2022:
        return 2024
    return None


def _normalizar_nome(nome: str) -> str:
    return " ".join(nome.strip().upper().split())


def buscar_candidatura_comparavel(candidatura: Candidatura, ano_alvo: int) -> Candidatura | None:
    """Procura, no ano_alvo, uma UNICA candidatura real com o mesmo nome
    completo (normalizado) e a mesma UF - nunca escolhe entre homonimos
    (ver nota metodologica do modulo)."""
    if ano_alvo == candidatura.ano_eleicao:
        return None
    nome_norm = _normalizar_nome(candidatura.nome_completo).replace("'", "''")
    con = _conexao()
    sql = f"""
        SELECT DISTINCT
            NR_CANDIDATO AS numero, DS_CARGO AS cargo, NR_TURNO AS turno,
            TRY_CAST(SG_UE AS INTEGER) AS codigo_municipio_tse, TP_ABRANGENCIA AS abrangencia
        FROM {_scan_parquet(_fonte_consulta_candidatos_ano(ano_alvo))}
        WHERE UPPER(TRIM(NM_CANDIDATO)) = '{nome_norm}'
          AND SG_UF = '{candidatura.uf.upper()}'
          AND DS_SIT_TOT_TURNO != '#NULO'
    """
    linhas = con.execute(sql).fetchdf()
    if linhas.empty:
        return None

    combinacoes = linhas[["numero", "cargo"]].drop_duplicates()
    if len(combinacoes) != 1:
        return None  # 0 ou >1 homonimos - nunca adivinha

    linha = linhas.sort_values("turno").iloc[0]
    cargo = str(linha["cargo"]).strip()
    municipio_codigo = (
        int(linha["codigo_municipio_tse"])
        if str(linha["abrangencia"]).upper() == "MUNICIPAL" and pd.notna(linha["codigo_municipio_tse"])
        else None
    )
    try:
        candidatos = buscar_candidatos_disputa(
            ano_alvo, cargo, candidatura.uf, municipio_codigo=municipio_codigo,
            turno=int(linha["turno"]), numero=int(linha["numero"]),
        )
    except (ValueError, KeyError):
        return None
    return candidatos[0] if candidatos else None


def _carregar_disputa(candidatura: Candidatura) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """2018 nao precisa de nenhum caminho especial aqui: uf_data_bootstrap.py
    ja resolve o fallback de votacao_secao_2018 (fonte alternativa via
    BigQuery, mesmo schema) de forma transparente para as MESMAS funcoes
    `_generalizado` usadas por 2022/2024."""
    if candidatura.codigo_municipio_tse is not None:
        vc = votos_da_candidatura(candidatura)
        vd = votos_da_disputa(candidatura)
        rd = registro_candidatos_disputa(candidatura)
    else:
        vc = votos_da_candidatura_generalizado(candidatura)
        vd = votos_da_disputa_generalizado(candidatura)
        rd = registro_candidatos_disputa_generalizado(candidatura)
    vc = vc.copy()
    vd = vd.copy()
    vc["NR_SECAO_COMPOSTA"] = secao_composta(vc)
    vd["NR_SECAO_COMPOSTA"] = secao_composta(vd)
    return vc, vd, rd


def montar_comparativo_historico(
    candidatura: Candidatura,
    vc_atual: pd.DataFrame, vd_atual: pd.DataFrame, rd_atual: pd.DataFrame,
    ano_alvo: int | None = None,
) -> ResultadoComparativoHistorico:
    """Ponto de entrada principal: procura uma segunda disputa real
    comparavel e, quando encontrada E com votacao por secao disponivel para
    os dois anos, monta o comparativo territorial (NR_ZONA). Degrada
    graciosamente (nunca lanca excecao) quando nao ha comparativo real
    possivel - ver `ResultadoComparativoHistorico.limitacoes`."""
    if ano_alvo is None:
        ano_alvo = ano_comparavel_padrao(candidatura.ano_eleicao)
    if ano_alvo is None:
        return ResultadoComparativoHistorico(
            candidatura, None,
            limitacoes=[
                _LIMITACAO_MATCH_NOME,
                f"Nao ha um segundo ano com votacao por secao carregada localmente para "
                f"comparar com {candidatura.ano_eleicao}.",
            ],
        )

    comparavel = buscar_candidatura_comparavel(candidatura, ano_alvo)
    limitacoes = [_LIMITACAO_MATCH_NOME]
    if comparavel is None:
        limitacoes.append(
            f"Nenhuma candidatura real comparavel encontrada para {candidatura.nome_completo} "
            f"em {candidatura.uf}/{ano_alvo} (zero ou mais de um nome correspondente) - "
            "nenhum comparativo historico e mostrado."
        )
        return ResultadoComparativoHistorico(candidatura, None, limitacoes=limitacoes)

    vc_comp, vd_comp, rd_comp = _carregar_disputa(comparavel)
    if vc_comp.empty:
        limitacoes.append(
            f"Candidatura encontrada em {ano_alvo} ({comparavel.cargo}, {comparavel.partido_sigla}) "
            "mas sem dado de votacao disponivel neste projeto para esse ano - "
            "comparativo territorial nao pode ser calculado, so o registro."
        )
        return ResultadoComparativoHistorico(candidatura, comparavel, limitacoes=limitacoes)

    if ano_alvo == _ANO_FONTE_ALTERNATIVA:
        limitacoes.append(_LIMITACAO_VOTOS_NOMINAIS_2018)

    terr_atual = desempenho_territorial(candidatura, vc_atual, vd_atual, rd_atual, "NR_ZONA")
    terr_comp = desempenho_territorial(comparavel, vc_comp, vd_comp, rd_comp, "NR_ZONA")

    ano_a, ano_b = candidatura.ano_eleicao, ano_alvo
    comparativo = terr_atual[["NR_ZONA", "votos_candidato", "pct_votos_validos_territorio"]].merge(
        terr_comp[["NR_ZONA", "votos_candidato", "pct_votos_validos_territorio"]],
        on="NR_ZONA", how="inner", suffixes=(f"_{ano_a}", f"_{ano_b}"),
    )
    correlacao = None
    if len(comparativo) >= 3:
        correlacao = round(
            float(comparativo[f"votos_candidato_{ano_a}"].corr(comparativo[f"votos_candidato_{ano_b}"])), 3,
        )
    limitacoes.append(_LIMITACAO_ZONA_INSTAVEL)
    return ResultadoComparativoHistorico(
        candidatura_atual=candidatura, candidatura_comparavel=comparavel,
        territorial_atual=terr_atual, territorial_comparavel=terr_comp,
        votos_totais_comparavel=int(terr_comp["votos_candidato"].sum()),
        comparativo_zonas=comparativo, correlacao_territorial=correlacao,
        n_zonas_comuns=len(comparativo), limitacoes=limitacoes,
    )
