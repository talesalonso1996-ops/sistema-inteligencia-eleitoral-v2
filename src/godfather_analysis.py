"""Analise do padrinho politico declarado no Questionario do Candidato
(Modo 1 - `IdentificacaoAnalise.nome_padrinho_politico`, ver
src/questionnaire/candidate_questionnaire.py). Metodologia em 2 camadas,
NUNCA misturadas num unico numero (mesmo principio ja aplicado em todo o
SIET - ex.: Matriz Integrada Candidato x Territorio x Pauta):

1. CRUZAMENTO REAL COM O TSE (automatico, esta modulo): busca o nome
   declarado no registro real de candidatos (consulta_cand, 2018/2022/
   2024, mesma UF do candidato) - mesmo padrao conservador ja usado em
   `candidate_history.buscar_candidatura_comparavel` (nome completo
   normalizado + UF, nunca CPF/titulo de eleitor - as fontes deste
   projeto nao trazem isso -, nunca escolhe entre homonimos: exige
   EXATAMENTE uma combinacao numero+cargo por ano verificado). Quando
   encontrado, calcula o IDP (Indice de Desempenho Politico) do padrinho
   na disputa REAL mais forte (mais votos) entre os anos onde ele foi
   encontrado - reaproveita `candidate_performance_indices.py`, ja
   validado nesta sessao, em vez de inventar uma metrica nova de "forca
   do padrinho".
2. PESQUISA MANUAL COMPLEMENTAR (nunca automatica - fora deste modulo):
   quando o padrinho NAO e encontrado no TSE (comum - empresarios,
   liderancas religiosas/comunitarias, pessoas que nunca disputaram
   eleicao, etc.), a UI (app.py) convida o analista a pesquisar
   externamente e preencher um campo de contexto. Este modulo NUNCA
   chama uma API de busca externa - Playwright/WebSearch/qualquer
   servico de pesquisa nao e uma dependencia real deste projeto (mesmo
   principio ja aplicado a exportacao de PDF, ver ETAPA1_ARQUITETURA.md)
   e nao rodaria de forma confiavel/gratuita no Streamlit Community
   Cloud."""
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
from .indicators.candidate_performance_indices import calcular_indices_desempenho_real

_ANOS_DISPONIVEIS = (2024, 2022, 2018)

LIMITACAO_MATCH_NOME = (
    "O cruzamento com o TSE e feito por NOME DECLARADO + mesma UF do candidato "
    "(as fontes deste projeto nao trazem CPF nem titulo de eleitor) - nao e um "
    "identificador unico. So e aceito quando existe EXATAMENTE uma combinacao "
    "(numero, cargo) com aquele nome nessa UF, em cada ano verificado (2018/2022/2024); "
    "havendo ambiguidade (2+ homonimos) ou nenhum resultado, aquele ano e ignorado - "
    "nunca adivinha entre pessoas diferentes com o mesmo nome."
)

LIMITACAO_ESCOPO_IDP = (
    "O Indice de Desempenho Politico (IDP) mede a forca eleitoral REAL e "
    "observavel do padrinho (colocacao, proximidade de ser eleito, forca no "
    "proprio partido) na disputa mais forte encontrada - nunca sua reputacao, "
    "popularidade pessoal ou influencia informal, que nao sao dado eleitoral "
    "verificavel."
)

LIMITACAO_TOP_TERRITORIOS = (
    "Territorios reais onde o padrinho teve seu MELHOR desempenho (maior participacao "
    "sobre os votos validos do proprio territorio) na disputa encontrada - um sinal real "
    "de 'base eleitoral emprestada', nao uma garantia de que o candidato-afilhado tera o "
    "mesmo desempenho ali."
)


@dataclass
class AnalisePadrinhoPolitico:
    nome_declarado: str
    uf: str
    encontrado_no_tse: bool
    candidatura_encontrada: Candidatura | None = None
    indice_forca_idp: float | None = None
    classificacao_forca: str | None = None
    anos_verificados: list[int] = field(default_factory=list)
    # Top territorios REAIS do padrinho (colunas: nivel territorial usado -
    # NR_ZONA se o padrinho foi candidato municipal, CD_MUNICIPIO se foi
    # estadual/distrital -, votos_candidato, pct_votos_validos_territorio) -
    # sinal real de "base eleitoral emprestada", nunca do candidato-afilhado.
    top_territorios: pd.DataFrame | None = None
    limitacoes: list[str] = field(default_factory=list)


