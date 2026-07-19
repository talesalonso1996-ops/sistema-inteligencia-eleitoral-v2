"""Sistema de Inteligencia Eleitoral V2 - interface Streamlit.

Fluxo guiado principal: Eleicao -> UF -> [Municipio, so 2024] -> Cargo ->
Candidato (barra lateral) -> resumo da selecao -> botao "Gerar analise
eleitoral". A busca direta por numero do candidato (fluxo original da V1,
2024 apenas) continua disponivel como alternativa, num expander da barra
lateral - nao foi removida.

Cargos municipais (Prefeito/Vereador, 2024) usam o MESMO caminho de dados
e as MESMAS 8 secoes de analise da V1, sem nenhuma mudanca de logica.
Cargos estaduais (Governador - piloto 2022/SP) usam as funcoes
generalizadas de src/candidate_finder.py e mostram um subconjunto de
secoes (Visao Geral/Concorrencia/Territorio por municipio/Indicadores
Estaduais) - Geografia/Demografia/Estatistica Avancada/Maslow dependem da
malha de setores censitarios de UM municipio e ficam fora do escopo deste
piloto (ver plano da V2).

Identidade visual: dashboard escuro ("war room"), paleta consistente com
src/charts.py e .streamlit/config.toml.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.candidate_finder import (
    Candidatura,
    buscar_candidaturas,
    buscar_candidatos_disputa,
    listar_municipios_uf,
    registro_candidatos_disputa,
    registro_candidatos_disputa_generalizado,
    votos_da_candidatura,
    votos_da_candidatura_generalizado,
    votos_da_disputa,
    votos_da_disputa_generalizado,
)
from src.rules.electoral_scope import cargos_disponiveis, resolver_escopo
from src.state_scope_indicators import (
    calcular_concentracao_territorial,
    calcular_indice_capilaridade,
    calcular_presenca_eleitoral,
)
from src.uf_nomes import UF_NOME
from src.clustering import gerar_narrativa_clusters, segmentar_territorios
from src.competitor_analysis import (
    concorrentes_diretos,
    delta_vs_rivais,
    matriz_candidato_territorio,
    ranking_disputa,
    ranking_partidos,
    rivais_por_similaridade_eleitorado,
    zonas_de_disputa,
)
from src.correlation_analysis import correlacoes_com_votos
from src.demographic_analysis import perfil_demografico_do_territorio, perfil_demografico_por_setor
from src.economic_analysis import carregar_perfil_economico_municipio
from src.electoral_metrics import (
    desempenho_territorial,
    enriquecer_com_comparecimento_abstencao,
    indice_concentracao_hhi,
    resultado_geral,
)
from src.excel_exporter import exportar_excel
from src.geographic_analysis import (
    agregar_votos_por_bairro,
    atribuir_setor_e_bairro,
    carregar_coordenadas_locais,
    carregar_fronteira_municipio,
    carregar_malha,
    juntar_votos_com_coordenadas,
    juntar_votos_com_coordenadas_secao,
    total_votos_validos_por_territorio,
    uf_tem_malha_completa,
)
from src.maslow_analysis import gerar_analise_maslow
from src.potential_analysis import identificar_bairros_potencial
from src.potential_index import calcular_indice_performance
from src.regression_models import regressao_linear_votos, regressao_logistica_bom_desempenho
from src.report_generator import DadosRelatorio, gerar_relatorio_html, gerar_relatorio_pdf
from src.utils import indicators_config, resolve_path
from src.vote_filtering import secao_composta
from src.voronoi_analysis import gerar_voronoi
import src.charts as charts
import src.maps as maps

st.set_page_config(page_title="Sistema de Inteligencia Eleitoral", layout="wide", page_icon="\U0001F5F3")

from src.cloud_data_bootstrap import garantir_dados_cloud  # noqa: E402

with st.spinner("Preparando dados (primeira execucao neste ambiente pode levar ~1 min)..."):
    _dados_ok = garantir_dados_cloud()
if not _dados_ok:
    st.error(
        "Nao foi possivel baixar o pacote de dados necessario. Verifique a "
        "conexao ou tente novamente em alguns minutos."
    )
    st.stop()

_NIVEL_TERRITORIO_DEMOGRAFICO = "secao_id"
# Nivel territorial usado nas analises estatisticas (regressao/clusterizacao/
# Maslow): SECAO eleitoral (urna), nao local de votacao (predio) nem
# distrito/bairro. Um local de votacao tem em media varias secoes - usar
# secao como unidade multiplica o numero de observacoes disponiveis, essencial
# em municipios pequenos (que podem ter poucos predios de votacao, mas ainda
# assim varias secoes rateadas entre eles). Secoes do mesmo predio
# compartilham a mesma coordenada/perfil demografico (nao sao observacoes
# geograficas independentes) - por isso a regressao usa erro-padrao robusto
# a cluster, agrupado por `local_votacao_id` (o predio fisico, ver
# _COLUNA_CLUSTER_REGRESSAO abaixo), o que evita superestimar a precisao dos
# coeficientes. O mapa coropletico e o Voronoi da aba Geografia continuam por
# predio/bairro/distrito (local_votacao_id) - secoes do mesmo predio tem a
# MESMA coordenada, entao nao fariam sentido como pontos/observacoes
# separadas num mapa.
_COLUNA_CLUSTER_REGRESSAO = "local_votacao_id"
VARIAVEIS_DEMOGRAFICAS = indicators_config()["clustering"]["variaveis_demograficas"]
K_CLUSTERS = indicators_config()["clustering"]["k_fixo"]

# --------------------------------------------------------------------- CSS
st.markdown(
    """
