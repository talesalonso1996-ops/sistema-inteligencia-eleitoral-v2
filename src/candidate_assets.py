"""Patrimonio declarado por candidato (TSE - bem_candidato) - Fase 5, item C.

bem_candidato NAO identifica o candidato por NR_CANDIDATO (numero de urna) -
so por SQ_CANDIDATO, um ID sequencial interno do TSE presente em
consulta_cand mas que nao fazia parte das colunas originalmente mantidas
neste projeto (ver scripts/adicionar_sq_candidato.py, que reprocessou
consulta_cand_2022_BR.parquet/consulta_cand_2024_BR.parquet para incluir
essa coluna). Por isso o primeiro passo aqui e sempre resolver o
SQ_CANDIDATO a partir dos campos que a Candidatura ja tem (numero, UF,
municipio, ano, turno, cargo) - mesmo padrao de filtro ja usado por
candidate_finder.registro_candidatos_disputa.
"""
from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pandas as pd

from .candidate_finder import Candidatura, _fonte_consulta_candidatos_ano, _scan_parquet
from .rules.electoral_scope import resolver_escopo
from .utils import cache_key, data_sources, get_logger, resolve_path, read_cache, write_cache

logger = get_logger(__name__)


@dataclass
class PerfilPatrimonialCandidato:
    numero: int
    valor_total_bens: float | None
    n_itens_declarados: int
    top_bens: pd.DataFrame  # colunas: tipo, descricao, valor
    disponivel: bool
    limitacoes: str = (
        "Valor total autodeclarado pelo proprio candidato ao TSE - nao e uma auditoria "
        "patrimonial, apenas o que consta oficialmente na candidatura."
    )


def _caminho(caminho: str) -> str:
    return caminho if (len(caminho) > 1 and caminho[1] == ":") else str(resolve_path(caminho))


def _resolver_sq_candidato(
    numero: int, ano_eleicao: int, cargo: str, turno: int, uf: str,
    codigo_municipio_tse: int | None, municipio: str,
) -> int | None:
    """Mesma logica de filtro ja usada por
    candidate_finder.registro_candidatos_disputa, so acrescentando
    NR_CANDIDATO para achar 1 candidato especifico (nao a disputa inteira)."""
    con = duckdb.connect()
    escopo = resolver_escopo(ano_eleicao, cargo, uf=uf, municipio=municipio, turno=turno)
    filtros = [
        f"DS_CARGO = '{cargo}'",
        f"ANO_ELEICAO = {ano_eleicao}",
        f"NR_TURNO = {turno}",
        f"NR_CANDIDATO = {numero}",
        f"DS_ELEICAO ILIKE '{escopo.filtro_sql_ds_eleicao}'",
    ]
    if escopo.filtro_sql_tp_abrangencia:
        filtros.append(f"TP_ABRANGENCIA = '{escopo.filtro_sql_tp_abrangencia}'")
    if codigo_municipio_tse is not None:
        filtros.append(f"TRY_CAST(SG_UE AS INTEGER) = {codigo_municipio_tse}")
    else:
        filtros.append(f"SG_UF = '{uf.upper()}'")

    sql = f"""
        SELECT SQ_CANDIDATO
        FROM {_scan_parquet(_fonte_consulta_candidatos_ano(ano_eleicao))}
        WHERE {" AND ".join(filtros)}
        LIMIT 1
    """
    resultado = con.execute(sql).fetchdf()
    return int(resultado["SQ_CANDIDATO"].iloc[0]) if not resultado.empty else None


def _perfil_vazio(numero: int) -> PerfilPatrimonialCandidato:
    return PerfilPatrimonialCandidato(
        numero=numero, valor_total_bens=None, n_itens_declarados=0,
        top_bens=pd.DataFrame(columns=["tipo", "descricao", "valor"]), disponivel=False,
    )