def _buscar_por_nome_uf_no_ano(nome_normalizado: str, uf: str, ano: int) -> Candidatura | None:
    """Mesma logica conservadora de
    candidate_history.buscar_candidatura_comparavel, generalizada para
    buscar por um NOME DECLARADO qualquer (nao precisa de uma Candidatura
    ja carregada) - usada aqui para cruzar o nome do padrinho politico.
    Nunca escolhe entre homonimos: zero ou 2+ combinacoes (numero, cargo)
    para o mesmo nome/UF no ano faz a busca retornar None para esse ano."""
    con = _conexao()
    sql = f"""
        SELECT DISTINCT
            NR_CANDIDATO AS numero, DS_CARGO AS cargo, NR_TURNO AS turno,
            TRY_CAST(SG_UE AS INTEGER) AS codigo_municipio_tse, TP_ABRANGENCIA AS abrangencia
        FROM {_scan_parquet(_fonte_consulta_candidatos_ano(ano))}
        WHERE UPPER(TRIM(NM_CANDIDATO)) = '{nome_normalizado}'
          AND SG_UF = '{uf.upper()}'
          AND DS_SIT_TOT_TURNO != '#NULO'
    """
    linhas = con.execute(sql).fetchdf()
    if linhas.empty:
        return None

    combinacoes = linhas[["numero", "cargo"]].drop_duplicates()
    if len(combinacoes) != 1:
        return None  # 0 ou 2+ homonimos - nunca adivinha

    linha = linhas.sort_values("turno").iloc[0]
    cargo = str(linha["cargo"]).strip()
    municipio_codigo = (
        int(linha["codigo_municipio_tse"])
        if str(linha["abrangencia"]).upper() == "MUNICIPAL" and pd.notna(linha["codigo_municipio_tse"])
        else None
    )
    try:
        candidatos = buscar_candidatos_disputa(
            ano, cargo, uf, municipio_codigo=municipio_codigo,
            turno=int(linha["turno"]), numero=int(linha["numero"]),
        )
    except (ValueError, KeyError):
        return None
    return candidatos[0] if candidatos else None


def _carregar_disputa(candidatura: Candidatura) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if candidatura.codigo_municipio_tse is not None:
        return (
            votos_da_candidatura(candidatura), votos_da_disputa(candidatura),
            registro_candidatos_disputa(candidatura),
        )
    return (
        votos_da_candidatura_generalizado(candidatura), votos_da_disputa_generalizado(candidatura),
        registro_candidatos_disputa_generalizado(candidatura),
    )


def analisar_padrinho_politico(nome_padrinho: str | None, uf: str) -> AnalisePadrinhoPolitico | None:
    """Ponto de entrada: cruza o nome do padrinho politico declarado no
    questionario com o registro real do TSE (2018/2022/2024, mesma UF do
    candidato). Retorna None quando nome_padrinho nao foi declarado -
    nunca roda a busca a toa. Quando encontrado em mais de um ano, usa a
    disputa com MAIS VOTOS (sinal real mais forte), nao a mais recente."""
    if not nome_padrinho or not nome_padrinho.strip():
        return None
    nome_norm = " ".join(nome_padrinho.strip().upper().split())

    melhor: Candidatura | None = None
    anos_verificados: list[int] = []
    for ano in _ANOS_DISPONIVEIS:
        encontrada = _buscar_por_nome_uf_no_ano(nome_norm, uf, ano)
        if encontrada is None:
            continue
        anos_verificados.append(ano)
        if melhor is None or encontrada.total_votos > melhor.total_votos:
            melhor = encontrada

    if melhor is None:
        return AnalisePadrinhoPolitico(
            nome_declarado=nome_padrinho.strip(), uf=uf.upper(), encontrado_no_tse=False,
            limitacoes=[LIMITACAO_MATCH_NOME],
        )

    vc, vd, rd = _carregar_disputa(melhor)
    nivel = "NR_ZONA" if melhor.codigo_municipio_tse is not None else "CD_MUNICIPIO"
    indices = calcular_indices_desempenho_real(melhor, vc, vd, rd, nivel)

    terr = desempenho_territorial(melhor, vc, vd, rd, nivel)
    top_territorios = None
    if not terr.empty:
        colunas = [c for c in [nivel, "votos_candidato", "pct_votos_validos_territorio"] if c in terr.columns]
        top_territorios = (
            terr[colunas].sort_values("pct_votos_validos_territorio", ascending=False).head(5).reset_index(drop=True)
        )

    return AnalisePadrinhoPolitico(
        nome_declarado=nome_padrinho.strip(), uf=uf.upper(), encontrado_no_tse=True,
        candidatura_encontrada=melhor,
        indice_forca_idp=indices.idp.valor,
        classificacao_forca=indices.idp.classificacao,
        anos_verificados=anos_verificados,
        top_territorios=top_territorios,
        limitacoes=[LIMITACAO_MATCH_NOME, LIMITACAO_ESCOPO_IDP, LIMITACAO_TOP_TERRITORIOS],
    )