<style>
.candidato-header {
    background: linear-gradient(135deg, #161b22 0%, #1c2530 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 18px;
}
.candidato-header h1 { font-size: 1.5rem; margin: 0 0 6px 0; color: #e6e6e6; }
.candidato-header .subtitulo { color: #8a92a3; font-size: 0.95rem; margin-bottom: 8px; }
.kpi-tile {
    background: #161b22;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 10px;
    height: 100%;
}
.kpi-tile .kpi-label { font-size: 0.75rem; color: #8a92a3; text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 4px; }
.kpi-tile .kpi-value { font-size: 1.7rem; font-weight: 700; color: #e6e6e6; line-height: 1.15; }
.kpi-tile .kpi-delta { font-size: 0.82rem; margin-top: 4px; }
.badge { display: inline-block; padding: 3px 12px; border-radius: 999px; font-size: 0.75rem; font-weight: 700;
         text-transform: uppercase; letter-spacing: 0.02em; }
.secao-explicacao {
    background: #10151c; border-left: 3px solid #2a78d6; border-radius: 6px;
    padding: 10px 16px; margin-bottom: 16px; color: #c3c9d2; font-size: 0.9rem;
}
.cluster-card {
    background: #161b22; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px;
    padding: 12px 16px; margin-bottom: 10px;
}
.cluster-card .titulo { font-weight: 700; color: #e6e6e6; margin-bottom: 4px; }
</style>
""",
    unsafe_allow_html=True,
)

_CORES_TOM = {"bom": ("rgba(12,163,12,0.18)", "#3ddc3d"), "neutro": ("rgba(237,161,0,0.18)", "#f5c451"),
              "ruim": ("rgba(208,59,59,0.18)", "#f27272")}


def _badge(texto: str, tom: str) -> str:
    bg, fg = _CORES_TOM.get(tom, _CORES_TOM["neutro"])
    return f'<span class="badge" style="background:{bg};color:{fg};">{texto}</span>'


def _tom_resultado(resultado_final: str) -> str:
    r = resultado_final.upper()
    if r.startswith("ELEITO"):
        return "bom"
    if "SUPLENTE" in r:
        return "neutro"
    return "ruim"


def _tom_classificacao(classificacao: str) -> str:
    return {"fortaleza": "bom", "consolidado": "bom", "competitivo": "neutro",
            "crescimento": "neutro", "baixa_penetracao": "ruim"}.get(classificacao, "neutro")


def _tom_rotulo_acao(rotulo: str) -> str:
    return {"Fortaleza": "bom", "Consolidar": "neutro", "Alto potencial": "neutro",
            "Baixa prioridade": "ruim"}.get(rotulo, "neutro")


def _kpi(col, rotulo: str, valor: str, delta: str | None = None, tom: str = "neutro") -> None:
    cor = _CORES_TOM.get(tom, _CORES_TOM["neutro"])[1]
    delta_html = f'<div class="kpi-delta" style="color:{cor}">{delta}</div>' if delta else ""
    col.markdown(
        f'<div class="kpi-tile"><div class="kpi-label">{rotulo}</div>'
        f'<div class="kpi-value">{valor}</div>{delta_html}</div>',
        unsafe_allow_html=True,
    )


def _explicacao(texto: str) -> None:
    st.markdown(f'<div class="secao-explicacao">{texto}</div>', unsafe_allow_html=True)


def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "n/d"
    return f"{v:,.0f}".replace(",", ".")


@st.cache_data(show_spinner=False)
def _buscar(numero: int) -> list[Candidatura]:
    return buscar_candidaturas(numero)


@st.cache_data(show_spinner=False)
def _carregar_dados_candidatura(numero, municipio_tse, cargo, ano, turno):
    candidaturas = _buscar(numero)
    candidatura = next(
        c for c in candidaturas
        if c.codigo_municipio_tse == municipio_tse and c.cargo == cargo
        and c.ano_eleicao == ano and c.turno == turno
    )
    vc = votos_da_candidatura(candidatura)
    vd = votos_da_disputa(candidatura)
    rd = registro_candidatos_disputa(candidatura)
    # NR_SECAO sozinho nao identifica uma secao fisica (a numeracao reinicia
    # a cada zona) - a coluna composta e o nivel territorial correto sempre
    # que o usuario escolhe "Secao eleitoral" em qualquer aba do app.
    vc["NR_SECAO_COMPOSTA"] = secao_composta(vc)
    vd["NR_SECAO_COMPOSTA"] = secao_composta(vd)
    return candidatura, vc, vd, rd


@st.cache_data(show_spinner=False)
def _listar_municipios(ano: int, uf: str) -> pd.DataFrame:
    return listar_municipios_uf(ano, uf)


@st.cache_data(show_spinner=False)
def _buscar_candidatos_guiado(ano: int, cargo: str, uf: str, municipio_codigo, turno: int) -> list[Candidatura]:
    return buscar_candidatos_disputa(ano, cargo, uf=uf, municipio_codigo=municipio_codigo, turno=turno)


@st.cache_data(show_spinner=False)
def _carregar_dados_candidatura_v2(ano: int, cargo: str, uf: str, municipio_codigo, turno: int, numero: int):
    """Equivalente a _carregar_dados_candidatura, mas alimentado pelo fluxo
    guiado em cascata (Eleicao->UF->[Municipio]->Cargo->Candidato) em vez
    da busca por numero - cobre tambem cargos estaduais (municipio_codigo
    None), usando as funcoes _generalizado quando aplicavel."""
    candidatos = _buscar_candidatos_guiado(ano, cargo, uf, municipio_codigo, turno)
    candidatura = next(c for c in candidatos if c.numero == numero)
    if candidatura.codigo_municipio_tse is not None:
        vc = votos_da_candidatura(candidatura)
        vd = votos_da_disputa(candidatura)
        rd = registro_candidatos_disputa(candidatura)
    else:
        vc = votos_da_candidatura_generalizado(candidatura)
        vd = votos_da_disputa_generalizado(candidatura)
        rd = registro_candidatos_disputa_generalizado(candidatura)
    vc["NR_SECAO_COMPOSTA"] = secao_composta(vc)
    vd["NR_SECAO_COMPOSTA"] = secao_composta(vd)
    return candidatura, vc, vd, rd


@st.cache_data(show_spinner=False)
def _carregar_geografia(numero, municipio_tse, cargo, ano, turno, _candidatura: Candidatura, _vc: pd.DataFrame):
    coords = carregar_coordenadas_locais(_candidatura)
    pontos = juntar_votos_com_coordenadas(_vc, coords)
    enriquecido, avisos = atribuir_setor_e_bairro(pontos, _candidatura)
    return pontos, enriquecido, avisos


@st.cache_data(show_spinner=False)
def _carregar_geografia_secao(numero, municipio_tse, cargo, ano, turno, _candidatura: Candidatura, _vc: pd.DataFrame):
    """Como _carregar_geografia, mas por SECAO eleitoral (nao por predio) -
    unidade de observacao das analises estatisticas (regressao/
    clusterizacao/Maslow). Ver _NIVEL_TERRITORIO_DEMOGRAFICO."""
    coords = carregar_coordenadas_locais(_candidatura)
    pontos = juntar_votos_com_coordenadas_secao(_vc, coords)
    enriquecido, avisos = atribuir_setor_e_bairro(pontos, _candidatura)
    return pontos, enriquecido, avisos


@st.cache_data(show_spinner=False)
def _carregar_demografia(
    numero, municipio_tse, cargo, ano, turno, _enriquecido: pd.DataFrame, _vd: pd.DataFrame,
):
    nivel = _NIVEL_TERRITORIO_DEMOGRAFICO
    setores = set(_enriquecido["CD_SETOR"].dropna().unique()) if "CD_SETOR" in _enriquecido else set()
    if not setores or nivel not in _enriquecido.columns or _enriquecido[nivel].notna().sum() == 0:
        return pd.DataFrame(), pd.DataFrame()
    perfil_setor = perfil_demografico_por_setor(setores)
    perfil_territorio = perfil_demografico_do_territorio(_enriquecido, perfil_setor, nivel)
    # "first" para local_votacao_id: todo secao_id pertence a exatamente um
    # local_votacao_id (predio), entao nao ha ambiguidade - preservado aqui
    # para uso como coluna de cluster na regressao (secoes do mesmo predio
    # nao sao observacoes independentes, ver _COLUNA_CLUSTER_REGRESSAO).
    agregacoes = {"votos_candidato": ("votos_candidato", "sum")}
    if "local_votacao_id" in _enriquecido.columns and nivel != "local_votacao_id":
        agregacoes["local_votacao_id"] = ("local_votacao_id", "first")
    votos_territorio = _enriquecido.groupby(nivel, as_index=False).agg(**agregacoes)
    total_validos = total_votos_validos_por_territorio(_vd, _enriquecido, nivel)
    base = (
        votos_territorio.merge(perfil_territorio, on=nivel, how="inner")
        .merge(total_validos, on=nivel, how="left")
    )
    base["pct_votos_validos_territorio"] = (
        100 * base["votos_candidato"] / base["votos_validos_territorio"]
    ).round(2)
    return perfil_setor, base


st.sidebar.header("Selecione a disputa")

_ANO_LABELS = {2024: "2024 - Eleicoes Municipais", 2022: "2022 - Eleicoes Gerais"}
ano = st.sidebar.selectbox("Eleicao", list(_ANO_LABELS), format_func=lambda a: _ANO_LABELS[a], key="v2_ano")

_ufs_ordenadas = sorted(UF_NOME.items(), key=lambda kv: kv[1])
_uf_opcoes = {f"{nome} - {sigla}": sigla for sigla, nome in _ufs_ordenadas}
uf_label = st.sidebar.selectbox("UF", ["-- selecione --"] + list(_uf_opcoes.keys()), key="v2_uf")
uf = _uf_opcoes.get(uf_label)

municipio_codigo = None
municipio_nome = None
if uf and ano == 2024:
    with st.spinner("Carregando municipios da UF..."):
        municipios_df = _listar_municipios(ano, uf)
    mun_opcoes = {
        row.municipio: int(row.codigo_municipio_tse)
        for row in municipios_df.itertuples(index=False)
    }
    mun_label = st.sidebar.selectbox("Municipio", ["-- selecione --"] + sorted(mun_opcoes), key="v2_municipio")
    if mun_label != "-- selecione --":
        municipio_codigo = mun_opcoes[mun_label]
        municipio_nome = mun_label

cargo = None
_cargo_pronto = bool(uf) and (ano == 2022 or municipio_codigo is not None)
if _cargo_pronto:
    cargos = cargos_disponiveis(ano, uf=uf)
    cargo_label = st.sidebar.selectbox("Cargo", ["-- selecione --"] + cargos, key="v2_cargo")
    cargo = cargo_label if cargo_label != "-- selecione --" else None

turno = 1
if cargo:
    escopo_provisorio = resolver_escopo(ano, cargo, uf=uf, municipio=(municipio_nome or uf), turno=1)
    if escopo_provisorio.permite_segundo_turno:
        turno = st.sidebar.radio("Turno", [1, 2], format_func=lambda t: f"{t}o turno", horizontal=True, key="v2_turno")

candidatura_guiada = None
if cargo:
    with st.spinner("Buscando candidatos..."):
        candidatos = _buscar_candidatos_guiado(ano, cargo, uf, municipio_codigo, turno)
    if not candidatos:
        st.sidebar.warning("Nenhum candidato encontrado para essa disputa.")
    else:
        busca = st.sidebar.text_input("Buscar (nome, numero ou partido)", key="v2_busca_candidato")
        candidatos_filtrados = candidatos
        if busca:
            busca_low = busca.strip().lower()
            candidatos_filtrados = [
                c for c in candidatos
                if busca_low in c.nome_urna.lower() or busca_low in c.nome_completo.lower()
                or busca_low in str(c.numero) or busca_low in c.partido_sigla.lower()
            ]
        cand_opcoes = {
            f"{c.nome_urna} - {c.numero} - {c.partido_sigla}": c
            for c in sorted(candidatos_filtrados, key=lambda c: -c.total_votos)
        }
        if not cand_opcoes:
            st.sidebar.warning("Nenhum candidato bate com a busca.")
        else:
            cand_label = st.sidebar.selectbox("Candidato", list(cand_opcoes.keys()), key="v2_candidato")
            candidatura_guiada = cand_opcoes[cand_label]

st.sidebar.divider()
candidatura_fallback = None
with st.sidebar.expander("Busca alternativa por numero (2024)"):
    numero_input = st.text_input("Numero do candidato", placeholder="ex.: 15900", key="v2_numero_fallback")
    if numero_input and numero_input.isdigit():
        with st.spinner("Buscando candidaturas no registro nacional do TSE..."):
            candidaturas_num = _buscar(int(numero_input))
        if not candidaturas_num:
            st.warning("Nenhuma candidatura encontrada nas Eleicoes Municipais 2024.")
        else:
            opcoes_num = {
                f"{c.nome_urna} - {c.cargo} - {c.municipio}/{c.uf} - {c.partido_sigla} "
                f"({c.total_votos} votos, {c.resultado_final})": c
                for c in candidaturas_num
            }
            escolha_num = st.selectbox("Selecione a candidatura:", list(opcoes_num.keys()), key="v2_escolha_fallback")
            candidatura_fallback = opcoes_num[escolha_num]

alvo = candidatura_guiada or candidatura_fallback
veio_do_fallback = alvo is candidatura_fallback and alvo is not None

if alvo is None:
    st.title("Sistema de Inteligencia Eleitoral")
    st.caption(
        "Dados oficiais TSE (consulta de candidatos + votacao por secao) e IBGE "
        "(Censo Demografico 2022). Eleicoes Municipais 2024 (Prefeito/Vereador, "
        "Brasil inteiro) e piloto de Eleicoes Gerais 2022 (Governador, SP)."
    )
    st.info(
        "Selecione Eleicao -> UF -> [Municipio] -> Cargo -> Candidato na barra "
        "lateral, ou use a busca alternativa por numero (2024)."
    )
    st.stop()

st.sidebar.divider()
st.sidebar.markdown(
    f"**Resumo da selecao**\n\n"
    f"- Eleicao: {alvo.ano_eleicao}\n"
    f"- UF: {alvo.uf}\n"
    f"- Municipio: {alvo.municipio if alvo.codigo_municipio_tse is not None else '(UF inteira)'}\n"
    f"- Cargo: {alvo.cargo}\n"
    f"- Turno: {alvo.turno}\n"
    f"- Candidato: {alvo.nome_urna} ({alvo.numero}) - {alvo.partido_sigla}\n"
    f"- Abrangencia: {'Municipal' if alvo.codigo_municipio_tse is not None else 'Estadual (piloto)'}"
)
if not st.sidebar.button("Gerar analise eleitoral", type="primary"):
    st.title("Sistema de Inteligencia Eleitoral")
    st.info("Confira o resumo da selecao na barra lateral e clique em **Gerar analise eleitoral**.")
    st.stop()

with st.spinner(
    "Carregando dados detalhados... Se esta e a primeira busca de um candidato "
    f"da UF '{alvo.uf}' nesta sessao, o sistema baixa e converte a votacao "
    "oficial daquele estado agora (pode levar alguns minutos em estados "
    "grandes); buscas seguintes na mesma UF sao rapidas."
):
    if veio_do_fallback:
        candidatura, vc, vd, rd = _carregar_dados_candidatura(
            alvo.numero, alvo.codigo_municipio_tse, alvo.cargo, alvo.ano_eleicao, alvo.turno
        )
    else:
        candidatura, vc, vd, rd = _carregar_dados_candidatura_v2(
            ano, cargo, uf, municipio_codigo, turno, alvo.numero
        )

_escopo_atual = resolver_escopo(
    candidatura.ano_eleicao, candidatura.cargo, uf=candidatura.uf,
    municipio=(candidatura.municipio if candidatura.codigo_municipio_tse is not None else None),
    turno=candidatura.turno,
)
_eh_municipal = _escopo_atual.tipo_abrangencia == "MUNICIPAL"

rg = resultado_geral(candidatura, vd, rd)
ranking = ranking_disputa(vd, rd)
st.session_state.setdefault("nivel_territorial", "NR_ZONA")


def _geo():
    return _carregar_geografia(
        candidatura.numero, candidatura.codigo_municipio_tse, candidatura.cargo,
        candidatura.ano_eleicao, candidatura.turno, candidatura, vc,
    )


def _geo_secao():
    return _carregar_geografia_secao(
        candidatura.numero, candidatura.codigo_municipio_tse, candidatura.cargo,
        candidatura.ano_eleicao, candidatura.turno, candidatura, vc,
    )


def _demo(enriquecido_df: pd.DataFrame):
    return _carregar_demografia(
        candidatura.numero, candidatura.codigo_municipio_tse, candidatura.cargo,
        candidatura.ano_eleicao, candidatura.turno, enriquecido_df, vd,
    )


# ----------------------------------------------------------- Cabecalho fixo
st.markdown(
    f"""
<div class="candidato-header">
  <h1>{candidatura.nome_completo} ({candidatura.nome_urna})</h1>
  <div class="subtitulo">{candidatura.cargo} - {candidatura.municipio}/{candidatura.uf} -
  {candidatura.partido_sigla} ({candidatura.partido_nome}) -
  {candidatura.coligacao_federacao or "Partido isolado"}</div>
  {_badge(candidatura.resultado_final, _tom_resultado(candidatura.resultado_final))}
</div>
""",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------- Navegacao
_opcoes_secao = ["Visao Geral", "Concorrencia", "Territorio"]
if _eh_municipal:
    _opcoes_secao += ["Geografia", "Demografia", "Estatistica Avancada", "Abordagem de Maslow"]
else:
    _opcoes_secao += ["Indicadores Estaduais"]
_opcoes_secao += ["Relatorio"]
secao = st.sidebar.radio("Navegacao", _opcoes_secao)
if not _eh_municipal:
    st.sidebar.caption(
        "Piloto de cargo estadual: Geografia/Demografia/Estatistica Avancada/"
        "Maslow dependem da malha de setores censitarios de UM municipio e "
        "ficam fora deste piloto (seriam necessarios os ~645 municipios da "
        "UF de uma vez)."
    )

# ============================================================ Visao Geral
if secao == "Visao Geral":
    c1, c2, c3, c4 = st.columns(4)
    _kpi(c1, "Total de votos", _fmt(rg.total_votos))
    _kpi(c2, "Colocacao geral", f"{rg.colocacao_geral}o de {rg.total_concorrentes}")
    _kpi(c3, "% dos votos validos", f"{rg.pct_votos_validos}%")
    _kpi(c4, "Candidatos eleitos na disputa", str(rg.total_eleitos))

    c5, c6, c7, c8 = st.columns(4)
    _kpi(c5, "1o colocado", rg.nome_primeiro_colocado, f"{_fmt(rg.votos_primeiro_colocado)} votos")
    _kpi(c6, "Distancia p/ ultimo eleito", f"{_fmt(rg.distancia_para_ultimo_eleito)} votos",
         tom="ruim" if (rg.distancia_para_ultimo_eleito or 0) > 0 else "bom")
    _kpi(c7, "Votos do partido na disputa", _fmt(rg.votos_partido_total))
    _kpi(c8, "% do candidato no partido", f"{rg.pct_candidato_sobre_partido}%")

    with st.container(border=True):
        st.plotly_chart(charts.grafico_pizza_votos_validos(rg), use_container_width=True)

    perfil_economico = carregar_perfil_economico_municipio(candidatura)
    with st.container(border=True):
        st.subheader("Contexto economico do municipio (RAIS + CAGED)")
        _explicacao(
            "RAIS Estabelecimentos e CAGED tem granularidade de MUNICIPIO (nao de "
            "distrito/zona) - por isso aparecem aqui como contexto do municipio como um "
            "todo, nao como variavel comparada entre territorios (isso fica nas secoes "
            "Estatistica Avancada/Territorio, que usam dados do Censo por setor)."
        )
        if not perfil_economico.disponivel:
            st.info("Dados de RAIS/CAGED indisponiveis para este municipio.")
        else:
            ce1, ce2, ce3 = st.columns(3)
            _kpi(ce1, "Vinculos formais ativos (RAIS 2023)", _fmt(perfil_economico.vinculos_ativos_total))
            _kpi(ce2, "Estabelecimentos ativos (RAIS 2023)", _fmt(perfil_economico.estabelecimentos_ativos))
            _kpi(
                ce3, "Saldo de empregos formais (CAGED 2024)",
                f"{perfil_economico.saldo_caged_2024:+,}".replace(",", "."),
                tom={"crescimento": "bom", "retracao": "ruim"}.get(perfil_economico.tendencia, "neutro"),
            )
            st.plotly_chart(charts.grafico_perfil_economico_municipio(perfil_economico), use_container_width=True)

# ============================================================ Concorrencia
elif secao == "Concorrencia":
    with st.container(border=True):
        st.subheader("Ranking da disputa")
        st.plotly_chart(charts.grafico_ranking_disputa(ranking, candidatura.numero), use_container_width=True)
        st.dataframe(
            ranking[["colocacao", "nome_urna", "partido_sigla", "total_votos", "pct_votos_validos", "eleito", "resultado_final"]],
            use_container_width=True, height=300,
            column_config={"pct_votos_validos": st.column_config.ProgressColumn("% votos validos", min_value=0, max_value=float(ranking["pct_votos_validos"].max()))},
        )

    with st.container(border=True):
        st.subheader("Concorrentes diretos (mesma faixa de volume de votos)")
        diretos = concorrentes_diretos(candidatura, ranking, n=5)
        st.dataframe(diretos[["colocacao", "nome_urna", "partido_sigla", "total_votos", "e_o_candidato"]], use_container_width=True)

    with st.container(border=True):
        st.subheader("Os 3 maiores rivais (mesma base eleitoral)")
        _explicacao(
            "Diferente da lista acima (que so olha volume de votos), aqui o sistema calcula, "
            "para cada concorrente, a correlacao estatistica (Pearson) entre a distribuicao "
            "geografica dos seus votos e a do candidato-alvo. Correlacao alta = o rival "
            "tambem e forte exatamente onde o candidato-alvo e forte, ou seja, disputa a "
            "MESMA base eleitoral - independente do tamanho total da candidatura dele."
        )
        rivais_sim, issues_sim = rivais_por_similaridade_eleitorado(
            candidatura, vd, rd, st.session_state["nivel_territorial"], top_n=3
        )
        for issue in issues_sim:
            st.warning(issue.mensagem)
        if not rivais_sim.empty:
            st.plotly_chart(charts.grafico_rivais_similaridade(rivais_sim), use_container_width=True)
            st.dataframe(
                rivais_sim[["nome_urna", "partido_sigla", "correlacao_base_eleitoral", "total_votos_rival",
                            "delta_total_votos", "territorios_em_comum", "territorios_maior_sobreposicao"]],
                use_container_width=True,
            )

    with st.container(border=True):
        st.subheader("Ranking por partido")
        partidos = ranking_partidos(ranking, vd, rd)
        st.plotly_chart(charts.grafico_ranking_partidos(partidos), use_container_width=True)
        st.dataframe(
            partidos[["partido_sigla", "partido_nome", "votos_totais", "n_candidatos", "n_eleitos", "colocacao_partido"]],
            use_container_width=True,
        )

# ============================================================== Territorio
elif secao == "Territorio":
    if _eh_municipal:
        nivel_label = st.radio(
            "Nivel territorial", ["Zona eleitoral", "Secao eleitoral"], horizontal=True,
            index=0 if st.session_state["nivel_territorial"] == "NR_ZONA" else 1,
        )
        st.session_state["nivel_territorial"] = "NR_ZONA" if nivel_label == "Zona eleitoral" else "NR_SECAO_COMPOSTA"
        nivel = st.session_state["nivel_territorial"]
    else:
        st.caption(
            "Cargo estadual (piloto): nivel territorial fixo em Municipio "
            "(a UF inteira, nao zona/secao)."
        )
        nivel = "CD_MUNICIPIO"

    terr = desempenho_territorial(candidatura, vc, vd, rd, nivel)
    terr = enriquecer_com_comparecimento_abstencao(terr, candidatura, nivel)
    hhi = indice_concentracao_hhi(terr)
    terr_class = zonas_de_disputa(terr, vd, rd, candidatura, nivel)
    indice_terr = calcular_indice_performance(terr_class, hhi)

    c1, c2 = st.columns([1, 2])
    with c1, st.container(border=True):
        st.plotly_chart(charts.grafico_indice_concentracao(hhi), use_container_width=True)
    with c2, st.container(border=True):
        st.plotly_chart(charts.grafico_distribuicao_indice(indice_terr), use_container_width=True)

    with st.container(border=True):
        st.plotly_chart(charts.grafico_votos_por_territorio(terr, nivel), use_container_width=True)

    with st.container(border=True):
        st.plotly_chart(charts.grafico_zonas_disputa(terr_class, nivel), use_container_width=True)

    with st.container(border=True):
        st.subheader("Indice de performance territorial (0-100)")
        _explicacao(
            "Mede a forca RELATIVA do candidato entre os proprios territorios (nao dominio "
            "eleitoral absoluto): combina % de votos validos no territorio, desempenho vs. "
            "media do proprio candidato, participacao no total de votos, comparecimento e "
            "distancia para o concorrente principal - pesos ajustaveis em config/indicators.yaml."
        )
        st.dataframe(indice_terr, use_container_width=True, height=380)

    with st.container(border=True):
        st.subheader("Delta contra os principais rivais, territorio a territorio")
        _explicacao(
            "Para cada territorio, a diferenca (delta) entre os votos do candidato e os "
            "votos de cada um dos 3 maiores rivais por volume - mostra exatamente onde o "
            "candidato ganha e onde perde, e por quantos votos."
        )
        matriz = matriz_candidato_territorio(candidatura, vd, ranking, nivel, top_n_concorrentes=3)
        delta = delta_vs_rivais(matriz, nivel, candidatura.nome_urna)
        st.plotly_chart(charts.grafico_delta_rivais(delta, nivel), use_container_width=True)
        st.plotly_chart(charts.grafico_comparativo_concorrentes(matriz, nivel), use_container_width=True)

# ================================================= Indicadores Estaduais (V2)
elif secao == "Indicadores Estaduais":
    _explicacao(
        "Indicadores de dispersao geografica do voto entre os municipios da "
        f"UF {candidatura.uf} inteira - complementam (nao substituem) o "
        "Territorio acima. Piloto: Governador 2022/SP - ver limitacoes "
        "metodologicas em config/indicators.yaml: indice_capilaridade."
    )
    terr_mun = desempenho_territorial(candidatura, vc, vd, rd, "CD_MUNICIPIO")
    terr_mun = terr_mun.merge(
        vd[["CD_MUNICIPIO", "NM_MUNICIPIO"]].drop_duplicates(), on="CD_MUNICIPIO", how="left"
    )
    presenca = calcular_presenca_eleitoral(terr_mun, vd)
    concentracao = calcular_concentracao_territorial(terr_mun)
    indice_capilaridade, classif_capilaridade = calcular_indice_capilaridade(presenca, concentracao)

    c1, c2, c3, c4 = st.columns(4)
    _kpi(c1, "Cobertura municipal", f"{presenca.pct_cobertura}%",
         f"{presenca.n_municipios_com_votos}/{presenca.n_municipios_universo} municipios")
    _kpi(c2, "Indice de capilaridade", f"{indice_capilaridade}/100", classif_capilaridade)
    _kpi(c3, "Concentracao (HHI)", f"{concentracao.hhi:.4f}")
    _kpi(c4, "Gini territorial", f"{concentracao.gini:.4f}")

    with st.container(border=True):
        st.subheader("Presenca eleitoral")
        c5, c6, c7 = st.columns(3)
        _kpi(c5, "Maior votacao absoluta", presenca.municipio_maior_votacao_absoluta,
             f"{_fmt(presenca.votos_municipio_maior_votacao_absoluta)} votos")
        _kpi(c6, "Participacao dos 5 maiores", f"{presenca.participacao_top5_pct}%")
        _kpi(c7, "Participacao dos 10/20 maiores",
             f"{presenca.participacao_top10_pct}% / {presenca.participacao_top20_pct}%")
        if presenca.municipios_sem_votos:
            st.caption(
                f"{len(presenca.municipios_sem_votos)} municipio(s) sem nenhum voto "
                f"registrado nesta disputa: {', '.join(presenca.municipios_sem_votos[:15])}"
                + (" ..." if len(presenca.municipios_sem_votos) > 15 else "")
            )

    with st.container(border=True):
        st.subheader("Concentracao territorial")
        c8, c9 = st.columns(2)
        _kpi(c8, "Dependencia do maior municipio", f"{concentracao.dependencia_maior_municipio_pct}%")
        _kpi(c9, "Dependencia dos 5/10 maiores",
             f"{concentracao.dependencia_top5_pct}% / {concentracao.dependencia_top10_pct}%")
        st.plotly_chart(charts.grafico_curva_lorenz(concentracao.curva_lorenz), use_container_width=True)

    with st.container(border=True):
        st.subheader(f"Ranking de municipios ({candidatura.uf})")
        st.dataframe(
            terr_mun[["NM_MUNICIPIO", "votos_candidato", "pct_votos_validos_territorio", "colocacao"]]
            .sort_values("votos_candidato", ascending=False),
            use_container_width=True, height=400,
        )

# =============================================================== Geografia
elif secao == "Geografia":
    if not uf_tem_malha_completa(candidatura.uf):
        st.info(f"Malha geografica nao configurada para a UF '{candidatura.uf}'.")
    else:
        with st.spinner("Localizando locais de votacao e cruzando com setores/bairros (IBGE)..."):
            pontos, enriquecido, avisos_geo = _geo()

        for aviso in avisos_geo:
            st.warning(aviso)

        bairros_agg = agregar_votos_por_bairro(enriquecido)
        with st.container(border=True):
            st.plotly_chart(charts.grafico_votos_por_bairro(bairros_agg), use_container_width=True)

        with st.container(border=True):
            st.subheader("Mapa de locais de votacao")
            mapa_pontos = maps.mapa_locais_votacao(enriquecido, candidatura.nome_urna)
            st_folium(mapa_pontos, width=None, height=500, key="mapa_pontos")

        with st.container(border=True):
            # Prefere bairro oficial do IBGE (mais granular) - so cai para
            # distrito (setor censitario) quando a UF/municipio nao tem malha
            # de bairro publicada pelo IBGE (ex.: capital de SP, Tocantins,
            # Goiania). O mapa coropletico precisa de POLIGONO real - o
            # bairro pode ter sido preenchido via CEP (ViaCEP, sem
            # poligono associado - ver geographic_analysis.py), entao a
            # escolha aqui depende de a malha de bairro EXISTIR
            # (carregar_malha != None), nao apenas de NM_BAIRRO_IBGE ter
            # algum valor preenchido.
            malha_bairros = carregar_malha("bairros", candidatura.municipio, candidatura.uf)
            if malha_bairros is not None:
                st.subheader("Mapa coropletico por bairro")
                malha_gdf = malha_bairros
                coluna_nivel, coluna_malha = "NM_BAIRRO_IBGE", "NM_BAIRRO"
            else:
                st.subheader("Mapa coropletico por distrito (malha de bairro sem poligonos para esta UF/municipio)")
                malha_gdf = carregar_malha("setores", candidatura.municipio, candidatura.uf)
                coluna_nivel, coluna_malha = "NM_DIST", "NM_DIST"

            if coluna_nivel in enriquecido.columns and enriquecido[coluna_nivel].notna().any() and malha_gdf is not None:
                territorios_gdf = malha_gdf.dissolve(by=coluna_malha, as_index=False)
                votos_territorio = enriquecido.groupby(coluna_nivel, as_index=False)["votos_candidato"].sum()
                mapa_choro = maps.mapa_choropleth_territorio(
                    territorios_gdf, votos_territorio, coluna_malha, coluna_nivel, "votos_candidato", candidatura.nome_urna
                )
                st_folium(mapa_choro, width=None, height=500, key="mapa_choro")
            else:
                st.info("Malha de bairro/distrito indisponivel para o mapa coropletico.")

        with st.container(border=True):
            st.subheader("Diagrama de Voronoi (area de influencia por local de votacao)")
            fronteira = carregar_fronteira_municipio(candidatura)
            if fronteira is not None:
                voronoi = gerar_voronoi(pontos, fronteira)
                if voronoi is not None:
                    mapa_voronoi = maps.mapa_voronoi(voronoi)
                    st_folium(mapa_voronoi, width=None, height=500, key="mapa_voronoi")
                else:
                    st.info("Numero insuficiente de locais com coordenada unica para gerar o Voronoi.")

# =============================================================== Demografia
elif secao == "Demografia":
    if not uf_tem_malha_completa(candidatura.uf):
        st.info(f"Malha geografica nao configurada para a UF '{candidatura.uf}'.")
    else:
        with st.spinner("Cruzando com o Censo 2022 (IBGE)..."):
            _, enriquecido_secao, _ = _geo_secao()
            perfil_setor, base_territorio = _demo(enriquecido_secao)

        if base_territorio.empty:
            st.info("Nao foi possivel montar o perfil demografico por territorio.")
        else:
            _explicacao(
                "Perfil demografico por secao eleitoral, a partir do setor censitario onde o "
                "local de votacao correspondente fica fisicamente localizado (fonte: Censo "
                "Demografico 2022, IBGE). Secoes do mesmo local de votacao compartilham o "
                "mesmo perfil (mesma coordenada) - variam apenas nos votos do candidato."
            )
            with st.container(border=True):
                st.dataframe(
                    base_territorio, use_container_width=True, height=400,
                    column_config={
                        "renda_media_responsavel": st.column_config.NumberColumn("Renda media (R$)", format="R$ %.2f"),
                        "pct_votos_validos_territorio": st.column_config.ProgressColumn(
                            "% votos validos", min_value=0,
                            max_value=float(base_territorio["pct_votos_validos_territorio"].max()),
                        ),
                    },
                )
            st.download_button(
                "Baixar perfil por setor (CSV)",
                perfil_setor.to_csv(index=False).encode("utf-8"),
                file_name="perfil_demografico_por_setor.csv",
            )

# ======================================================= Estatistica Avancada
elif secao == "Estatistica Avancada":
    if not uf_tem_malha_completa(candidatura.uf):
        st.info(f"Malha geografica nao configurada para a UF '{candidatura.uf}'.")
    else:
        with st.spinner("Calculando correlacoes, regressoes e clusterizacao..."):
            _, enriquecido_secao, _ = _geo_secao()
            perfil_setor, base_territorio = _demo(enriquecido_secao)

        if base_territorio.empty:
            st.info("Dados insuficientes para analise estatistica territorial.")
        else:
            variaveis_disp = [v for v in VARIAVEIS_DEMOGRAFICAS if v in base_territorio.columns]

            with st.container(border=True):
                st.subheader("Correlacao com o desempenho eleitoral")
                corr, issues_corr = correlacoes_com_votos(base_territorio, "votos_candidato", variaveis_disp)
                for issue in issues_corr:
                    st.warning(issue.mensagem)
                if not corr.empty:
                    st.plotly_chart(charts.grafico_correlacoes(corr), use_container_width=True)
                    st.dataframe(corr, use_container_width=True)
                    var_destaque = corr.iloc[0]["variavel"]
                    st.plotly_chart(
                        charts.grafico_dispersao_correlacao(base_territorio, "votos_candidato", var_destaque),
                        use_container_width=True,
                    )

            with st.container(border=True):
                st.subheader("Regressao linear (votos por territorio)")
                reg, issues_reg = regressao_linear_votos(
                    base_territorio, "votos_candidato", variaveis_disp,
                    coluna_cluster=_COLUNA_CLUSTER_REGRESSAO,
                )
                for issue in issues_reg:
                    st.warning(issue.mensagem)
                if reg:
                    st.write(f"R2 = {reg.r_quadrado}  |  R2 ajustado = {reg.r_quadrado_ajustado}  |  n = {reg.n_observacoes}")
                    st.dataframe(reg.coeficientes, use_container_width=True)
                    st.caption(reg.limitacoes)

            modelo_log = None
            with st.container(border=True):
                st.subheader("Regressao logistica: o que explica uma 'boa votacao'?")
                _explicacao(
                    "Classifica cada territorio como 'boa votacao' (1) se o candidato teve "
                    "percentual de votos validos ali acima da sua PROPRIA mediana entre os "
                    "territorios onde concorreu, ou 'fraca' (0) caso contrario - e mede que "
                    "caracteristicas demograficas aumentam ou diminuem essa chance (odds ratio)."
                )
                modelo_log, issues_log = regressao_logistica_bom_desempenho(
                    base_territorio, "pct_votos_validos_territorio", variaveis_disp,
                    coluna_cluster=_COLUNA_CLUSTER_REGRESSAO,
                )
                for issue in issues_log:
                    st.warning(issue.mensagem)
                if modelo_log:
                    c1, c2, c3, c4 = st.columns(4)
                    _kpi(c1, "Limiar 'boa votacao'", f"{modelo_log.limiar_usado}%")
                    _kpi(c2, "Pseudo-R2 (McFadden)", str(modelo_log.pseudo_r2_mcfadden))
                    _kpi(c3, "Acuracia (na amostra)", f"{modelo_log.acuracia*100:.0f}%")
                    _kpi(c4, "Secoes (boa/fraca votacao)", f"{modelo_log.n_positivos}/{modelo_log.n_negativos}")
                    st.dataframe(modelo_log.coeficientes, use_container_width=True)
                    st.write("**Matriz de confusao** (linhas=real, colunas=previsto)")
                    st.dataframe(modelo_log.matriz_confusao, use_container_width=True)
                    for texto in modelo_log.interpretacoes:
                        st.markdown(f"- {texto}")
                    st.caption(modelo_log.limitacoes)

            resultado_clustering = None
            with st.container(border=True):
                st.subheader(f"Segmentacao de territorios (k={K_CLUSTERS})")
                _explicacao(
                    "Agrupa os territorios por semelhanca demografica em 10 perfis. Serve "
                    "para decidir ONDE investir recurso de campanha (canvassing, anuncios "
                    "segmentados, agenda de visitas): clusters de 'Fortaleza' sao a base "
                    "solida a manter mobilizada; clusters de 'Alto potencial' tem perfil "
                    "parecido com a fortaleza do candidato mas ainda votam pouco nele - sao "
                    "o alvo prioritario de expansao; clusters de 'Baixa prioridade' tem "
                    "perfil distante da base do candidato e retorno de investimento menor."
                )
                resultado_clustering, issues_clust = segmentar_territorios(base_territorio, variaveis_disp, k=K_CLUSTERS)
                for issue in issues_clust:
                    st.warning(issue.mensagem)
                if resultado_clustering:
                    st.write(f"k = {resultado_clustering.k_escolhido}  |  indice de silhueta = {resultado_clustering.silhouette}")
                    narrativa = gerar_narrativa_clusters(resultado_clustering, "votos_candidato")
                    for _, linha in narrativa.iterrows():
                        badge_html = _badge(linha["rotulo_acao"], _tom_rotulo_acao(linha["rotulo_acao"]))
                        st.markdown(
                            f'<div class="cluster-card"><div class="titulo">'
                            f'{badge_html} Cluster {linha["cluster"]}</div>{linha["resumo"]}</div>',
                            unsafe_allow_html=True,
                        )
                    if len(variaveis_disp) >= 2:
                        st.plotly_chart(
                            charts.grafico_clusters(
                                resultado_clustering.territorios_com_cluster, variaveis_disp[0], variaveis_disp[1],
                                _NIVEL_TERRITORIO_DEMOGRAFICO,
                            ),
                            use_container_width=True,
                        )
                    st.plotly_chart(
                        charts.grafico_perfil_clusters(resultado_clustering.perfil_clusters, variaveis_disp),
                        use_container_width=True,
                    )
                    st.dataframe(resultado_clustering.perfil_clusters, use_container_width=True)

            with st.container(border=True):
                st.subheader("Secoes eleitorais com maior potencial de crescimento")
                _explicacao(
                    "Combina o quanto o territorio esta abaixo da media de territorios com "
                    "perfil demografico parecido (mesmo cluster) com a probabilidade prevista "
                    "pela regressao logistica de boa votacao ali - aponta onde o candidato "
                    "tem terreno demografico favoravel mas ainda nao converteu isso em votos."
                )
                if resultado_clustering:
                    potencial = identificar_bairros_potencial(
                        resultado_clustering, modelo_log, _NIVEL_TERRITORIO_DEMOGRAFICO, "votos_candidato",
                    )
                    if not potencial.empty:
                        st.plotly_chart(
                            charts.grafico_bairros_potencial(potencial, _NIVEL_TERRITORIO_DEMOGRAFICO),
                            use_container_width=True,
                        )
                        st.dataframe(potencial, use_container_width=True)
                    else:
                        st.info("Nenhum territorio abaixo da media do proprio cluster foi encontrado.")
                else:
                    st.info("Segmentacao de clusters indisponivel - potencial nao calculado.")

# ===================================================== Abordagem de Maslow
elif secao == "Abordagem de Maslow":
    if not uf_tem_malha_completa(candidatura.uf):
        st.info(f"Malha geografica nao configurada para a UF '{candidatura.uf}'.")
    else:
        with st.spinner("Recalculando modelos estatisticos para aplicar a lente de Maslow..."):
            _, enriquecido_secao, _ = _geo_secao()
            perfil_setor, base_territorio = _demo(enriquecido_secao)

        if base_territorio.empty:
            st.info("Dados insuficientes para aplicar a abordagem de Maslow.")
        else:
            variaveis_disp = [v for v in VARIAVEIS_DEMOGRAFICAS if v in base_territorio.columns]

            st.warning(
                "Esta secao NAO mede psicologia do eleitorado. Ela reinterpreta, como lente "
                "teorica, os coeficientes/odds ratios ja calculados por modelos estatisticos "
                "reais (secao 'Estatistica Avancada'), usando proxies socioeconomicos "
                "consagrados na literatura de ciencias sociais. Nenhum numero psicologico e "
                "medido ou estimado - niveis sem proxy defensavel nos dados aparecem como "
                "lacuna explicita, nao sao preenchidos artificialmente."
            )

            modelo_log_m, issues_log_m = regressao_logistica_bom_desempenho(
                base_territorio, "pct_votos_validos_territorio", variaveis_disp,
                coluna_cluster=_COLUNA_CLUSTER_REGRESSAO,
            )
            for issue in issues_log_m:
                st.warning(issue.mensagem)

            modelo_lin_m, corr_m = None, None
            if modelo_log_m is None:
                modelo_lin_m, issues_lin_m = regressao_linear_votos(
                    base_territorio, "votos_candidato", variaveis_disp,
                    coluna_cluster=_COLUNA_CLUSTER_REGRESSAO,
                )
                for issue in issues_lin_m:
                    st.warning(issue.mensagem)
                if modelo_lin_m is None:
                    corr_m, issues_corr_m = correlacoes_com_votos(base_territorio, "votos_candidato", variaveis_disp)
                    for issue in issues_corr_m:
                        st.warning(issue.mensagem)

            resultado_maslow = gerar_analise_maslow(modelo_log_m, modelo_lin_m, corr_m)
            st.caption(resultado_maslow.disclaimer)

            mapeadas = resultado_maslow.tiers_mapeados.query("status == 'mapeado'") if not resultado_maslow.tiers_mapeados.empty else resultado_maslow.tiers_mapeados
            with st.container(border=True):
                st.subheader("Niveis da piramide com proxy mapeado")
                if not mapeadas.empty:
                    st.plotly_chart(
                        charts.grafico_piramide_maslow(
                            resultado_maslow.tiers_mapeados, resultado_maslow.tiers_sem_proxy,
                            resultado_maslow.ordem_tiers,
                        ),
                        use_container_width=True,
                    )
                    st.dataframe(mapeadas, use_container_width=True)
                    for frase in resultado_maslow.narrativa:
                        st.markdown(f"- {frase}")
                else:
                    st.info("Nenhum modelo estatistico disponivel para aplicar a lente de Maslow nesta candidatura.")
                    for frase in resultado_maslow.narrativa:
                        st.markdown(f"- {frase}")

            with st.container(border=True):
                st.subheader("Niveis sem proxy disponivel nos dados atuais")
                st.dataframe(resultado_maslow.tiers_sem_proxy, use_container_width=True)

            if not resultado_maslow.variaveis_pendentes.empty:
                with st.container(border=True):
                    st.subheader("Variaveis com mapeamento pendente de decisao do cliente")
                    st.dataframe(resultado_maslow.variaveis_pendentes, use_container_width=True)

            with st.container(border=True):
                st.subheader("Variaveis demograficas sem correspondencia teorica direta")
                st.dataframe(resultado_maslow.variaveis_sem_correspondencia, use_container_width=True)

# ================================================================ Relatorio
elif secao == "Relatorio" and not _eh_municipal:
    st.info(
        "Relatorio executivo (HTML/PDF/Excel) disponivel apenas para cargos "
        "municipais nesta versao piloto - os indicadores estaduais podem ser "
        "conferidos na aba 'Indicadores Estaduais'."
    )

elif secao == "Relatorio":
    st.write("Gere o relatorio executivo ou exporte os dados desta candidatura.")
    nivel_relatorio = st.session_state.get("nivel_territorial", "NR_ZONA")
    perfil_economico_rel = carregar_perfil_economico_municipio(candidatura)

    limitacoes: list[str] = []
    bairros_agg_rel = None
    corr_rel = None
    modelo_log_rel = None
    narrativa_rel = None
    potencial_rel = None
    rivais_sim_rel = None
    delta_rel = None
    resultado_maslow_rel = None

    if uf_tem_malha_completa(candidatura.uf):
        pontos, enriquecido, avisos_geo = _geo()
        limitacoes = list(avisos_geo)
        bairros_agg_rel = agregar_votos_por_bairro(enriquecido)
        _, enriquecido_secao_rel, _ = _geo_secao()
        _, base_territorio_rel = _demo(enriquecido_secao_rel)
        if not base_territorio_rel.empty:
            variaveis_disp = [v for v in VARIAVEIS_DEMOGRAFICAS if v in base_territorio_rel.columns]
            corr_rel, _ = correlacoes_com_votos(base_territorio_rel, "votos_candidato", variaveis_disp)
            modelo_log_rel, _ = regressao_logistica_bom_desempenho(
                base_territorio_rel, "pct_votos_validos_territorio", variaveis_disp,
                coluna_cluster=_COLUNA_CLUSTER_REGRESSAO,
            )
            resultado_clustering_rel, _ = segmentar_territorios(base_territorio_rel, variaveis_disp, k=K_CLUSTERS)
            if resultado_clustering_rel:
                narrativa_rel = gerar_narrativa_clusters(resultado_clustering_rel, "votos_candidato")
                potencial_rel = identificar_bairros_potencial(
                    resultado_clustering_rel, modelo_log_rel, _NIVEL_TERRITORIO_DEMOGRAFICO, "votos_candidato",
                )
            modelo_lin_rel = None
            if modelo_log_rel is None:
                modelo_lin_rel, _ = regressao_linear_votos(
                    base_territorio_rel, "votos_candidato", variaveis_disp,
                    coluna_cluster=_COLUNA_CLUSTER_REGRESSAO,
                )
            resultado_maslow_rel = gerar_analise_maslow(modelo_log_rel, modelo_lin_rel, corr_rel)
    else:
        limitacoes = [f"Malha geografica nao configurada para a UF '{candidatura.uf}'."]

    rivais_sim_rel, _ = rivais_por_similaridade_eleitorado(candidatura, vd, rd, nivel_relatorio, top_n=3)

    terr_rel = desempenho_territorial(candidatura, vc, vd, rd, nivel_relatorio)
    hhi_rel = indice_concentracao_hhi(terr_rel)
    terr_class_rel = zonas_de_disputa(terr_rel, vd, rd, candidatura, nivel_relatorio)
    indice_terr_rel = calcular_indice_performance(terr_class_rel, hhi_rel)
    matriz_rel = matriz_candidato_territorio(candidatura, vd, ranking, nivel_relatorio, top_n_concorrentes=3)
    delta_rel = delta_vs_rivais(matriz_rel, nivel_relatorio, candidatura.nome_urna)

    figuras = {
        "Ranking da disputa": charts.grafico_ranking_disputa(ranking, candidatura.numero),
        f"Votos por {nivel_relatorio}": charts.grafico_votos_por_territorio(terr_rel, nivel_relatorio),
    }
    if not rivais_sim_rel.empty:
        figuras["Rivais por similaridade de base eleitoral"] = charts.grafico_rivais_similaridade(rivais_sim_rel)
    if potencial_rel is not None and not potencial_rel.empty:
        figuras["Territorios com maior potencial"] = charts.grafico_bairros_potencial(potencial_rel, _NIVEL_TERRITORIO_DEMOGRAFICO)
    if (
        resultado_maslow_rel is not None
        and not resultado_maslow_rel.tiers_mapeados.empty
        and not resultado_maslow_rel.tiers_mapeados.query("status == 'mapeado'").empty
    ):
        figuras["Piramide de Maslow"] = charts.grafico_piramide_maslow(
            resultado_maslow_rel.tiers_mapeados, resultado_maslow_rel.tiers_sem_proxy,
            resultado_maslow_rel.ordem_tiers,
        )
    if perfil_economico_rel.disponivel:
        figuras["Perfil economico do municipio (RAIS/CAGED)"] = charts.grafico_perfil_economico_municipio(perfil_economico_rel)

    dados_relatorio = DadosRelatorio(
        candidatura=candidatura, resultado_geral=rg, ranking=ranking,
        territorial_indice=indice_terr_rel, bairros_agg=bairros_agg_rel, correlacoes=corr_rel,
        limitacoes=limitacoes, figuras=figuras,
        regressao_logistica=modelo_log_rel, clusters_narrativa=narrativa_rel,
        delta_rivais=delta_rel, bairros_potencial=potencial_rel, rivais_similaridade=rivais_sim_rel,
        maslow=resultado_maslow_rel, perfil_economico=perfil_economico_rel,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        html_bytes = gerar_relatorio_html(dados_relatorio).encode("utf-8")
        st.download_button("Baixar relatorio HTML", html_bytes, file_name=f"relatorio_{candidatura.nome_urna}.html")
    with col2:
        pdf_path = resolve_path(f"outputs/reports/relatorio_{candidatura.numero}_{candidatura.codigo_municipio_tse}.pdf")
        gerar_relatorio_pdf(dados_relatorio, pdf_path)
        st.download_button("Baixar relatorio PDF", pdf_path.read_bytes(), file_name=pdf_path.name)
    with col3:
        planilhas = {
            "Resumo": pd.DataFrame([vars(rg)]),
            "Ranking": ranking,
            "Territorio": indice_terr_rel,
            "Rivais_Similaridade": rivais_sim_rel,
            "Delta_Territorio": delta_rel,
        }
        if bairros_agg_rel is not None:
            planilhas["Bairros"] = bairros_agg_rel
        if narrativa_rel is not None:
            planilhas["Clusters_k10"] = narrativa_rel
        if potencial_rel is not None:
            planilhas["Bairros_Potencial"] = potencial_rel
        if modelo_log_rel is not None:
            planilhas["Regressao_Logistica"] = modelo_log_rel.coeficientes
        if perfil_economico_rel.disponivel:
            planilhas["Perfil_Economico_Municipio"] = pd.DataFrame([vars(perfil_economico_rel)])
        if resultado_maslow_rel is not None and resultado_maslow_rel.fonte_efeito != "indisponivel":
            planilhas["Maslow_Tiers"] = resultado_maslow_rel.tiers_mapeados
            planilhas["Maslow_Sem_Proxy"] = resultado_maslow_rel.tiers_sem_proxy
        xlsx_path = resolve_path(f"outputs/reports/dados_{candidatura.numero}_{candidatura.codigo_municipio_tse}.xlsx")
        exportar_excel(xlsx_path, planilhas)
        st.download_button("Baixar dados (Excel)", xlsx_path.read_bytes(), file_name=xlsx_path.name)