def carregar_patrimonio_candidato(candidatura: Candidatura) -> PerfilPatrimonialCandidato:
    """Ponto de entrada principal: bens declarados do candidato ao TSE.
    Nunca lanca excecao por dado ausente - retorna disponivel=False se a
    fonte nao existir ou o candidato nao for encontrado (nunca inventa
    valor)."""
    # top_bens e cacheada como uma tabela PROPRIA (nao aninhada dentro de
    # uma celula do resumo) - uma lista de dicts guardada numa unica celula
    # nao sobrevive ao round-trip via parquet (write_cache/read_cache):
    # a coluna volta como uma serie de dicts soltos em vez de reconstruir
    # tipo/descricao/valor, um bug real pego testando a leitura do cache
    # (nao so o calculo na hora).
    key = cache_key(
        "patrimonio", candidatura.numero, candidatura.ano_eleicao, candidatura.cargo,
        candidatura.uf, candidatura.codigo_municipio_tse, candidatura.turno,
    )
    cached = read_cache("candidate_assets", key)
    if cached is not None:
        if cached.empty:
            return _perfil_vazio(candidatura.numero)
        linha = cached.iloc[0]
        top_bens = read_cache("candidate_assets_top_bens", key)
        return PerfilPatrimonialCandidato(
            numero=candidatura.numero, valor_total_bens=linha["valor_total_bens"],
            n_itens_declarados=int(linha["n_itens_declarados"]),
            top_bens=top_bens if top_bens is not None else pd.DataFrame(columns=["tipo", "descricao", "valor"]),
            disponivel=True,
        )

    sq_candidato = _resolver_sq_candidato(
        candidatura.numero, candidatura.ano_eleicao, candidatura.cargo, candidatura.turno,
        candidatura.uf, candidatura.codigo_municipio_tse, candidatura.municipio,
    )
    if sq_candidato is None:
        write_cache("candidate_assets", key, pd.DataFrame())
        return _perfil_vazio(candidatura.numero)

    fonte = data_sources()["tse"].get("bens_candidatos")
    if fonte is None:
        return _perfil_vazio(candidatura.numero)
    caminho = _caminho(f"data/raw/bem_candidato_{candidatura.ano_eleicao}_BR.parquet")
    from pathlib import Path

    if not Path(caminho).exists():
        logger.warning("Arquivo bem_candidato nao encontrado: %s", caminho)
        return _perfil_vazio(candidatura.numero)

    df = pd.read_parquet(caminho)
    linhas = df[df["SQ_CANDIDATO"] == sq_candidato]
    if linhas.empty:
        write_cache("candidate_assets", key, pd.DataFrame())
        return _perfil_vazio(candidatura.numero)

    valor_total = round(float(linhas["VR_BEM_CANDIDATO"].sum()), 2)
    top_bens = (
        linhas.nlargest(5, "VR_BEM_CANDIDATO")[["DS_TIPO_BEM_CANDIDATO", "DS_BEM_CANDIDATO", "VR_BEM_CANDIDATO"]]
        .rename(columns={
            "DS_TIPO_BEM_CANDIDATO": "tipo", "DS_BEM_CANDIDATO": "descricao", "VR_BEM_CANDIDATO": "valor",
        })
        .reset_index(drop=True)
    )
    resultado = PerfilPatrimonialCandidato(
        numero=candidatura.numero, valor_total_bens=valor_total,
        n_itens_declarados=len(linhas), top_bens=top_bens, disponivel=True,
    )
    write_cache(
        "candidate_assets", key,
        pd.DataFrame([{"valor_total_bens": valor_total, "n_itens_declarados": len(linhas)}]),
    )
    write_cache("candidate_assets_top_bens", key, top_bens)
    return resultado


def patrimonio_comparativo(candidatura: Candidatura, ranking: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """Compara o patrimonio do candidato-alvo com os top_n maiores rivais
    da MESMA disputa (mesmo ano/cargo/UF/[municipio]/turno) - reusa o
    `ranking` ja calculado (competitor_analysis.ranking_disputa)."""
    rivais = ranking[ranking["NR_VOTAVEL"] != candidatura.numero].head(top_n)
    numeros = [candidatura.numero] + rivais["NR_VOTAVEL"].tolist()
    nomes = {candidatura.numero: candidatura.nome_urna}
    nomes.update(dict(zip(rivais["NR_VOTAVEL"], rivais["nome_urna"])))

    linhas = []
    for numero in numeros:
        sq = _resolver_sq_candidato(
            numero, candidatura.ano_eleicao, candidatura.cargo, candidatura.turno,
            candidatura.uf, candidatura.codigo_municipio_tse, candidatura.municipio,
        )
        perfil = _perfil_vazio(numero)
        if sq is not None:
            caminho = _caminho(f"data/raw/bem_candidato_{candidatura.ano_eleicao}_BR.parquet")
            from pathlib import Path

            if Path(caminho).exists():
                df = pd.read_parquet(caminho)
                linhas_candidato = df[df["SQ_CANDIDATO"] == sq]
                if not linhas_candidato.empty:
                    perfil = PerfilPatrimonialCandidato(
                        numero=numero, valor_total_bens=round(float(linhas_candidato["VR_BEM_CANDIDATO"].sum()), 2),
                        n_itens_declarados=len(linhas_candidato), top_bens=pd.DataFrame(), disponivel=True,
                    )
        linhas.append({
            "numero": numero, "nome_urna": nomes.get(numero, str(numero)),
            "valor_total_bens": perfil.valor_total_bens, "disponivel": perfil.disponivel,
        })
    return pd.DataFrame(linhas)
