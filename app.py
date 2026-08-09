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
from src.proportional_analysis import ranking_federacoes, resumo_proporcional
from src.turno_comparison import comparar_turnos
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
    perfil_comparativo_dois_candidatos,
    ranking_disputa,
    ranking_partidos,
    rivais_por_similaridade_eleitorado,
    zonas_de_disputa,
)
from src.correlation_analysis import correlacoes_com_votos
from src.demographic_analysis import (
    agregados_populacionais_municipio,
    perfil_demografico_do_territorio,
    perfil_demografico_por_setor,
)
from src.candidate_assets import carregar_patrimonio_candidato, patrimonio_comparativo
from src.economic_analysis import carregar_perfil_economico_municipio
from src.electorate_profile import (
    LIMITACAO_VINTAGE,
    carregar_perfil_eleitorado_secao,
    comparar_eleitorado_vs_votos_candidato,
    perfil_eleitorado_por_territorio,
)
from src.electoral_metrics import (
    desempenho_territorial,
    enriquecer_com_comparecimento_abstencao,
    indice_concentracao_hhi,
    indice_participacao_territorial,
    resultado_geral,
)
from src.excel_exporter import exportar_excel
from src.geographic_analysis import (
    agregar_votos_por_bairro,
    atribuir_setor_e_bairro,
    atribuir_setor_e_bairro_uf,
    carregar_coordenadas_locais,
    carregar_coordenadas_uf,
    carregar_fronteira_municipio,
    carregar_malha,
    carregar_malha_municipios_uf,
    juntar_votos_com_coordenadas,
    juntar_votos_com_coordenadas_secao,
    normalizar_nome_municipio,
    total_votos_validos_por_territorio,
    uf_tem_malha_completa,
)
from src.maslow_analysis import gerar_analise_maslow
from src.potential_analysis import identificar_bairros_potencial
from src.projections.monte_carlo import cenario_agregado_votos, simular_regressao_linear
from src.candidate_history import montar_comparativo_historico
from src.reports.relatorio_completo import gerar_relatorio_completo_html
from src.reports.relatorio_comparativo import gerar_relatorio_comparativo_html, gerar_relatorio_comparativo_pdf
from src.reports.relatorio_estrategia import gerar_relatorio_estrategia_html, gerar_relatorio_estrategia_pdf
from src.potential_index import calcular_indice_performance
from src.regression_models import regressao_linear_votos, regressao_logistica_bom_desempenho
from src.report_generator import DadosRelatorio, gerar_relatorio_html, gerar_relatorio_pdf
from src.utils import indicators_config, resolve_path
from src.vote_filtering import secao_composta, zona_uf_composta
from src.voronoi_analysis import gerar_voronoi
import src.charts as charts
import src.maps as maps

# Modulo Candidato (Modo 1 da expansao SIET) - questionario de
# autoavaliacao, independente de qualquer candidatura real do TSE. Ver
# ETAPA1_ARQUITETURA.md.
from src.indicators.candidate_indices import calcular_indices_candidato
from src.indicators.candidate_performance_indices import calcular_indices_desempenho_real
from src.profiles.candidate_archetype import classificar_arquetipo
from src.questionnaire.candidate_questionnaire import (
    BaseEleitoral,
    Comunicacao,
    IdentificacaoAnalise,
    NivelIntensidade,
    Posicionamento,
    Recursos,
    RespostaQuestionario,
    SimNao,
    Trajetoria,
)

# Rivais projetados + compatibilidade partidaria (secoes 17/22, dentro do
# Modulo Candidato) - DIFERENTE do resto do modulo: usa dado real do TSE da
# disputa comparavel mais recente, nunca autoavaliacao. Ver
# src/rivals/hypothetical_rivals.py e src/parties/party_compatibility.py.
from src.parties.party_compatibility import avaliar_compatibilidade_partidaria
from src.rivals.hypothetical_rivals import identificar_rivais_projetados

# Modulo de Pautas/Plataforma (Modo 3 da expansao SIET) - questionario de
# pauta de politica publica, independente de qualquer candidatura real do
# TSE. Ver ETAPA1_ARQUITETURA.md.
from src.indicators.policy_indices import calcular_indices_pauta
from src.platforms.platform_builder import montar_plataforma, verificar_gate_competencia
from src.profiles.policy_classification import classificar_pauta
from src.questionnaire.policy_questionnaire import PropostaPauta, pautas_disponiveis, policy_areas_config

# Matriz Candidato x Territorio x Pauta (Modo 4 - Integracao, secao 15).
# Cruza a saida ja calculada dos Modos 1 e 3 com o perfil territorial REAL
# (Censo IBGE/RAIS-CAGED) do municipio informado. Ver
# src/integration/candidate_territory_policy_matrix.py.
from src.integration.candidate_territory_policy_matrix import montar_matriz_candidato_territorio_pauta

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


# --------------------------------------------------------- Modulo Candidato
_CARGOS_MODO1 = [
    "Vereador", "Prefeito", "Deputado Estadual", "Deputado Distrital",
    "Deputado Federal", "Senador", "Governador", "Presidente",
]
_OPCOES_NIVEL = {
    "-- nao respondido --": None,
    "Nenhuma": NivelIntensidade.NENHUMA,
    "Baixa": NivelIntensidade.BAIXA,
    "Moderada": NivelIntensidade.MODERADA,
    "Alta": NivelIntensidade.ALTA,
    "Muito alta": NivelIntensidade.MUITO_ALTA,
}
_OPCOES_SIMNAO = {"-- nao respondido --": None, "Sim": SimNao.SIM, "Nao": SimNao.NAO}


def _nivel(label: str, key: str):
    return _OPCOES_NIVEL[st.selectbox(label, list(_OPCOES_NIVEL.keys()), key=key)]


def _simnao(label: str, key: str):
    return _OPCOES_SIMNAO[st.selectbox(label, list(_OPCOES_SIMNAO.keys()), key=key)]


def _tom_indice(valor: float, pior_quando_alto: bool) -> str:
    v = 100 - valor if pior_quando_alto else valor
    if v >= 60:
        return "bom"
    if v >= 40:
        return "neutro"
    return "ruim"


# `classificacao` (critico/baixo/moderado/alto/muito_alto) e sempre a faixa
# de MAGNITUDE bruta (mesma tabela de limites de config/weights.yaml para
# todo indice, ver src/indicators/candidate_indices.py) - correto para
# testes e para os 18 indices normais, mas enganoso na tela para os 2
# indices "pior_quando_alto" (risco_reputacional, rejeicao_potencial):
# nota 0 nesses dois e a MELHOR situacao possivel, mas apareceria rotulada
# "critico" se mostrada sem traducao. Este dict so existe para exibicao -
# nao altera o dado armazenado em ResultadoIndice.classificacao.
_ROTULOS_INDICE_INVERTIDO = {
    "critico": "risco minimo",
    "baixo": "risco baixo",
    "moderado": "risco moderado",
    "alto": "risco alto",
    "muito_alto": "risco critico",
}


def _rotulo_classificacao(r) -> str:
    if r.pior_quando_alto:
        return _ROTULOS_INDICE_INVERTIDO.get(r.classificacao, r.classificacao)
    return r.classificacao


def _pagina_questionario_candidato() -> None:
    """Modo 1 (Candidato) - questionario de autoavaliacao (secao 8 do
    briefing de expansao SIET). NAO depende de nenhuma candidatura real do
    TSE - roda 100% a partir das respostas deste formulario. Ver
    ETAPA1_ARQUITETURA.md e src/questionnaire/candidate_questionnaire.py."""
    st.title("Questionario do Candidato")
    _explicacao(
        "Autoavaliacao estruturada - <strong>nao e dado eleitoral verificado</strong>, "
        "diferente do resto do SIET (calculado a partir de TSE/IBGE reais). Responda o "
        "quanto conseguir: perguntas deixadas em \"-- nao respondido --\" ficam de fora "
        "do calculo de cada indice, e a cobertura de cada um aparece junto ao resultado - "
        "nunca e preenchida com estimativa."
    )

    with st.form("form_questionario_candidato"):
        st.subheader("1. Identificacao da analise")
        c1, c2, c3 = st.columns(3)
        cargo_pretendido = c1.selectbox("Cargo pretendido", _CARGOS_MODO1, key="q_cargo")
        uf = c2.selectbox("UF", list(UF_NOME.keys()), key="q_uf")
        municipio_base = c3.text_input("Municipio-base", key="q_municipio")
        c4, c5, c6 = st.columns(3)
        with c4:
            partido_definido = _simnao("Partido definido?", "q_partido_definido")
        with c5:
            ja_disputou = _simnao("Ja disputou eleicao antes?", "q_ja_disputou")
        with c6:
            partido_sigla = st.text_input(
                "Sigla do partido (se definido)", key="q_partido_sigla",
                help="Usado para os rivais projetados e a compatibilidade partidaria abaixo - "
                     "so preenche se 'Partido definido?' for Sim.",
            )
        c7, c8 = st.columns(2)
        with c7:
            possui_padrinho = _simnao("Possui padrinho politico?", "q_possui_padrinho")
        with c8:
            nome_padrinho = st.text_input(
                "Nome do padrinho politico (se houver)", key="q_nome_padrinho",
                help="So preenche se 'Possui padrinho politico?' for Sim. Usado na estrategia e "
                     "nos relatorios deste candidato - vinculo de apadrinhamento e fonte real de "
                     "apoio, mas tambem risco de associacao (desgaste do padrinho reflete no afilhado).",
            )

        with st.expander("2. Trajetoria"):
            tempo_atuacao_publica = _nivel("Tempo de atuacao publica", "q_tempo_atuacao")
            mandato_anterior = _simnao("Teve mandato anterior?", "q_mandato_anterior")
            experiencia_politica_geral = _nivel("Experiencia politica geral", "q_exp_politica")
            atuacao_administrativa = _nivel("Atuacao administrativa (gestao)", "q_atuacao_adm")
            projetos_realizados = _nivel("Projetos realizados", "q_projetos")
            resultados_concretos = _nivel("Resultados concretos entregues", "q_resultados")

        with st.expander("3. Base eleitoral"):
            numero_territorios = st.number_input(
                "Numero de bairros/cidades onde tem presenca organizada", min_value=0, max_value=200, step=1,
                key="q_num_territorios",
            )
            estrutura_bairros = _nivel("Estrutura nos bairros/cidades de presenca", "q_estrutura_bairros")
            apoiadores_mobilizaveis = _nivel("Apoiadores mobilizaveis", "q_apoiadores")
            capacidade_eventos = _nivel("Capacidade de realizar eventos", "q_eventos")
            relacionamento_liderancas = _nivel("Relacionamento com liderancas comunitarias", "q_rel_liderancas")
            relacionamento_vereadores = _nivel("Relacionamento com vereadores", "q_rel_vereadores")
            relacionamento_prefeitos = _nivel("Relacionamento com prefeitos", "q_rel_prefeitos")
            relacionamento_deputados = _nivel("Relacionamento com deputados", "q_rel_deputados")
            relacionamento_entidades = _nivel("Relacionamento com entidades/associacoes", "q_rel_entidades")
            liderancas_regionais = _nivel("Relacionamento com liderancas regionais", "q_liderancas_regionais")
            apoio_do_partido = _nivel("Apoio do partido a esta candidatura", "q_apoio_partido")

        with st.expander("4. Comunicacao"):
            conhecimento_espontaneo = _nivel(
                "Conhecimento espontaneo (eleitores que reconhecem o nome sem ajuda)", "q_conhecimento"
            )
            oratoria = _nivel("Oratoria", "q_oratoria")
            desempenho_videos = _nivel("Desempenho em videos", "q_videos")
            entrevistas = _nivel("Desempenho em entrevistas", "q_entrevistas")
            debates = _nivel("Desempenho em debates", "q_debates")
            resposta_criticas = _nivel("Resposta a criticas", "q_resp_criticas")
            seguidores_redes = _nivel("Volume de seguidores nas redes sociais", "q_seguidores")
            engajamento = _nivel("Engajamento nas redes sociais", "q_engajamento")
            producao_conteudo = _nivel("Producao propria de conteudo", "q_conteudo")
            equipe_comunicacao = _nivel("Equipe de comunicacao", "q_equipe_com")
            rejeicao_percebida = _nivel("Rejeicao percebida (quanto maior, pior)", "q_rejeicao")

        with st.expander("5. Recursos"):
            disponibilidade_tempo = _nivel("Disponibilidade de tempo", "q_disp_tempo")
            capacidade_investimento_legal = _nivel("Capacidade de investimento legal proprio", "q_investimento")
            capacidade_arrecadacao = _nivel("Capacidade de arrecadacao de campanha", "q_arrecadacao")
            equipe = _nivel("Equipe disponivel", "q_equipe")
            transporte = _nivel("Transporte", "q_transporte")
            locais_reuniao = _nivel("Locais para reuniao", "q_locais")
            audiovisual = _nivel("Estrutura audiovisual", "q_audiovisual")
            disponibilidade_viagens = _nivel("Disponibilidade para viagens", "q_disp_viagens")

        with st.expander("6. Posicionamento"):
            temas = st.text_input("Temas de maior identificacao (separados por virgula)", key="q_temas")
            resistencia_ataques = _nivel("Resistencia a ataques/criticas publicas", "q_resistencia")
            disciplina = _nivel("Disciplina (agenda, partido, mensagem)", "q_disciplina")

        enviado = st.form_submit_button("Calcular indices", type="primary")

    if not enviado:
        return

    resposta = RespostaQuestionario(
        identificacao=IdentificacaoAnalise(
            cargo_pretendido=cargo_pretendido,
            uf=uf,
            municipio_base=municipio_base or "-- nao informado --",
            partido_definido=partido_definido,
            partido_sigla=partido_sigla.strip().upper() if partido_definido == SimNao.SIM and partido_sigla.strip() else None,
            ja_disputou_eleicao=ja_disputou if ja_disputou is not None else SimNao.NAO,
            possui_padrinho_politico=possui_padrinho,
            nome_padrinho_politico=nome_padrinho.strip() if possui_padrinho == SimNao.SIM and nome_padrinho.strip() else None,
        ),
        trajetoria=Trajetoria(
            tempo_atuacao_publica=tempo_atuacao_publica,
            mandato_anterior=mandato_anterior,
            experiencia_politica_geral=experiencia_politica_geral,
            atuacao_administrativa=atuacao_administrativa,
            projetos_realizados=projetos_realizados,
            resultados_concretos=resultados_concretos,
        ),
        base_eleitoral=BaseEleitoral(
            numero_territorios_presenca=int(numero_territorios) if numero_territorios else None,
            estrutura_bairros=estrutura_bairros,
            apoiadores_mobilizaveis=apoiadores_mobilizaveis,
            capacidade_eventos=capacidade_eventos,
            relacionamento_liderancas=relacionamento_liderancas,
            relacionamento_vereadores=relacionamento_vereadores,
            relacionamento_prefeitos=relacionamento_prefeitos,
            relacionamento_deputados=relacionamento_deputados,
            relacionamento_entidades=relacionamento_entidades,
            liderancas_regionais=liderancas_regionais,
            apoio_do_partido=apoio_do_partido,
        ),
        comunicacao=Comunicacao(
            conhecimento_espontaneo=conhecimento_espontaneo,
            oratoria=oratoria,
            desempenho_videos=desempenho_videos,
            entrevistas=entrevistas,
            debates=debates,
            resposta_criticas=resposta_criticas,
            seguidores_redes=seguidores_redes,
            engajamento=engajamento,
            producao_conteudo=producao_conteudo,
            equipe_comunicacao=equipe_comunicacao,
            rejeicao_percebida=rejeicao_percebida,
        ),
        recursos=Recursos(
            disponibilidade_tempo=disponibilidade_tempo,
            capacidade_investimento_legal=capacidade_investimento_legal,
            capacidade_arrecadacao=capacidade_arrecadacao,
            equipe=equipe,
            transporte=transporte,
            locais_reuniao=locais_reuniao,
            audiovisual=audiovisual,
            disponibilidade_viagens=disponibilidade_viagens,
        ),
        posicionamento=Posicionamento(
            temas_identificacao=[t.strip() for t in temas.split(",") if t.strip()],
            resistencia_ataques=resistencia_ataques,
            disciplina=disciplina,
        ),
    )

    indices = calcular_indices_candidato(resposta)
    arquetipo = classificar_arquetipo(indices)

    st.divider()
    st.subheader("Resultado")
    st.caption(
        f"Taxa de preenchimento do questionario: {resposta.taxa_preenchimento()}% - "
        f"Cobertura geral dos indices: {indices.cobertura_geral_pct}%"
    )
    st.warning(
        "Aviso metodologico: os indices abaixo sao autoavaliacao categorica declarada "
        "neste formulario - nao sao medicao objetiva de dado eleitoral."
    )
    if resposta.identificacao.possui_padrinho_politico == SimNao.SIM:
        st.info(
            f"🤝 Padrinho politico declarado: **{resposta.identificacao.nome_padrinho_politico or '-- nome nao informado --'}**. "
            "Leve em conta na estrategia e nos relatorios deste candidato: pode ser fonte real de apoio "
            "(estrutura, base eleitoral emprestada, aval publico) mas tambem risco de associacao "
            "(desgaste ou controversia do padrinho reflete no afilhado)."
        )

    r_prontidao = indices["prontidao_eleitoral"]
    r_competitividade = indices["competitividade_inicial"]
    r_potencial = indices["potencial_crescimento"]
    r_risco = indices["risco_reputacional"]
    kpis = st.columns(4)
    _kpi(kpis[0], "Prontidao Eleitoral", f"{r_prontidao.valor:.0f}/100", _rotulo_classificacao(r_prontidao),
         _tom_indice(r_prontidao.valor, False))
    _kpi(kpis[1], "Competitividade Inicial", f"{r_competitividade.valor:.0f}/100",
         _rotulo_classificacao(r_competitividade), _tom_indice(r_competitividade.valor, False))
    _kpi(kpis[2], "Potencial de Crescimento", f"{r_potencial.valor:.0f}/100", _rotulo_classificacao(r_potencial),
         _tom_indice(r_potencial.valor, False))
    _kpi(kpis[3], "Risco Reputacional", f"{r_risco.valor:.0f}/100", _rotulo_classificacao(r_risco),
         _tom_indice(r_risco.valor, True))

    st.subheader("Os 20 indices")
    linhas = [
        {
            "Indice": nome.replace("_", " ").title(),
            "Nota": r.valor,
            "Classificacao": _rotulo_classificacao(r),
            "Cobertura": f"{r.cobertura_pct:.0f}%",
            "Leitura": "nota alta = pior" if r.pior_quando_alto else "nota alta = melhor",
        }
        for nome, r in indices.indices.items()
    ]
    st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)

    st.subheader("Arquetipo politico-eleitoral")
    if arquetipo.arquetipo_principal:
        st.markdown(f"**Principal:** {arquetipo.arquetipo_principal.replace('_', ' ').title()}")
        if arquetipo.arquetipos_secundarios:
            secundarios_fmt = ", ".join(a.replace("_", " ").title() for a in arquetipo.arquetipos_secundarios)
            st.markdown(f"**Secundarios:** {secundarios_fmt}")
        if arquetipo.cargos_compativeis:
            st.markdown(f"**Cargos compativeis (arquetipo principal):** {', '.join(arquetipo.cargos_compativeis)}")
        st.caption(f"Evidencia: `{arquetipo.evidencias.get(arquetipo.arquetipo_principal)}`")
    else:
        st.markdown("Nenhum arquetipo com evidencia suficiente nas respostas informadas.")

    st.divider()
    st.subheader("Rivais projetados e compatibilidade partidaria")
    _explicacao(
        "Diferente dos indices acima, esta secao <strong>nao e autoavaliacao</strong>: usa dado "
        "real de votacao do TSE da disputa comparavel mais recente para o cargo/UF/municipio "
        "informados (mesmo motor de busca do resto do SIET). A unica premissa hipotetica, "
        "sempre declarada, e que essa disputa passada e um proxy razoavel de quem disputara a "
        "proxima eleicao."
    )

    resultado_rivais = identificar_rivais_projetados(resposta.identificacao)
    disputa = resultado_rivais.disputa
    if disputa.ano:
        st.caption(
            f"Disputa comparavel usada: {disputa.cargo_tse} / {disputa.uf}"
            f"{' / ' + disputa.municipio_nome if disputa.municipio_nome else ''} / {disputa.ano}"
        )
    for aviso in disputa.avisos:
        st.warning(aviso)

    if resultado_rivais.rivais:
        st.markdown("**Rivais projetados (top votados na disputa comparavel real)**")
        linhas_rivais = [
            {
                "Colocacao": r.colocacao,
                "Nome de urna": r.candidatura.nome_urna,
                "Partido": r.candidatura.partido_sigla,
                "Votos (disputa comparavel)": r.candidatura.total_votos,
                "Resultado (disputa comparavel)": r.candidatura.resultado_final,
                "Indice de rivalidade": r.indice_rivalidade,
                "Classificacao": r.classificacao.replace("_", " ").title(),
                "Tipo": ", ".join(t.replace("_", " ") for t in r.tipos),
            }
            for r in resultado_rivais.rivais
        ]
        st.dataframe(pd.DataFrame(linhas_rivais), use_container_width=True, hide_index=True)

    if resposta.identificacao.partido_sigla:
        resultado_partido = avaliar_compatibilidade_partidaria(
            resposta.identificacao.partido_sigla,
            resposta.identificacao.cargo_pretendido,
            resposta.identificacao.uf,
            resposta.identificacao.municipio_base,
        )
        st.markdown(f"**Compatibilidade partidaria real: {resultado_partido.partido_sigla}**")
        for aviso in resultado_partido.avisos:
            if aviso not in disputa.avisos:
                st.warning(aviso)
        if resultado_partido.n_candidatos_partido:
            kpis_partido = st.columns(4)
            _kpi(kpis_partido[0], "Candidatos do partido (disputa comparavel)", str(resultado_partido.n_candidatos_partido))
            _kpi(kpis_partido[1], "Eleitos do partido (disputa comparavel)", str(resultado_partido.n_eleitos_partido))
            _kpi(kpis_partido[2], "Taxa de sucesso do partido",
                 f"{resultado_partido.taxa_sucesso_partido * 100:.0f}%" if resultado_partido.taxa_sucesso_partido is not None else "n/d")
            _kpi(kpis_partido[3], "Melhor colocacao do partido",
                 f"{resultado_partido.melhor_colocacao_partido}o lugar" if resultado_partido.melhor_colocacao_partido else "n/d")
            if resultado_partido.piso_real_da_disputa is not None and resultado_partido.votos_melhor_candidato_partido is not None:
                st.caption(
                    f"Piso real de votos entre os eleitos da disputa comparavel: "
                    f"{_fmt(resultado_partido.piso_real_da_disputa)}. Melhor candidato do partido nessa "
                    f"disputa teve {_fmt(resultado_partido.votos_melhor_candidato_partido)} votos."
                )
    else:
        st.caption("Informe a sigla do partido no formulario acima para ver a compatibilidade partidaria real.")


# --------------------------------------------------------- Modulo Pautas
_PAUTAS_LABELS = {
    pauta_id: dados["label"] for pauta_id, dados in policy_areas_config()["pautas"].items()
}


def _pagina_questionario_pauta() -> None:
    """Modo 3 (Pautas/Plataforma) - questionario de pauta de politica
    publica (secao 10 do briefing de expansao SIET). NAO depende de
    nenhuma candidatura real do TSE. Ver ETAPA1_ARQUITETURA.md e
    src/questionnaire/policy_questionnaire.py."""
    st.title("Questionario de Pauta / Plataforma")
    _explicacao(
        "Autoavaliacao estruturada da pauta - <strong>nao e dado oficial de politica "
        "publica</strong> (isso exigiria conectores DATASUS/INEP/SICONFI/SNIS, nao "
        "integrados nesta etapa). A UNICA parte com fonte externa verificavel e a "
        "competencia federativa/base legal da pauta, lida de config/policy_areas.yaml - "
        "nunca digitada aqui. Perguntas deixadas em \"-- nao respondido --\" ficam de "
        "fora do calculo de cada indice."
    )

    with st.form("form_questionario_pauta"):
        st.subheader("1. Identificacao da pauta")
        c1, c2 = st.columns(2)
        pauta_id = c1.selectbox(
            "Pauta", list(_PAUTAS_LABELS.keys()), format_func=lambda k: _PAUTAS_LABELS[k], key="p_pauta_id"
        )
        cargo_analisado = c2.selectbox("Cargo analisado", _CARGOS_MODO1, key="p_cargo")

        problema_central = st.text_area("Problema central que a proposta pretende enfrentar", key="p_problema")
        c3, c4 = st.columns(2)
        publico_afetado = c3.text_input("Publico afetado (agregado, nunca individual)", key="p_publico")
        territorio_afetado = c4.text_input("Territorio afetado", key="p_territorio")
        proposta_principal = st.text_area("Proposta principal", key="p_proposta_principal")
        propostas_complementares = st.text_input(
            "Propostas complementares (separadas por virgula)", key="p_propostas_complementares"
        )

        with st.expander("2. Gravidade, urgencia e aderencia"):
            gravidade_problema = _nivel("Gravidade do problema", "p_gravidade")
            urgencia = _nivel("Urgencia", "p_urgencia")
            abrangencia_territorial = _nivel("Abrangencia territorial do problema", "p_abrangencia")
            aderencia_candidato = _nivel("Aderencia a trajetoria do candidato", "p_aderencia")
            credibilidade_candidato = _nivel("Credibilidade do candidato nesta pauta", "p_credibilidade")
            experiencia_anterior_candidato = _nivel("Experiencia anterior do candidato com o tema", "p_experiencia")

        with st.expander("3. Concorrencia e diferenciacao"):
            saturacao_outros_candidatos = _nivel(
                "Quanto outros candidatos ja ocupam esta pauta (saturacao)", "p_saturacao"
            )
            diferenciacao = _nivel("Diferenciacao desta proposta frente as existentes", "p_diferenciacao")

        with st.expander("4. Viabilidade e risco"):
            dados_comprovam_problema = _simnao("Existem dados que comprovam o problema?", "p_dados_comprovam")
            existe_estimativa_custo = _simnao("Existe estimativa de custo?", "p_custo")
            existe_fonte_financiamento = _simnao("Existe fonte de financiamento identificada?", "p_financiamento")
            existe_prazo_definido = _simnao("Existe prazo definido?", "p_prazo")
            existe_indicador_resultado = _simnao("Existe indicador de resultado?", "p_indicador")
            existe_meta_definida = _simnao("Existe meta definida?", "p_meta")
            depende_outro_ente = _simnao("A proposta depende de outro ente federativo?", "p_depende_outro_ente")
            exige_alteracao_legislativa = _simnao("A proposta exige alteracao legislativa?", "p_exige_lei")
            exige_parceria = _simnao("A proposta exige parceria (privada/terceiro setor)?", "p_exige_parceria")
            risco_juridico = _nivel("Risco juridico percebido", "p_risco_juridico")
            risco_fiscal = _nivel("Risco fiscal percebido", "p_risco_fiscal")
            risco_rejeicao = _nivel("Risco de rejeicao publica percebido", "p_risco_rejeicao")

        with st.expander("5. Comunicacao e coerencia"):
            potencial_comunicacao = _nivel("Potencial de comunicacao da pauta", "p_potencial_comunicacao")
            potencial_mobilizacao = _nivel("Potencial de mobilizacao da pauta", "p_potencial_mobilizacao")
            coerencia_com_outras_pautas = _nivel(
                "Coerencia com as demais pautas da plataforma", "p_coerencia"
            )

        enviado = st.form_submit_button("Calcular prioridade", type="primary")

    if not enviado:
        return

    proposta = PropostaPauta(
        pauta_id=pauta_id,
        cargo_analisado=cargo_analisado,
        problema_central=problema_central,
        publico_afetado=publico_afetado,
        territorio_afetado=territorio_afetado,
        proposta_principal=proposta_principal,
        propostas_complementares=[t.strip() for t in propostas_complementares.split(",") if t.strip()],
        gravidade_problema=gravidade_problema,
        urgencia=urgencia,
        abrangencia_territorial=abrangencia_territorial,
        aderencia_candidato=aderencia_candidato,
        credibilidade_candidato=credibilidade_candidato,
        experiencia_anterior_candidato=experiencia_anterior_candidato,
        saturacao_outros_candidatos=saturacao_outros_candidatos,
        diferenciacao=diferenciacao,
        risco_juridico=risco_juridico,
        risco_fiscal=risco_fiscal,
        risco_rejeicao=risco_rejeicao,
        potencial_comunicacao=potencial_comunicacao,
        potencial_mobilizacao=potencial_mobilizacao,
        coerencia_com_outras_pautas=coerencia_com_outras_pautas,
        dados_comprovam_problema=dados_comprovam_problema,
        existe_estimativa_custo=existe_estimativa_custo,
        existe_fonte_financiamento=existe_fonte_financiamento,
        existe_prazo_definido=existe_prazo_definido,
        existe_indicador_resultado=existe_indicador_resultado,
        existe_meta_definida=existe_meta_definida,
        depende_outro_ente=depende_outro_ente,
        exige_alteracao_legislativa=exige_alteracao_legislativa,
        exige_parceria=exige_parceria,
    )

    indices = calcular_indices_pauta(proposta)
    classificacao = classificar_pauta(indices)
    plataforma = montar_plataforma(proposta, indices, classificacao)

    st.divider()
    st.subheader("Resultado")
    st.caption(
        f"Taxa de preenchimento do questionario: {proposta.taxa_preenchimento()}% - "
        f"Cobertura geral dos indices: {indices.cobertura_geral_pct}%"
    )
    st.warning(
        "Aviso metodologico: os indices abaixo sao autoavaliacao categorica declarada "
        "neste formulario - nao sao dado oficial de politica publica."
    )

    r_geral = indices["indice_geral_prioridade"]
    r_relevancia = indices["relevancia_pauta"]
    r_viab_fiscal = indices["viabilidade_fiscal"]
    r_risco_rejeicao = indices["risco_de_rejeicao"]
    kpis = st.columns(4)
    _kpi(kpis[0], "Indice Geral de Prioridade", f"{r_geral.valor:.0f}/100", _rotulo_classificacao(r_geral),
         _tom_indice(r_geral.valor, False))
    _kpi(kpis[1], "Relevancia da Pauta", f"{r_relevancia.valor:.0f}/100", _rotulo_classificacao(r_relevancia),
         _tom_indice(r_relevancia.valor, False))
    _kpi(kpis[2], "Viabilidade Fiscal", f"{r_viab_fiscal.valor:.0f}/100", _rotulo_classificacao(r_viab_fiscal),
         _tom_indice(r_viab_fiscal.valor, False))
    _kpi(kpis[3], "Risco de Rejeicao", f"{r_risco_rejeicao.valor:.0f}/100", _rotulo_classificacao(r_risco_rejeicao),
         _tom_indice(r_risco_rejeicao.valor, True))

    st.subheader("Os 20 indices")
    linhas = [
        {
            "Indice": nome.replace("_", " ").title(),
            "Nota": r.valor,
            "Classificacao": _rotulo_classificacao(r),
            "Cobertura": f"{r.cobertura_pct:.0f}%",
            "Leitura": "nota alta = pior" if r.pior_quando_alto else "nota alta = melhor",
        }
        for nome, r in indices.indices.items()
    ]
    st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)

    st.subheader("Classificacao na matriz de priorizacao")
    if classificacao.classificacao_principal:
        st.markdown(f"**Principal:** {classificacao.classificacao_principal.replace('_', ' ').title()}")
        if classificacao.tambem_aplicavel:
            outros_fmt = ", ".join(c.replace("_", " ").title() for c in classificacao.tambem_aplicavel)
            st.markdown(f"**Tambem aplicavel:** {outros_fmt}")
        st.caption(f"Evidencia: `{classificacao.evidencias.get(classificacao.classificacao_principal)}`")
    else:
        st.markdown("Nenhuma classificacao da matriz com evidencia suficiente nas respostas informadas.")

    st.subheader("Plataforma gerada")
    if plataforma.gate.aprovado:
        st.success(f"Gate de competencia do cargo: APROVADO - {plataforma.gate.motivo}")
    else:
        st.error(f"Gate de competencia do cargo: REPROVADO - {plataforma.gate.motivo}")

    st.markdown(f"**Orgao responsavel:** {plataforma.orgao_responsavel}")
    st.markdown(f"**Publico beneficiado:** {plataforma.publico_beneficiado}")
    st.markdown(f"**Territorio:** {plataforma.territorio}")
    st.markdown(f"**Custo estimado:** {plataforma.custo_estimado}")
    st.markdown(f"**Fonte de recursos:** {plataforma.fonte_recursos}")
    st.markdown(f"**Prazo:** {plataforma.prazo}")
    st.markdown(f"**Indicadores:** {plataforma.indicadores}")
    st.markdown(f"**Metas:** {plataforma.metas}")
    st.markdown(f"**Parceiros:** {plataforma.parceiros}")
    st.markdown(f"**Riscos:** {plataforma.riscos}")
    with st.expander("Campos que exigem elaboracao qualitativa adicional (nao gerados automaticamente)"):
        st.markdown(f"**Causas:** {plataforma.causas}")
        st.markdown(f"**Consequencias:** {plataforma.consequencias}")
        st.markdown(f"**Objetivos especificos:** {plataforma.objetivos_especificos}")
        st.markdown(f"**Etapas:** {plataforma.etapas}")
    st.caption(f"Justificativa tecnica: {plataforma.justificativa_tecnica}")


# ------------------------------------------------------- Modulo Integracao
def _pagina_matriz_integrada() -> None:
    """Modo 4 (Integracao) - Matriz Candidato x Territorio x Pauta (secao
    15 do briefing de expansao SIET). Cruza um subconjunto do Modo 1
    (identificacao + autoridade tematica), uma pauta do Modo 3 e o perfil
    territorial REAL (Censo IBGE/RAIS-CAGED) do municipio informado. Ver
    ETAPA1_ARQUITETURA.md e src/integration/candidate_territory_policy_matrix.py.

    Escopo desta etapa (decisao explicita, nao lacuna escondida): uma pauta
    por analise (o backend ja aceita uma lista - a UI de comparar varias
    pautas de uma vez fica para uma proxima etapa) e so os 2 campos do Modo
    1 que alimentam o indice de Autoridade Tematica (quem quiser o
    perfil de autoavaliacao completo usa o Modo 1 por si)."""
    st.title("Matriz Integrada: Candidato x Territorio x Pauta")
    _explicacao(
        "Cruza tres origens de dado DIFERENTES, cada uma rotulada como e: "
        "(1) autoavaliacao do candidato e da pauta (Modos 1 e 3, categorica, "
        "declarada aqui); (2) perfil territorial REAL do municipio (Censo IBGE 2022 "
        "+ RAIS/CAGED, nao ponderado por voto - o candidato ainda nao disputou, "
        "ver nota metodologica do modulo). O indice de compatibilidade candidato-pauta "
        "so combina as duas autoavaliacoes; o perfil territorial e mostrado ao lado, "
        "nunca misturado num unico numero com autoavaliacao."
    )

    with st.form("form_matriz_integrada"):
        st.subheader("1. Identificacao")
        c1, c2, c3 = st.columns(3)
        cargo_pretendido = c1.selectbox("Cargo pretendido", _CARGOS_MODO1, key="m_cargo")
        uf = c2.selectbox("UF", list(UF_NOME.keys()), key="m_uf")
        municipio_base = c3.text_input("Municipio-base", key="m_municipio")

        st.subheader("2. Autoridade tematica do candidato (resumo do Modo 1)")
        temas = st.text_input("Temas de maior identificacao (separados por virgula)", key="m_temas")
        c4, c5 = st.columns(2)
        with c4:
            projetos_realizados = _nivel("Projetos realizados no tema da pauta abaixo", "m_projetos")
        with c5:
            resultados_concretos = _nivel("Resultados concretos entregues no tema", "m_resultados")

        st.subheader("3. Pauta a cruzar")
        c6, c7 = st.columns(2)
        pauta_id = c6.selectbox(
            "Pauta", list(_PAUTAS_LABELS.keys()), format_func=lambda k: _PAUTAS_LABELS[k], key="m_pauta_id"
        )
        territorio_afetado = c7.text_input("Territorio afetado pela pauta", key="m_territorio_pauta")
        c8, c9 = st.columns(2)
        with c8:
            aderencia_candidato = _nivel("Aderencia desta pauta a trajetoria do candidato", "m_aderencia")
        with c9:
            gravidade_problema = _nivel("Gravidade do problema que a pauta enfrenta", "m_gravidade")

        enviado = st.form_submit_button("Calcular matriz", type="primary")

    if not enviado:
        return

    identificacao = IdentificacaoAnalise(cargo_pretendido=cargo_pretendido, uf=uf, municipio_base=municipio_base or "-- nao informado --")
    resposta = RespostaQuestionario(
        identificacao=identificacao,
        trajetoria=Trajetoria(projetos_realizados=projetos_realizados, resultados_concretos=resultados_concretos),
        posicionamento=Posicionamento(temas_identificacao=[t.strip() for t in temas.split(",") if t.strip()]),
    )
    indices_candidato = calcular_indices_candidato(resposta)

    proposta = PropostaPauta(
        pauta_id=pauta_id, cargo_analisado=cargo_pretendido,
        territorio_afetado=territorio_afetado, aderencia_candidato=aderencia_candidato,
        gravidade_problema=gravidade_problema,
    )
    indices_pauta = calcular_indices_pauta(proposta)
    gate = verificar_gate_competencia(proposta.pauta_id, proposta.cargo_analisado)

    resultado = montar_matriz_candidato_territorio_pauta(identificacao, indices_candidato, [(proposta, indices_pauta, gate)])

    st.divider()
    st.subheader("Perfil territorial real do municipio")
    perfil = resultado.perfil_territorial
    for aviso in perfil.avisos:
        st.warning(aviso)
    if perfil.indicadores_piramide_maslow:
        st.caption(
            f"{perfil.municipio}/{perfil.uf} - {perfil.n_setores_censitarios} setores censitarios (Censo IBGE 2022). "
            "Media ponderada por populacao real do setor - NAO ponderada por voto (sem candidatura real ainda)."
        )
        linhas_territorio = [
            {"Indicador": var.replace("_", " ").title(), "Valor real (municipio)": valor}
            for var, valor in perfil.indicadores_piramide_maslow.items()
        ]
        st.dataframe(pd.DataFrame(linhas_territorio), use_container_width=True, hide_index=True)
    if perfil.perfil_economico and perfil.perfil_economico.disponivel:
        pe = perfil.perfil_economico
        st.caption(
            f"Contexto economico real (RAIS/CAGED): {_fmt(pe.vinculos_ativos_total)} vinculos formais ativos, "
            f"tendencia de emprego '{pe.tendencia}'."
        )

    st.subheader("Compatibilidade candidato x pauta")
    for c in resultado.compatibilidades:
        if c.elegivel_pelo_cargo:
            st.success(f"Gate de competencia do cargo: APROVADO - {c.motivo_elegibilidade}")
        else:
            st.error(f"Gate de competencia do cargo: REPROVADO - {c.motivo_elegibilidade}")

        kpis = st.columns(4)
        _kpi(kpis[0], "Indice de Compatibilidade", f"{c.indice_compatibilidade:.0f}/100",
             c.classificacao.replace("_", " ").title(), _tom_indice(c.indice_compatibilidade, False))
        _kpi(kpis[1], "Autoridade Tematica (Modo 1)",
             f"{c.autoridade_tematica_candidato:.0f}/100" if c.autoridade_tematica_candidato is not None else "n/d")
        _kpi(kpis[2], "Aderencia a Pauta (Modo 3)",
             f"{c.aderencia_candidato_pauta:.0f}/100" if c.aderencia_candidato_pauta is not None else "n/d")
        _kpi(kpis[3], "Prioridade da Pauta (Modo 3)", f"{c.indice_geral_prioridade_pauta:.0f}/100")

        if c.mesmo_territorio_declarado is False:
            st.warning(
                "O territorio-base do candidato e o territorio afetado declarado na pauta "
                "parecem diferentes - confira se a pauta faz sentido para este municipio-base."
            )
        st.caption(f"Cobertura do indice de compatibilidade: {c.cobertura_pct}%")


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
def _carregar_territorial_turno(
    veio_do_fallback: bool, ano: int, cargo: str, uf: str, municipio_codigo, turno_alvo: int, numero: int, nivel: str,
) -> pd.DataFrame | None:
    """Carrega o desempenho territorial de um turno especifico (1 ou 2)
    para o MESMO candidato - usado pela Comparacao de Turnos, que precisa
    dos dois turnos independente de qual foi escolhido na selecao guiada.
    Retorna None quando o candidato nao existe nesse turno (bug real
    corrigido: a maioria das disputas brasileiras de Prefeito/Governador
    NUNCA tem 2o turno, e mesmo quando tem, so os 2 primeiros colocados
    avancam - antes disso o `next(...)` sem default de
    _carregar_dados_candidatura[_v2] estourava StopIteration nao tratado e
    derrubava a pagina inteira para qualquer candidato comum que abrisse
    esta secao)."""
    try:
        if veio_do_fallback:
            cand_t, vc_t, vd_t, rd_t = _carregar_dados_candidatura(numero, municipio_codigo, cargo, ano, turno_alvo)
        else:
            cand_t, vc_t, vd_t, rd_t = _carregar_dados_candidatura_v2(ano, cargo, uf, municipio_codigo, turno_alvo, numero)
    except StopIteration:
        return None
    return desempenho_territorial(cand_t, vc_t, vd_t, rd_t, nivel)


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
    # Comparecimento/abstencao/brancos/nulos (por secao, so existe para 2024
    # - ver enriquecer_com_comparecimento_abstencao) mesclados ANTES do
    # groupby por secao_id, usando a mesma chave composta (zona+secao) que a
    # funcao ja sabe casar - cada secao_id corresponde a exatamente 1
    # NR_SECAO_COMPOSTA, entao "first" no groupby abaixo preserva o valor
    # sem ambiguidade.
    enriquecido_part = _enriquecido
    if "NR_ZONA" in _enriquecido.columns and "NR_SECAO" in _enriquecido.columns:
        enriquecido_part = enriquecer_com_comparecimento_abstencao(
            _enriquecido.assign(NR_SECAO_COMPOSTA=secao_composta(_enriquecido)),
            municipio_tse, cargo, "NR_SECAO_COMPOSTA",
        )
    # "first" para local_votacao_id: todo secao_id pertence a exatamente um
    # local_votacao_id (predio), entao nao ha ambiguidade - preservado aqui
    # para uso como coluna de cluster na regressao (secoes do mesmo predio
    # nao sao observacoes independentes, ver _COLUNA_CLUSTER_REGRESSAO).
    agregacoes = {"votos_candidato": ("votos_candidato", "sum")}
    if "local_votacao_id" in enriquecido_part.columns and nivel != "local_votacao_id":
        agregacoes["local_votacao_id"] = ("local_votacao_id", "first")
    for col in ("comparecimento", "QT_APTOS", "abstencoes", "votos_brancos", "votos_nulos"):
        if col in enriquecido_part.columns:
            agregacoes[col] = (col, "first")
    votos_territorio = enriquecido_part.groupby(nivel, as_index=False).agg(**agregacoes)
    total_validos = total_votos_validos_por_territorio(_vd, _enriquecido, nivel)
    base = (
        votos_territorio.merge(perfil_territorio, on=nivel, how="inner")
        .merge(total_validos, on=nivel, how="left")
    )
    base["pct_votos_validos_territorio"] = (
        100 * base["votos_candidato"] / base["votos_validos_territorio"]
    ).round(2)
    if "QT_APTOS" in base.columns:
        base = indice_participacao_territorial(base)
    return perfil_setor, base


@st.cache_data(show_spinner=False)
def _carregar_geografia_estadual(numero, uf, cargo, ano, turno, _candidatura: Candidatura, _vc: pd.DataFrame):
    """Equivalente a _carregar_geografia, mas para a UF inteira (cargos
    estaduais/distritais, V2) - mesmo arquivo nacional de coordenadas e
    mesma malha por UF ja usados pelo caminho municipal, so sem filtrar
    para 1 municipio (ver src/geographic_analysis.py)."""
    coords = carregar_coordenadas_uf(uf, ano)
    pontos = juntar_votos_com_coordenadas(_vc, coords)
    enriquecido, avisos = atribuir_setor_e_bairro_uf(pontos, uf)
    return pontos, enriquecido, avisos


@st.cache_data(show_spinner=False)
def _carregar_geografia_estadual_secao(numero, uf, cargo, ano, turno, _candidatura: Candidatura, _vc: pd.DataFrame):
    """Como _carregar_geografia_estadual, mas por SECAO (nao por predio) -
    usado quando o usuario escolhe analisar 1 municipio da UF por bairro
    (V2): precisa da mesma granularidade de secao/setor ja usada pelo
    caminho municipal (_geo_secao), so calculada para a UF inteira antes
    de filtrar para o municipio escolhido (reaproveita a mesma malha ja
    baixada, sem download adicional)."""
    coords = carregar_coordenadas_uf(uf, ano)
    pontos = juntar_votos_com_coordenadas_secao(_vc, coords)
    enriquecido, avisos = atribuir_setor_e_bairro_uf(pontos, uf)
    return pontos, enriquecido, avisos


@st.cache_data(show_spinner=False)
def _carregar_demografia_estadual_generica(
    numero, uf, cargo, ano, turno, _enriquecido: pd.DataFrame, _vd: pd.DataFrame, nivel: str,
):
    """Como _carregar_demografia_estadual, mas parametrizada por `nivel` -
    permite agregar por CD_MUNICIPIO (regressao por municipio, ja existente,
    ver _carregar_demografia_estadual) OU por uma granularidade mais fina
    cobrindo a UF inteira (zona_uf_composta ou secao_id - "Regressao Geral",
    usada quando o numero de municipios da UF e pequeno demais para a
    regressao por municipio convergir, ver src/regression_models.py).

    Quando `nivel` nao e CD_MUNICIPIO, preserva CD_MUNICIPIO (e
    local_votacao_id, quando presente) agregados por "first": cada zona/secao
    pertence a exatamente 1 municipio (e cada secao a exatamente 1 local de
    votacao), entao nao ha ambiguidade - essas colunas sao usadas depois
    para cluster de 2 vias e para mesclar covariaveis de porte do
    municipio."""
    setores = set(_enriquecido["CD_SETOR"].dropna().unique()) if "CD_SETOR" in _enriquecido else set()
    if not setores or nivel not in _enriquecido.columns or _enriquecido[nivel].notna().sum() == 0:
        return pd.DataFrame(), pd.DataFrame()
    perfil_setor = perfil_demografico_por_setor(setores)
    perfil_territorio = perfil_demografico_do_territorio(_enriquecido, perfil_setor, nivel)
    agregacoes = {"votos_candidato": ("votos_candidato", "sum")}
    if nivel != "CD_MUNICIPIO" and "CD_MUNICIPIO" in _enriquecido.columns:
        agregacoes["CD_MUNICIPIO"] = ("CD_MUNICIPIO", "first")
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


@st.cache_data(show_spinner=False)
def _carregar_demografia_estadual(
    numero, uf, cargo, ano, turno, _enriquecido: pd.DataFrame, _vd: pd.DataFrame,
):
    """Equivalente a _carregar_demografia, mas agregado por MUNICIPIO (nao
    por secao/predio) - unidade natural para uma disputa estadual: da uma
    amostra grande o suficiente para regressao/clusterizacao (centenas de
    municipios) sem precisar de granularidade de secao, que so faz sentido
    dentro de 1 municipio."""
    return _carregar_demografia_estadual_generica(numero, uf, cargo, ano, turno, _enriquecido, _vd, "CD_MUNICIPIO")


@st.cache_data(show_spinner=False)
def _carregar_perfil_eleitorado_uf(uf: str) -> pd.DataFrame:
    return carregar_perfil_eleitorado_secao(uf)


st.sidebar.header("Modo de analise")
_modo_app = st.sidebar.radio(
    "O que voce quer analisar?",
    [
        "Candidatura ja disputada (TSE)",
        "Questionario de candidato (nova candidatura)",
        "Questionario de pauta/plataforma",
        "Matriz Integrada (Candidato x Territorio x Pauta)",
    ],
    key="v2_modo_app",
)
st.sidebar.divider()

if _modo_app == "Questionario de candidato (nova candidatura)":
    _pagina_questionario_candidato()
    st.stop()

if _modo_app == "Questionario de pauta/plataforma":
    _pagina_questionario_pauta()
    st.stop()

if _modo_app == "Matriz Integrada (Candidato x Territorio x Pauta)":
    _pagina_matriz_integrada()
    st.stop()

st.sidebar.header("Selecione a disputa")

_ANO_LABELS = {2024: "2024 - Eleicoes Municipais", 2022: "2022 - Eleicoes Gerais", 2018: "2018 - Eleicoes Gerais"}
_ANOS_SEM_MUNICIPIO = (2022, 2018)  # anos ESTADUAIS/DISTRITAIS - sem seletor de municipio
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
_cargo_pronto = bool(uf) and (ano in _ANOS_SEM_MUNICIPIO or municipio_codigo is not None)
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
cand_opcoes: dict = {}
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
        "(Censo Demografico 2022), Brasil inteiro. Eleicoes Municipais 2024 "
        "(Prefeito/Vereador). Eleicoes Gerais 2022 e 2018 (Governador, Senador, "
        "Deputado Federal e Estadual) - 2018 usa fonte alternativa de votacao "
        "por secao (o CDN oficial do TSE bloqueia esse ano), ver Limitacoes."
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
    f"- Abrangencia: {'Municipal' if alvo.codigo_municipio_tse is not None else 'Estadual'}"
)

candidatura_b_selecionada = None
if not veio_do_fallback and cand_opcoes:
    st.sidebar.checkbox("Comparar com outro candidato (mesma disputa)", key="v2_modo_comparacao")
    if st.session_state.get("v2_modo_comparacao"):
        cand_opcoes_b = {k: c for k, c in cand_opcoes.items() if c.numero != alvo.numero}
        if cand_opcoes_b:
            cand_label_b = st.sidebar.selectbox("Candidato B", list(cand_opcoes_b.keys()), key="v2_candidato_b")
            candidatura_b_selecionada = cand_opcoes_b[cand_label_b]
        else:
            st.sidebar.info("Nenhum outro candidato disponivel nesta disputa.")

_numero_b = candidatura_b_selecionada.numero if candidatura_b_selecionada is not None else None
_assinatura_selecao = (
    alvo.ano_eleicao, alvo.uf, alvo.codigo_municipio_tse, alvo.cargo, alvo.turno, alvo.numero, _numero_b,
)
_ja_gerado_para_esta_selecao = st.session_state.get("v2_selecao_gerada") == _assinatura_selecao

if st.sidebar.button("Gerar analise eleitoral", type="primary"):
    st.session_state["v2_selecao_gerada"] = _assinatura_selecao
    _ja_gerado_para_esta_selecao = True

if not _ja_gerado_para_esta_selecao:
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

candidatura_b = vc_b = None
if candidatura_b_selecionada is not None:
    with st.spinner(f"Carregando dados do candidato B ({candidatura_b_selecionada.nome_urna})..."):
        candidatura_b, vc_b, _, _ = _carregar_dados_candidatura_v2(
            ano, cargo, uf, municipio_codigo, turno, candidatura_b_selecionada.numero
        )

_escopo_atual = resolver_escopo(
    candidatura.ano_eleicao, candidatura.cargo, uf=candidatura.uf,
    municipio=(candidatura.municipio if candidatura.codigo_municipio_tse is not None else None),
    turno=candidatura.turno,
)
_eh_municipal = _escopo_atual.tipo_abrangencia == "MUNICIPAL"
_eh_proporcional = _escopo_atual.sistema_eleitoral == "PROPORCIONAL"
_permite_2o_turno = _escopo_atual.permite_segundo_turno

rg = resultado_geral(candidatura, vd, rd)
ranking = ranking_disputa(vd, rd)
rg_b = resultado_geral(candidatura_b, vd, rd) if candidatura_b is not None else None
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


def _geo_uf():
    return _carregar_geografia_estadual(
        candidatura.numero, candidatura.uf, candidatura.cargo,
        candidatura.ano_eleicao, candidatura.turno, candidatura, vc,
    )


def _demo_uf(enriquecido_df: pd.DataFrame):
    return _carregar_demografia_estadual(
        candidatura.numero, candidatura.uf, candidatura.cargo,
        candidatura.ano_eleicao, candidatura.turno, enriquecido_df, vd,
    )


def _geo_uf_secao():
    return _carregar_geografia_estadual_secao(
        candidatura.numero, candidatura.uf, candidatura.cargo,
        candidatura.ano_eleicao, candidatura.turno, candidatura, vc,
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
if not _eh_municipal:
    _opcoes_secao += ["Indicadores Estaduais"]
_opcoes_secao += ["Geografia", "Demografia", "Perfil do Eleitorado (TSE)", "Estatistica Avancada", "Abordagem de Maslow"]
if _eh_proporcional:
    _opcoes_secao += ["Detalhamento Proporcional"]
if _permite_2o_turno:
    _opcoes_secao += ["Comparacao de Turnos"]
if candidatura_b is not None:
    _opcoes_secao += ["Comparativo"]
_opcoes_secao += ["Relatorio"]
secao = st.sidebar.radio("Navegacao", _opcoes_secao)

_modo_estadual = None
_municipio_bairro_nome = None
_municipio_bairro_codigo = None
if not _eh_municipal:
    st.sidebar.divider()
    _modo_label = st.sidebar.radio(
        "Nivel em Geografia/Demografia/Estatistica/Maslow",
        ["Municipio (UF inteira)", "Bairro (escolher 1 municipio)"],
        key="v2_modo_estadual",
    )
    _modo_estadual = "municipio" if _modo_label.startswith("Municipio") else "bairro"
    if _modo_estadual == "municipio":
        st.sidebar.caption(
            "Cobre a UF inteira (todos os municipios), calculado sob demanda ao "
            "abrir a aba - a primeira abertura por UF pode levar cerca de 1 "
            "minuto (malha geografica), as seguintes ficam em cache."
        )
    else:
        _municipios_uf_disponiveis = sorted(vd["NM_MUNICIPIO"].dropna().unique())
        _municipio_bairro_nome = st.sidebar.selectbox(
            "Municipio para analise por bairro", _municipios_uf_disponiveis, key="v2_municipio_bairro",
        )
        _municipio_bairro_codigo = int(
            vd.loc[vd["NM_MUNICIPIO"] == _municipio_bairro_nome, "CD_MUNICIPIO"].iloc[0]
        )
        st.sidebar.caption(
            f"Analise de bairro restrita a {_municipio_bairro_nome} - mesmo detalhamento "
            "usado para Prefeito/Vereador (2024), aplicado aos votos deste candidato "
            "estadual dentro deste municipio."
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

    with st.container(border=True):
        st.subheader("Contexto economico do municipio (RAIS + CAGED)")
        if not _eh_municipal:
            st.info(
                "Contexto de RAIS/CAGED tem granularidade de MUNICIPIO - nao se aplica "
                "diretamente a um cargo estadual (a UF inteira nao e 'um municipio'). "
                "Disponivel apenas para Prefeito/Vereador nesta versao."
            )
        else:
            perfil_economico = carregar_perfil_economico_municipio(candidatura)
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
                ce4, ce5 = st.columns(2)
                _kpi(
                    ce4, "% vinculos formais em CLT",
                    f"{perfil_economico.pct_formalizacao_clt}%" if perfil_economico.pct_formalizacao_clt is not None else "n/d",
                )
                _kpi(
                    ce5, "Taxa de atividade empresarial",
                    f"{perfil_economico.taxa_atividade_empresarial}%" if perfil_economico.taxa_atividade_empresarial is not None else "n/d",
                    "% dos estabelecimentos cadastrados que estao ativos",
                )
                st.plotly_chart(charts.grafico_perfil_economico_municipio(perfil_economico), use_container_width=True)

    with st.container(border=True):
        st.subheader("Patrimonio declarado (TSE)")
        _explicacao(
            "Bens declarados pelo proprio candidato ao TSE no registro da candidatura - "
            "autodeclarado, nao e uma auditoria patrimonial. Comparado aos 3 maiores rivais "
            "da mesma disputa."
        )
        perfil_patrimonial = carregar_patrimonio_candidato(candidatura)
        if not perfil_patrimonial.disponivel:
            st.info("Bens declarados indisponiveis para este candidato.")
        else:
            pp1, pp2 = st.columns(2)
            _kpi(pp1, "Valor total declarado", f"R$ {_fmt(perfil_patrimonial.valor_total_bens)}")
            _kpi(pp2, "Itens declarados", str(perfil_patrimonial.n_itens_declarados))
            if not perfil_patrimonial.top_bens.empty:
                st.dataframe(
                    perfil_patrimonial.top_bens, use_container_width=True,
                    column_config={"valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f")},
                )
            comparativo_patrimonio = patrimonio_comparativo(candidatura, ranking, top_n=3)
            if not comparativo_patrimonio.empty:
                st.plotly_chart(
                    charts.grafico_patrimonio_comparativo(comparativo_patrimonio), use_container_width=True,
                )
            st.caption(perfil_patrimonial.limitacoes)

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
        st.subheader("Desempenho eleitoral real - candidato x rivais (IDP/IVE/IEC/QEC)")
        _explicacao(
            "4 indices calculados a partir do resultado eleitoral REAL de cada candidato na "
            "mesma disputa - nunca uma estimativa ou percepcao subjetiva. IDP (Desempenho "
            "Politico) e IEC (Eficiencia de Campanha): quanto maior, melhor. IVE "
            "(Vulnerabilidade Eleitoral): quanto maior, PIOR (mais exposto). QEC (Qualidade da "
            "Estrategia): mede a solidez/alcance das vitorias territoriais - tende a ficar "
            "perto de zero em disputas proporcionais concorridas (muitos candidatos fortes), "
            "onde 'dominar' um territorio com folga e raro mesmo para o 1o colocado - "
            "ver metodologia completa em config/indicators.yaml."
        )
        if not rivais_sim.empty:
            nivel_indices = "NR_ZONA" if _eh_municipal else "CD_MUNICIPIO"
            nomes_radar = [candidatura.nome_urna]
            indices_radar = [calcular_indices_desempenho_real(candidatura, vc, vd, rd, nivel_indices).valores()]
            registro_por_numero = rd.drop_duplicates("numero").set_index("numero")
            for linha in rivais_sim.itertuples():
                registro_rival = (
                    registro_por_numero.loc[int(linha.numero)]
                    if int(linha.numero) in registro_por_numero.index else None
                )
                candidatura_rival = Candidatura(
                    numero=int(linha.numero), nome_completo=linha.nome_urna, nome_urna=linha.nome_urna,
                    cargo=candidatura.cargo, municipio=candidatura.municipio,
                    codigo_municipio_tse=candidatura.codigo_municipio_tse, uf=candidatura.uf,
                    ano_eleicao=candidatura.ano_eleicao, turno=candidatura.turno,
                    partido_sigla=linha.partido_sigla,
                    partido_nome=str(registro_rival["partido_nome"]) if registro_rival is not None else "",
                    coligacao_federacao=str(registro_rival["coligacao_federacao"]) if registro_rival is not None else "",
                    situacao_candidatura=str(registro_rival["situacao_candidatura"]) if registro_rival is not None else "",
                    resultado_final=str(registro_rival["resultado_final"]) if registro_rival is not None else "",
                    total_votos=int(linha.total_votos_rival), zonas_com_votos=int(linha.territorios_em_comum),
                )
                vc_rival = vd[vd["NR_VOTAVEL"] == candidatura_rival.numero]
                indices_radar.append(
                    calcular_indices_desempenho_real(candidatura_rival, vc_rival, vd, rd, nivel_indices).valores()
                )
                nomes_radar.append(linha.nome_urna)
            st.plotly_chart(charts.grafico_radar_desempenho(nomes_radar, indices_radar), use_container_width=True)
        else:
            st.info("Precisa dos rivais por similaridade de base eleitoral (acima) para montar o comparativo.")

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
            "Cargo estadual: nivel territorial fixo em Municipio "
            "(a UF inteira, nao zona/secao)."
        )
        nivel = "CD_MUNICIPIO"

    terr = desempenho_territorial(candidatura, vc, vd, rd, nivel)
    terr = enriquecer_com_comparecimento_abstencao(
        terr, candidatura.codigo_municipio_tse, candidatura.cargo, nivel
    )
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
        st.subheader("Participacao territorial (comparecimento/abstencao/brancos/nulos)")
        _explicacao(
            "Comparecimento e abstencao sao % sobre o eleitorado apto do territorio; "
            "brancos e nulos sao % sobre quem compareceu - um proxy de protesto/rejeicao "
            "que nao aparece em nenhuma outra analise. So disponivel para 2024 (o TSE "
            "ainda nao publicou o arquivo de detalhe por secao para 2022 neste sistema)."
        )
        terr_participacao = indice_participacao_territorial(terr)
        if terr_participacao["pct_abstencao"].notna().any():
            st.plotly_chart(
                charts.grafico_participacao_territorial(terr_participacao, nivel), use_container_width=True,
            )
            st.dataframe(
                terr_participacao[[nivel, "pct_comparecimento", "pct_abstencao", "pct_brancos", "pct_nulos"]]
                .sort_values("pct_abstencao", ascending=False),
                use_container_width=True, height=300,
            )
        else:
            st.info("Dado de comparecimento/abstencao indisponivel para esta candidatura.")

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

# ================================================ Detalhamento Proporcional
elif secao == "Detalhamento Proporcional":
    _explicacao(
        "Cargo proporcional: a situacao final oficial (eleito/suplente/nao "
        "eleito) vem diretamente do TSE (DS_SIT_TOT_TURNO) - este sistema NAO "
        "recalcula quociente eleitoral/partidario nem a distribuicao de "
        "sobras (metodo de maiores medias), so reorganiza o resultado ja "
        "oficial por posicao dentro do partido/federacao."
    )
    partidos_rel = ranking_partidos(ranking, vd, rd)
    resumo_prop = resumo_proporcional(candidatura.numero, ranking, rd, partidos_rel)

    c1, c2, c3, c4 = st.columns(4)
    _kpi(c1, "Situacao oficial (TSE)", resumo_prop.situacao_final_oficial)
    _kpi(c2, "Colocacao geral", f"{resumo_prop.colocacao_geral}o de {len(ranking)}")
    _kpi(c3, "Colocacao no partido", f"{resumo_prop.colocacao_dentro_partido}o de {resumo_prop.n_candidatos_partido}")
    _kpi(c4, "Eleitos no partido", str(resumo_prop.n_eleitos_partido))

    with st.container(border=True):
        st.subheader(f"Dentro do partido ({resumo_prop.partido_sigla})")
        c5, c6 = st.columns(2)
        _kpi(c5, "Votos do partido (nominal + legenda)", _fmt(resumo_prop.votos_partido_total))
        _kpi(c6, "% do candidato no partido", f"{resumo_prop.pct_participacao_partido}%")
        c7, c8 = st.columns(2)
        _kpi(
            c7, "Diferenca p/ ultimo eleito do partido",
            f"{_fmt(resumo_prop.diferenca_para_ultimo_eleito_partido)} votos"
            if resumo_prop.diferenca_para_ultimo_eleito_partido is not None else "n/d",
            tom="bom" if (resumo_prop.diferenca_para_ultimo_eleito_partido or 0) >= 0 else "ruim",
        )
        _kpi(
            c8, "Diferenca p/ 1o suplente do partido",
            f"{_fmt(resumo_prop.diferenca_para_primeiro_suplente_partido)} votos"
            if resumo_prop.diferenca_para_primeiro_suplente_partido is not None else "n/d",
        )

    if resumo_prop.federacao:
        with st.container(border=True):
            st.subheader(f"Dentro da federacao/coligacao ({resumo_prop.federacao})")
            c9, c10, c11 = st.columns(3)
            _kpi(c9, "Votos da federacao", _fmt(resumo_prop.votos_federacao_total))
            _kpi(c10, "Colocacao na federacao", f"{resumo_prop.colocacao_dentro_federacao}o de {resumo_prop.n_candidatos_federacao}")
            _kpi(c11, "Eleitos na federacao", str(resumo_prop.n_eleitos_federacao))

    with st.container(border=True):
        st.subheader(f"Todos os candidatos do partido {resumo_prop.partido_sigla}")
        grupo_partido_rel = ranking[ranking["partido_sigla"] == resumo_prop.partido_sigla].sort_values(
            "total_votos", ascending=False
        )
        st.dataframe(
            grupo_partido_rel[["nome_urna", "total_votos", "pct_votos_validos", "resultado_final", "eleito"]],
            use_container_width=True, height=350,
        )

    with st.container(border=True):
        st.subheader("Ranking de partidos/federacoes na disputa")
        st.dataframe(partidos_rel, use_container_width=True, height=300)
        federacoes_rel = ranking_federacoes(partidos_rel, rd)
        if not federacoes_rel.empty:
            st.subheader("Ranking de federacoes/coligacoes")
            st.dataframe(federacoes_rel, use_container_width=True, height=250)

# =============================================================== Geografia
elif secao == "Geografia" and not _eh_municipal and _modo_estadual == "bairro":
    if not uf_tem_malha_completa(candidatura.uf):
        st.info(f"Malha geografica nao configurada para a UF '{candidatura.uf}'.")
    else:
        with st.spinner(
            f"Localizando locais de votacao da UF {candidatura.uf} inteira e cruzando com "
            "setores/bairros (IBGE) - a primeira vez pode levar cerca de 1 minuto..."
        ):
            pontos_uf, enriquecido_uf_bairro, avisos_geo_uf_bairro = _geo_uf()

        for aviso in avisos_geo_uf_bairro:
            st.warning(aviso)

        pontos = pontos_uf[pontos_uf["CD_MUNICIPIO"] == _municipio_bairro_codigo].reset_index(drop=True)
        enriquecido = enriquecido_uf_bairro[
            enriquecido_uf_bairro["CD_MUNICIPIO"] == _municipio_bairro_codigo
        ].reset_index(drop=True)

        if enriquecido.empty:
            st.info(f"Nenhum local de votacao encontrado para {_municipio_bairro_nome}.")
        else:
            bairros_agg = agregar_votos_por_bairro(enriquecido)
            with st.container(border=True):
                st.plotly_chart(charts.grafico_votos_por_bairro(bairros_agg), use_container_width=True)

            with st.container(border=True):
                st.subheader(f"Mapa de locais de votacao - {_municipio_bairro_nome}")
                mapa_pontos = maps.mapa_locais_votacao(enriquecido, candidatura.nome_urna)
                st_folium(mapa_pontos, width=None, height=500, key="mapa_pontos_bairro")

            with st.container(border=True):
                malha_bairros = carregar_malha("bairros", _municipio_bairro_nome, candidatura.uf)
                if malha_bairros is not None:
                    st.subheader(f"Mapa coropletico por bairro - {_municipio_bairro_nome}")
                    malha_gdf = malha_bairros
                    coluna_nivel, coluna_malha = "NM_BAIRRO_IBGE", "NM_BAIRRO"
                else:
                    st.subheader(
                        f"Mapa coropletico por distrito - {_municipio_bairro_nome} "
                        "(malha de bairro sem poligonos para este municipio)"
                    )
                    malha_gdf = carregar_malha("setores", _municipio_bairro_nome, candidatura.uf)
                    coluna_nivel, coluna_malha = "NM_DIST", "NM_DIST"

                if coluna_nivel in enriquecido.columns and enriquecido[coluna_nivel].notna().any() and malha_gdf is not None:
                    territorios_gdf = malha_gdf.dissolve(by=coluna_malha, as_index=False)
                    votos_territorio = enriquecido.groupby(coluna_nivel, as_index=False)["votos_candidato"].sum()
                    mapa_choro = maps.mapa_choropleth_territorio(
                        territorios_gdf, votos_territorio, coluna_malha, coluna_nivel,
                        "votos_candidato", candidatura.nome_urna,
                    )
                    st_folium(mapa_choro, width=None, height=500, key="mapa_choro_bairro")
                else:
                    st.info("Malha de bairro/distrito indisponivel para o mapa coropletico.")

            with st.container(border=True):
                st.subheader("Diagrama de Voronoi (area de influencia por local de votacao)")
                fronteira = malha_bairros if malha_bairros is not None else carregar_malha(
                    "setores", _municipio_bairro_nome, candidatura.uf
                )
                if fronteira is not None:
                    voronoi = gerar_voronoi(pontos, fronteira)
                    if voronoi is not None:
                        mapa_voronoi = maps.mapa_voronoi(voronoi)
                        st_folium(mapa_voronoi, width=None, height=500, key="mapa_voronoi_bairro")
                    else:
                        st.info("Numero insuficiente de locais com coordenada unica para gerar o Voronoi.")

elif secao == "Geografia" and not _eh_municipal:
    if not uf_tem_malha_completa(candidatura.uf):
        st.info(f"Malha geografica nao configurada para a UF '{candidatura.uf}'.")
    else:
        with st.spinner(
            f"Localizando locais de votacao da UF {candidatura.uf} inteira e cruzando com "
            "setores censitarios (IBGE) - a primeira vez pode levar cerca de 1 minuto..."
        ):
            _, enriquecido_uf, avisos_geo_uf = _geo_uf()

        for aviso in avisos_geo_uf:
            st.warning(aviso)

        terr_mun_geo = desempenho_territorial(candidatura, vc, vd, rd, "CD_MUNICIPIO")
        terr_mun_geo = terr_mun_geo.merge(
            vd[["CD_MUNICIPIO", "NM_MUNICIPIO"]].drop_duplicates(), on="CD_MUNICIPIO", how="left"
        )
        terr_mun_geo["_nome_norm"] = terr_mun_geo["NM_MUNICIPIO"].apply(normalizar_nome_municipio)

        with st.container(border=True):
            st.subheader(f"Mapa coropletico por municipio ({candidatura.uf})")
            _explicacao(
                "Um poligono por municipio da UF (contorno oficial IBGE, dissolvido a partir "
                "dos setores censitarios), colorido pela votacao do candidato - calculado sob "
                "demanda, cacheado apos a primeira vez para esta UF."
            )
            with st.spinner("Montando contorno dos municipios (primeira vez por UF - cacheado depois)..."):
                malha_municipios = carregar_malha_municipios_uf(candidatura.uf)
            if malha_municipios is not None:
                malha_municipios = malha_municipios.copy()
                malha_municipios["_nome_norm"] = malha_municipios["NM_MUN"].apply(normalizar_nome_municipio)
                mapa_choro_uf = maps.mapa_choropleth_territorio(
                    malha_municipios, terr_mun_geo, "_nome_norm", "_nome_norm",
                    "votos_candidato", candidatura.nome_urna, zoom_start=6,
                    simplificar_tolerancia=0.005,
                )
                st_folium(mapa_choro_uf, width=None, height=550, key="mapa_choro_uf")
            else:
                st.info("Malha de setores censitarios indisponivel para esta UF - mapa coropletico nao gerado.")

        with st.container(border=True):
            st.subheader("Ranking de municipios por votos")
            st.dataframe(
                terr_mun_geo[["NM_MUNICIPIO", "votos_candidato", "pct_votos_validos_territorio", "colocacao"]]
                .sort_values("votos_candidato", ascending=False),
                use_container_width=True, height=400,
            )

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
        if _eh_municipal:
            with st.spinner("Cruzando com o Censo 2022 (IBGE)..."):
                _, enriquecido_demo, _ = _geo_secao()
                perfil_setor, base_territorio = _demo(enriquecido_demo)
            _explicacao_demografia = (
                "Perfil demografico por secao eleitoral, a partir do setor censitario onde o "
                "local de votacao correspondente fica fisicamente localizado (fonte: Censo "
                "Demografico 2022, IBGE). Secoes do mesmo local de votacao compartilham o "
                "mesmo perfil (mesma coordenada) - variam apenas nos votos do candidato."
            )
        elif _modo_estadual == "bairro":
            with st.spinner(f"Cruzando {_municipio_bairro_nome} com o Censo 2022 (IBGE)..."):
                _, enriquecido_secao_uf_demo, avisos_bairro_demo = _geo_uf_secao()
                for aviso in avisos_bairro_demo:
                    st.warning(aviso)
                enriquecido_demo = enriquecido_secao_uf_demo[
                    enriquecido_secao_uf_demo["CD_MUNICIPIO"] == _municipio_bairro_codigo
                ].reset_index(drop=True)
                perfil_setor, base_territorio = _carregar_demografia(
                    candidatura.numero, _municipio_bairro_codigo, candidatura.cargo,
                    candidatura.ano_eleicao, candidatura.turno, enriquecido_demo, vd,
                )
            _explicacao_demografia = (
                f"Perfil demografico por secao eleitoral, restrito a {_municipio_bairro_nome} "
                f"(UF {candidatura.uf}) - mesmo detalhamento usado para Prefeito/Vereador (2024), "
                "aplicado aos votos deste candidato estadual dentro deste municipio."
            )
        else:
            with st.spinner(f"Cruzando a UF {candidatura.uf} inteira com o Censo 2022 (IBGE)..."):
                _, enriquecido_demo, avisos_demo_uf = _geo_uf()
                for aviso in avisos_demo_uf:
                    st.warning(aviso)
                perfil_setor, base_territorio = _demo_uf(enriquecido_demo)
            _explicacao_demografia = (
                f"Perfil demografico por MUNICIPIO (media ponderada pelos votos do candidato "
                f"dentro de cada municipio) - UF {candidatura.uf} inteira, a partir do setor "
                "censitario de cada local de votacao (fonte: Censo Demografico 2022, IBGE)."
            )

        if base_territorio.empty:
            st.info("Nao foi possivel montar o perfil demografico por territorio.")
        else:
            _explicacao(_explicacao_demografia)
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

# =============================================== Perfil do Eleitorado (TSE)
elif secao == "Perfil do Eleitorado (TSE)":
    st.warning(LIMITACAO_VINTAGE)
    _explicacao(
        "Perfil do eleitorado (genero, faixa etaria, escolaridade) por secao eleitoral - "
        "fonte TSE (Portal de Dados Abertos, dataset 'Eleitorado Atual'), DIFERENTE do Censo "
        "IBGE usado na aba Demografia. Baixado e convertido sob demanda na primeira vez "
        "(pode levar ate 1 minuto em UFs grandes, cacheado depois)."
    )
    with st.spinner(f"Baixando/convertendo perfil do eleitorado da UF {candidatura.uf}..."):
        perfil_uf_eleitorado = _carregar_perfil_eleitorado_uf(candidatura.uf)

    if perfil_uf_eleitorado.empty:
        st.info("Dados de perfil do eleitorado indisponiveis para esta UF.")
    else:
        if _eh_municipal:
            nivel_eleitorado = "NR_ZONA"
            terr_eleitorado = desempenho_territorial(candidatura, vc, vd, rd, nivel_eleitorado)
            perfil_terr_eleitorado = perfil_eleitorado_por_territorio(
                perfil_uf_eleitorado, candidatura.codigo_municipio_tse, nivel_eleitorado
            )
        else:
            nivel_eleitorado = "CD_MUNICIPIO"
            terr_eleitorado = desempenho_territorial(candidatura, vc, vd, rd, nivel_eleitorado)
            terr_eleitorado = terr_eleitorado.merge(
                vd[["CD_MUNICIPIO", "NM_MUNICIPIO"]].drop_duplicates(), on="CD_MUNICIPIO", how="left"
            )
            perfil_terr_eleitorado = perfil_eleitorado_por_territorio(perfil_uf_eleitorado, None, nivel_eleitorado)

        comparativo = comparar_eleitorado_vs_votos_candidato(perfil_terr_eleitorado, terr_eleitorado, nivel_eleitorado)
        if comparativo.empty:
            st.info("Nao foi possivel cruzar o perfil do eleitorado com o desempenho territorial.")
        else:
            total_eleitores = perfil_terr_eleitorado["qt_eleitores_total"].sum()
            pct_jovens_uf = round(100 * perfil_terr_eleitorado["qt_eleitores_jovens"].sum() / total_eleitores, 2) if total_eleitores else None
            pct_60mais_uf = round(100 * perfil_terr_eleitorado["qt_eleitores_60mais"].sum() / total_eleitores, 2) if total_eleitores else None
            pct_superior_uf = round(100 * perfil_terr_eleitorado["qt_eleitores_superior"].sum() / total_eleitores, 2) if total_eleitores else None
            pct_feminino_uf = round(100 * perfil_terr_eleitorado["qt_eleitores_feminino"].sum() / total_eleitores, 2) if total_eleitores else None

            c1, c2, c3, c4 = st.columns(4)
            _kpi(c1, "Eleitores 16-24 anos", f"{pct_jovens_uf}%" if pct_jovens_uf is not None else "n/d")
            _kpi(c2, "Eleitores 60+ anos", f"{pct_60mais_uf}%" if pct_60mais_uf is not None else "n/d")
            _kpi(c3, "Com ensino superior", f"{pct_superior_uf}%" if pct_superior_uf is not None else "n/d")
            _kpi(c4, "Eleitorado feminino", f"{pct_feminino_uf}%" if pct_feminino_uf is not None else "n/d")

            with st.container(border=True):
                st.subheader("Perfil do eleitorado vs. desempenho do candidato, por territorio")
                st.dataframe(
                    comparativo.sort_values("votos_candidato", ascending=False),
                    use_container_width=True, height=400,
                )

            with st.container(border=True):
                st.subheader("Correlacao: perfil do eleitorado x desempenho territorial")
                _explicacao(
                    "So descritivo - NAO alimenta a regressao/clusterizacao da aba Estatistica "
                    "Avancada, que usa exclusivamente variaveis do Censo IBGE."
                )
                variaveis_eleitorado = [
                    "pct_eleitores_jovens", "pct_eleitores_60mais",
                    "pct_eleitores_superior", "pct_eleitores_feminino",
                ]
                corr_eleitorado, issues_corr_eleitorado = correlacoes_com_votos(
                    comparativo, "pct_votos_validos_territorio", variaveis_eleitorado
                )
                for issue in issues_corr_eleitorado:
                    st.warning(issue.mensagem)
                if not corr_eleitorado.empty:
                    st.dataframe(corr_eleitorado, use_container_width=True)

# ======================================================= Estatistica Avancada
elif secao == "Estatistica Avancada":
    if not uf_tem_malha_completa(candidatura.uf):
        st.info(f"Malha geografica nao configurada para a UF '{candidatura.uf}'.")
    else:
        _regressao_geral_estadual = False
        _granularidade_geral = None
        _usar_covariaveis_municipio = False
        if not _eh_municipal and _modo_estadual == "municipio":
            _modo_regressao_label = st.radio(
                "Tipo de analise estatistica",
                ["Regressao por Municipio", "Regressao Geral (zona/secao, UF inteira)"],
                horizontal=True, key="v2_modo_regressao_estadual",
            )
            _regressao_geral_estadual = _modo_regressao_label.startswith("Regressao Geral")
            if _regressao_geral_estadual:
                _explicacao(
                    "A 'Regressao por Municipio' pode falhar em UFs com poucos municipios "
                    "(amostra pequena demais). A 'Regressao Geral' usa zona ou secao "
                    "eleitoral (UF inteira) como unidade de observacao - muito mais "
                    "observacoes - e o municipio entra como fator via erro-padrao robusto "
                    "a cluster (e, opcionalmente, como covariavel de porte)."
                )
                _granularidade_geral = st.radio(
                    "Unidade de observacao", ["Zona eleitoral", "Secao eleitoral"],
                    horizontal=True, key="v2_granularidade_geral",
                )
                _usar_covariaveis_municipio = st.checkbox(
                    "Incluir populacao e votos validos do municipio como variaveis",
                    key="v2_covariaveis_municipio",
                )

        nivel_geral = None
        with st.spinner("Calculando correlacoes, regressoes e clusterizacao..."):
            if _eh_municipal:
                _, enriquecido_est, _ = _geo_secao()
                perfil_setor, base_territorio = _demo(enriquecido_est)
            elif _modo_estadual == "bairro":
                _, enriquecido_est_uf, avisos_est_bairro = _geo_uf_secao()
                for aviso in avisos_est_bairro:
                    st.warning(aviso)
                enriquecido_est = enriquecido_est_uf[
                    enriquecido_est_uf["CD_MUNICIPIO"] == _municipio_bairro_codigo
                ].reset_index(drop=True)
                perfil_setor, base_territorio = _carregar_demografia(
                    candidatura.numero, _municipio_bairro_codigo, candidatura.cargo,
                    candidatura.ano_eleicao, candidatura.turno, enriquecido_est, vd,
                )
            elif _regressao_geral_estadual:
                _, enriquecido_est_uf, avisos_est = _geo_uf_secao()
                for aviso in avisos_est:
                    st.warning(aviso)
                enriquecido_est = enriquecido_est_uf.copy()
                if _granularidade_geral == "Zona eleitoral":
                    enriquecido_est["zona_uf_composta"] = zona_uf_composta(enriquecido_est)
                    nivel_geral = "zona_uf_composta"
                else:
                    nivel_geral = "secao_id"
                perfil_setor, base_territorio = _carregar_demografia_estadual_generica(
                    candidatura.numero, candidatura.uf, candidatura.cargo,
                    candidatura.ano_eleicao, candidatura.turno, enriquecido_est, vd, nivel_geral,
                )
                if _usar_covariaveis_municipio and not base_territorio.empty:
                    pop_municipio = agregados_populacionais_municipio(enriquecido_est, perfil_setor)
                    votos_municipio = total_votos_validos_por_territorio(
                        vd, enriquecido_est, "CD_MUNICIPIO"
                    ).rename(columns={"votos_validos_territorio": "votos_validos_municipio"})
                    base_territorio = base_territorio.merge(
                        pop_municipio, on="CD_MUNICIPIO", how="left"
                    ).merge(votos_municipio, on="CD_MUNICIPIO", how="left")
            else:
                _, enriquecido_est, avisos_est = _geo_uf()
                for aviso in avisos_est:
                    st.warning(aviso)
                perfil_setor, base_territorio = _demo_uf(enriquecido_est)

        if not _eh_municipal and _modo_estadual == "bairro" and not base_territorio.empty:
            _explicacao(
                f"Unidade de observacao: secao eleitoral, restrito a {_municipio_bairro_nome} "
                f"(UF {candidatura.uf}) - {len(base_territorio)} secoes."
            )
        elif _regressao_geral_estadual and not base_territorio.empty:
            _unidade_geral = "zona eleitoral" if nivel_geral == "zona_uf_composta" else "secao eleitoral"
            _n_municipios_geral = base_territorio["CD_MUNICIPIO"].nunique() if "CD_MUNICIPIO" in base_territorio else 0
            _explicacao(
                f"Unidade de observacao: {_unidade_geral} (UF {candidatura.uf} inteira, "
                f"{len(base_territorio)} observacoes, {_n_municipios_geral} municipios) - "
                "Regressao Geral."
            )
            if nivel_geral == "zona_uf_composta" and len(base_territorio) < 150:
                st.warning(
                    f"Esta UF tem poucas zonas eleitorais ({len(base_territorio)} zonas para "
                    f"{_n_municipios_geral} municipios) - em estados pequenos, uma zona eleitoral "
                    "costuma cobrir 1 unico municipio, entao o numero de observacoes fica quase "
                    "igual ao da 'Regressao por Municipio' e a regressao ainda pode falhar por "
                    "amostra insuficiente. Tente **Secao eleitoral** (muito mais observacoes, "
                    "cobre o mesmo problema de amostra pequena)."
                )
        elif not _eh_municipal and not base_territorio.empty:
            _explicacao(
                f"Unidade de observacao: MUNICIPIO (UF {candidatura.uf} inteira, "
                f"{len(base_territorio)} municipios) - nao secao/local de votacao, que so "
                "faz sentido dentro de 1 municipio."
            )

        if base_territorio.empty:
            st.info("Dados insuficientes para analise estatistica territorial.")
        else:
            variaveis_disp = [v for v in VARIAVEIS_DEMOGRAFICAS if v in base_territorio.columns]
            if _usar_covariaveis_municipio:
                variaveis_disp += [
                    v for v in ["populacao_total_municipio", "votos_validos_municipio"]
                    if v in base_territorio.columns
                ]

            _coluna_cluster_ativa = _COLUNA_CLUSTER_REGRESSAO
            if _regressao_geral_estadual:
                _coluna_cluster_ativa = (
                    ["local_votacao_id", "CD_MUNICIPIO"] if nivel_geral == "secao_id"
                    else ["CD_MUNICIPIO"]
                )
                _n_municipios_dummy = base_territorio["CD_MUNICIPIO"].nunique() if "CD_MUNICIPIO" in base_territorio else 0
                if 0 < _n_municipios_dummy <= 30:
                    _usar_dummy_municipio = st.checkbox(
                        "Incluir municipio como variavel dummy completa (1 coluna por "
                        f"municipio - disponivel porque esta UF tem so {_n_municipios_dummy} "
                        "municipios, limite de 30)",
                        key="v2_dummy_municipio",
                    )
                    if _usar_dummy_municipio:
                        # pd.get_dummies gera colunas dtype bool - misturado com as
                        # colunas float das demais variaveis, o statsmodels rejeita
                        # o DataFrame inteiro ("Pandas data cast to numpy dtype of
                        # object"). astype(int) evita o dtype misto.
                        _dummies_municipio = pd.get_dummies(
                            base_territorio[["CD_MUNICIPIO"]].astype(str), prefix="mun", drop_first=True
                        ).astype(int)
                        base_territorio = pd.concat([base_territorio, _dummies_municipio], axis=1)
                        variaveis_disp += list(_dummies_municipio.columns)

            nivel_estatistica = (
                nivel_geral if _regressao_geral_estadual
                else "CD_MUNICIPIO" if (not _eh_municipal and _modo_estadual == "municipio")
                else _NIVEL_TERRITORIO_DEMOGRAFICO
            )

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
                    coluna_cluster=_coluna_cluster_ativa,
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
                    coluna_cluster=_coluna_cluster_ativa,
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
                                nivel_estatistica,
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
                        resultado_clustering, modelo_log, nivel_estatistica, "votos_candidato",
                    )
                    if not potencial.empty:
                        st.plotly_chart(
                            charts.grafico_bairros_potencial(potencial, nivel_estatistica),
                            use_container_width=True,
                        )
                        st.dataframe(potencial, use_container_width=True)
                    else:
                        st.info("Nenhum territorio abaixo da media do proprio cluster foi encontrado.")
                else:
                    st.info("Segmentacao de clusters indisponivel - potencial nao calculado.")

            with st.container(border=True):
                st.subheader("Cenarios de votos (simulacao de Monte Carlo)")
                _explicacao(
                    "Sorteia repetidamente os coeficientes reais da regressao linear acima "
                    "(distribuicao Normal em torno de cada coeficiente e seu proprio erro-padrao "
                    "ja estimado) e aplica aos territorios de maior potencial - gera uma faixa "
                    "conservador/mediano/otimista que reflete a INCERTEZA ESTATISTICA real do "
                    "modelo, nao uma previsao de turnout futuro ou de comportamento de rivais."
                )
                if reg and resultado_clustering and not potencial.empty:
                    sim = simular_regressao_linear(reg, base_territorio, nivel_estatistica, n_simulacoes=2000)
                    if sim is None:
                        st.info("Nao foi possivel simular (variaveis do modelo indisponiveis nos dados).")
                    else:
                        territorios_potencial = base_territorio[
                            base_territorio[nivel_estatistica].isin(potencial[nivel_estatistica])
                        ]
                        cenario = cenario_agregado_votos(
                            sim, territorios_potencial, nivel_estatistica, "votos_validos_territorio",
                        )
                        if cenario:
                            c1, c2, c3, c4 = st.columns(4)
                            _kpi(c1, "Votos reais hoje (nesses territorios)", _fmt(cenario.votos_reais_atuais))
                            _kpi(c2, "Cenario conservador (p5)", _fmt(cenario.conservador))
                            _kpi(c3, "Cenario mediano (p50)", _fmt(cenario.mediano))
                            _kpi(c4, "Cenario otimista (p95)", _fmt(cenario.otimista))
                            st.caption(f"{cenario.n_territorios} territorios de maior potencial, {sim.n_simulacoes} simulacoes.")
                        sim_potencial = sim.territorios[sim.territorios[nivel_estatistica].isin(potencial[nivel_estatistica])]
                        st.dataframe(sim_potencial, use_container_width=True)
                        st.caption(sim.limitacoes)
                else:
                    st.info("Regressao linear, clusters e territorios de potencial precisam estar disponiveis para simular cenarios.")

# ===================================================== Abordagem de Maslow
elif secao == "Abordagem de Maslow":
    if not uf_tem_malha_completa(candidatura.uf):
        st.info(f"Malha geografica nao configurada para a UF '{candidatura.uf}'.")
    else:
        with st.spinner("Recalculando modelos estatisticos para aplicar a lente de Maslow..."):
            if _eh_municipal:
                _, enriquecido_maslow, _ = _geo_secao()
                perfil_setor, base_territorio = _demo(enriquecido_maslow)
            elif _modo_estadual == "bairro":
                _, enriquecido_maslow_uf, avisos_maslow_bairro = _geo_uf_secao()
                for aviso in avisos_maslow_bairro:
                    st.warning(aviso)
                enriquecido_maslow = enriquecido_maslow_uf[
                    enriquecido_maslow_uf["CD_MUNICIPIO"] == _municipio_bairro_codigo
                ].reset_index(drop=True)
                perfil_setor, base_territorio = _carregar_demografia(
                    candidatura.numero, _municipio_bairro_codigo, candidatura.cargo,
                    candidatura.ano_eleicao, candidatura.turno, enriquecido_maslow, vd,
                )
            else:
                _, enriquecido_maslow, avisos_maslow = _geo_uf()
                for aviso in avisos_maslow:
                    st.warning(aviso)
                perfil_setor, base_territorio = _demo_uf(enriquecido_maslow)

        if not _eh_municipal and _modo_estadual == "bairro" and not base_territorio.empty:
            _explicacao(
                f"Unidade de observacao: secao eleitoral, restrito a {_municipio_bairro_nome} "
                f"(UF {candidatura.uf})."
            )
        elif not _eh_municipal and not base_territorio.empty:
            _explicacao(
                f"Unidade de observacao: MUNICIPIO (UF {candidatura.uf} inteira, "
                f"{len(base_territorio)} municipios)."
            )

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

# ==================================================== Comparacao de Turnos
elif secao == "Comparacao de Turnos":
    _explicacao(
        "Compara o desempenho do candidato entre 1o e 2o turno: variacao "
        "absoluta/percentual de votos, mudanca na % de votos validos, "
        "territorios onde o candidato passou a liderar ou deixou de liderar "
        "(nao um limiar arbitrario - mudanca real de 1o lugar no territorio), "
        "e variacao do comparecimento quando disponivel."
    )
    _nivel_2t = "CD_MUNICIPIO" if not _eh_municipal else st.session_state.get("nivel_territorial", "NR_ZONA")

    with st.spinner("Carregando dados do 1o e 2o turno..."):
        _terr_t1 = _carregar_territorial_turno(
            veio_do_fallback, candidatura.ano_eleicao, candidatura.cargo, candidatura.uf,
            candidatura.codigo_municipio_tse, 1, candidatura.numero, _nivel_2t,
        )
        _terr_t2 = _carregar_territorial_turno(
            veio_do_fallback, candidatura.ano_eleicao, candidatura.cargo, candidatura.uf,
            candidatura.codigo_municipio_tse, 2, candidatura.numero, _nivel_2t,
        )

    if _terr_t1 is None or _terr_t2 is None:
        st.info(
            "Nao ha comparacao para mostrar: este candidato nao tem candidatura "
            "registrada em um dos dois turnos (a maioria das disputas de "
            "Prefeito/Governador no Brasil nao vai a 2o turno, e mesmo quando "
            "vai, so os 2 primeiros colocados do 1o turno avancam)."
        )
    else:
        comp_turnos = comparar_turnos(_terr_t1, _terr_t2, _nivel_2t)

        c1, c2, c3, c4 = st.columns(4)
        _kpi(c1, "Votos 1o turno", _fmt(comp_turnos.votos_turno1))
        _kpi(c2, "Votos 2o turno", _fmt(comp_turnos.votos_turno2))
        _kpi(
            c3, "Variacao absoluta", f"{comp_turnos.variacao_absoluta:+,}".replace(",", "."),
            tom="bom" if comp_turnos.variacao_absoluta >= 0 else "ruim",
        )
        _kpi(
            c4, "Variacao percentual", f"{comp_turnos.variacao_percentual:+.2f}%",
            tom="bom" if comp_turnos.variacao_percentual >= 0 else "ruim",
        )

        c5, c6 = st.columns(2)
        _kpi(c5, "% votos validos - 1o turno", f"{comp_turnos.pct_validos_turno1}%")
        _kpi(c6, "% votos validos - 2o turno", f"{comp_turnos.pct_validos_turno2}%")

        with st.container(border=True):
            st.subheader("Territorios conquistados e perdidos entre os turnos")
            cc1, cc2 = st.columns(2)
            with cc1:
                st.metric("Territorios conquistados", len(comp_turnos.territorios_conquistados))
                if comp_turnos.territorios_conquistados:
                    amostra = ", ".join(str(t) for t in comp_turnos.territorios_conquistados[:20])
                    st.caption(amostra + (" ..." if len(comp_turnos.territorios_conquistados) > 20 else ""))
            with cc2:
                st.metric("Territorios perdidos", len(comp_turnos.territorios_perdidos))
                if comp_turnos.territorios_perdidos:
                    amostra = ", ".join(str(t) for t in comp_turnos.territorios_perdidos[:20])
                    st.caption(amostra + (" ..." if len(comp_turnos.territorios_perdidos) > 20 else ""))

        if comp_turnos.variacao_comparecimento_pct is not None:
            with st.container(border=True):
                st.subheader("Comparecimento")
                st.metric("Variacao do comparecimento", f"{comp_turnos.variacao_comparecimento_pct:+.2f}%")

        with st.container(border=True):
            st.subheader("Detalhamento por territorio")
            st.dataframe(
                comp_turnos.detalhe_territorial.sort_values("delta_votos", ascending=False),
                use_container_width=True, height=400,
            )

# =============================================================== Comparativo
elif secao == "Comparativo":
    _explicacao(
        f"Comparacao lado a lado entre {candidatura.nome_urna} e {candidatura_b.nome_urna} - "
        "mesma disputa (mesmo ano/cargo/UF/turno). Metricas gerais reaproveitam resultado_geral; "
        "o perfil demografico dos redutos reaproveita o mesmo pipeline de Geografia/Demografia."
    )
    cA, cB = st.columns(2)
    with cA, st.container(border=True):
        st.markdown(f"### {candidatura.nome_urna} ({candidatura.numero})")
        st.metric("Total de votos", _fmt(rg.total_votos))
        st.metric("Colocacao geral", f"{rg.colocacao_geral}o de {rg.total_concorrentes}")
        st.metric("% votos validos", f"{rg.pct_votos_validos}%")
    with cB, st.container(border=True):
        st.markdown(f"### {candidatura_b.nome_urna} ({candidatura_b.numero})")
        st.metric("Total de votos", _fmt(rg_b.total_votos))
        st.metric("Colocacao geral", f"{rg_b.colocacao_geral}o de {rg_b.total_concorrentes}")
        st.metric("% votos validos", f"{rg_b.pct_votos_validos}%")

    with st.spinner("Calculando perfil demografico dos redutos de cada candidato..."):
        if _eh_municipal:
            _, enriquecido_a_comp, _ = _carregar_geografia_secao(
                candidatura.numero, candidatura.codigo_municipio_tse, candidatura.cargo,
                candidatura.ano_eleicao, candidatura.turno, candidatura, vc,
            )
            _, base_territorio_a_comp = _carregar_demografia(
                candidatura.numero, candidatura.codigo_municipio_tse, candidatura.cargo,
                candidatura.ano_eleicao, candidatura.turno, enriquecido_a_comp, vd,
            )
            _, enriquecido_b_comp, _ = _carregar_geografia_secao(
                candidatura_b.numero, candidatura_b.codigo_municipio_tse, candidatura_b.cargo,
                candidatura_b.ano_eleicao, candidatura_b.turno, candidatura_b, vc_b,
            )
            _, base_territorio_b_comp = _carregar_demografia(
                candidatura_b.numero, candidatura_b.codigo_municipio_tse, candidatura_b.cargo,
                candidatura_b.ano_eleicao, candidatura_b.turno, enriquecido_b_comp, vd,
            )
        else:
            _, enriquecido_a_comp, _ = _carregar_geografia_estadual(
                candidatura.numero, candidatura.uf, candidatura.cargo,
                candidatura.ano_eleicao, candidatura.turno, candidatura, vc,
            )
            _, base_territorio_a_comp = _carregar_demografia_estadual(
                candidatura.numero, candidatura.uf, candidatura.cargo,
                candidatura.ano_eleicao, candidatura.turno, enriquecido_a_comp, vd,
            )
            _, enriquecido_b_comp, _ = _carregar_geografia_estadual(
                candidatura_b.numero, candidatura_b.uf, candidatura_b.cargo,
                candidatura_b.ano_eleicao, candidatura_b.turno, candidatura_b, vc_b,
            )
            _, base_territorio_b_comp = _carregar_demografia_estadual(
                candidatura_b.numero, candidatura_b.uf, candidatura_b.cargo,
                candidatura_b.ano_eleicao, candidatura_b.turno, enriquecido_b_comp, vd,
            )

    if base_territorio_a_comp.empty or base_territorio_b_comp.empty:
        st.info("Nao foi possivel montar o perfil demografico comparativo dos redutos.")
    else:
        with st.container(border=True):
            st.subheader("Perfil demografico medio dos 5 maiores redutos de cada candidato")
            comparativo_perfil = perfil_comparativo_dois_candidatos(
                base_territorio_a_comp, base_territorio_b_comp, VARIAVEIS_DEMOGRAFICAS, top_n=5,
            )
            if comparativo_perfil.empty:
                st.info("Sem variaveis demograficas em comum para comparar.")
            else:
                st.dataframe(
                    comparativo_perfil.rename(columns={
                        "media_candidato_a": candidatura.nome_urna, "media_candidato_b": candidatura_b.nome_urna,
                    }),
                    use_container_width=True, height=350,
                )

# ================================================================ Relatorio
elif secao == "Relatorio":
    st.write("Gere o relatorio executivo ou exporte os dados desta candidatura.")
    nivel_relatorio = "CD_MUNICIPIO" if not _eh_municipal else st.session_state.get("nivel_territorial", "NR_ZONA")
    # Cargos estaduais/distritais nao tem "bairro" - o territorio de
    # analise para clustering/regressao/potencial e o MUNICIPIO (UF
    # inteira), mesmo nivel ja usado e validado nas secoes "Concorrencia"
    # (IDP/IVE/IEC/QEC) e "Estatistica Avancada" (modo Municipio) para
    # candidaturas estaduais - nunca o drill-down por bairro de 1
    # municipio (isso continua so nas secoes de exploracao ad-hoc).
    _nivel_potencial_rel = _NIVEL_TERRITORIO_DEMOGRAFICO if _eh_municipal else "CD_MUNICIPIO"
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
    reg_pct_rel = None
    simulacao_mc_rel = None
    cenario_mc_rel = None

    if uf_tem_malha_completa(candidatura.uf):
        if _eh_municipal:
            pontos, enriquecido, avisos_geo = _geo()
            limitacoes = list(avisos_geo)
            bairros_agg_rel = agregar_votos_por_bairro(enriquecido)
            _, enriquecido_secao_rel, _ = _geo_secao()
            _, base_territorio_rel = _demo(enriquecido_secao_rel)
        else:
            _, enriquecido_uf_rel, avisos_geo = _geo_uf()
            limitacoes = list(avisos_geo)
            terr_mun_rel = desempenho_territorial(candidatura, vc, vd, rd, "CD_MUNICIPIO")
            terr_mun_rel = terr_mun_rel.merge(
                vd[["CD_MUNICIPIO", "NM_MUNICIPIO"]].drop_duplicates(), on="CD_MUNICIPIO", how="left"
            )
            bairros_agg_rel = terr_mun_rel.rename(columns={"NM_MUNICIPIO": "municipio"})[
                ["municipio", "votos_candidato", "pct_votos_validos_territorio", "colocacao"]
            ].sort_values("votos_candidato", ascending=False).reset_index(drop=True)
            _, base_territorio_rel = _demo_uf(enriquecido_uf_rel)
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
                    resultado_clustering_rel, modelo_log_rel, _nivel_potencial_rel, "votos_candidato",
                )
            modelo_lin_rel = None
            if modelo_log_rel is None:
                modelo_lin_rel, _ = regressao_linear_votos(
                    base_territorio_rel, "votos_candidato", variaveis_disp,
                    coluna_cluster=_COLUNA_CLUSTER_REGRESSAO,
                )
            resultado_maslow_rel = gerar_analise_maslow(modelo_log_rel, modelo_lin_rel, corr_rel)

            # regressao linear (percentual) + simulacao de Monte Carlo -
            # sempre calculada aqui (independente do fallback de Maslow
            # acima, que so roda o modelo linear quando o logistico falha)
            # porque o cenario de votos (Etapa 8) precisa especificamente
            # do modelo linear para converter % simulado em votos reais.
            reg_pct_rel, _ = regressao_linear_votos(
                base_territorio_rel, "pct_votos_validos_territorio", variaveis_disp,
                coluna_cluster=_COLUNA_CLUSTER_REGRESSAO,
            )
            if reg_pct_rel is not None:
                simulacao_mc_rel = simular_regressao_linear(reg_pct_rel, base_territorio_rel, _nivel_potencial_rel)
                if simulacao_mc_rel is not None:
                    cenario_mc_rel = cenario_agregado_votos(
                        simulacao_mc_rel, base_territorio_rel, _nivel_potencial_rel, "votos_validos_territorio",
                    )
    else:
        limitacoes = [f"Malha geografica nao configurada para a UF '{candidatura.uf}'."]

    rivais_sim_rel, _ = rivais_por_similaridade_eleitorado(candidatura, vd, rd, nivel_relatorio, top_n=3)

    terr_rel = desempenho_territorial(candidatura, vc, vd, rd, nivel_relatorio)
    hhi_rel = indice_concentracao_hhi(terr_rel)
    terr_class_rel = zonas_de_disputa(terr_rel, vd, rd, candidatura, nivel_relatorio)
    indice_terr_rel = calcular_indice_performance(terr_class_rel, hhi_rel)
    matriz_rel = matriz_candidato_territorio(candidatura, vd, ranking, nivel_relatorio, top_n_concorrentes=3)
    delta_rel = delta_vs_rivais(matriz_rel, nivel_relatorio, candidatura.nome_urna)
    ranking_partidos_rel = ranking_partidos(ranking, vd, rd)
    concentracao_rel = calcular_concentracao_territorial(terr_rel)
    patrimonio_comparativo_rel = patrimonio_comparativo(candidatura, ranking, top_n=7)
    comparativo_historico_rel = montar_comparativo_historico(candidatura, vc, vd, rd)

    figuras = {
        "Ranking da disputa": charts.grafico_ranking_disputa(ranking, candidatura.numero),
        f"Votos por {nivel_relatorio}": charts.grafico_votos_por_territorio(terr_rel, nivel_relatorio),
    }
    if not rivais_sim_rel.empty:
        figuras["Rivais por similaridade de base eleitoral"] = charts.grafico_rivais_similaridade(rivais_sim_rel)
    if potencial_rel is not None and not potencial_rel.empty:
        figuras["Territorios com maior potencial"] = charts.grafico_bairros_potencial(potencial_rel, _nivel_potencial_rel)
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
        ranking_partidos=ranking_partidos_rel, concentracao_territorial=concentracao_rel,
        zonas_disputa=terr_class_rel, regressao_linear=reg_pct_rel,
        cenario_monte_carlo=cenario_mc_rel, simulacao_monte_carlo=simulacao_mc_rel,
        patrimonio_comparativo=patrimonio_comparativo_rel,
        comparativo_historico=comparativo_historico_rel,
    )

    # Cargos estaduais/distritais nao tem codigo de municipio (candidatura
    # cobre a UF inteira) - usa a UF como sufixo do nome de arquivo nesse
    # caso, em vez de literalmente escrever "None" no nome baixado.
    _sufixo_arquivo_rel = candidatura.codigo_municipio_tse if candidatura.codigo_municipio_tse is not None else candidatura.uf

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        html_bytes = gerar_relatorio_html(dados_relatorio).encode("utf-8")
        st.download_button("Baixar relatorio HTML", html_bytes, file_name=f"relatorio_{candidatura.nome_urna}.html")
    with col2:
        pdf_path = resolve_path(f"outputs/reports/relatorio_{candidatura.numero}_{_sufixo_arquivo_rel}.pdf")
        gerar_relatorio_pdf(dados_relatorio, pdf_path)
        st.download_button("Baixar relatorio PDF", pdf_path.read_bytes(), file_name=pdf_path.name)
    with col3:
        completo_bytes = gerar_relatorio_completo_html(dados_relatorio).encode("utf-8")
        st.download_button(
            "Baixar relatorio completo (rico)", completo_bytes,
            file_name=f"relatorio_completo_{candidatura.nome_urna}.html",
        )
    with col4:
        estrategia_bytes = gerar_relatorio_estrategia_html(dados_relatorio).encode("utf-8")
        st.download_button(
            "Baixar relatorio de estrategia", estrategia_bytes,
            file_name=f"relatorio_estrategia_{candidatura.nome_urna}.html",
        )
    with col5:
        comparativo_bytes = gerar_relatorio_comparativo_html(dados_relatorio).encode("utf-8")
        st.download_button(
            "Baixar relatorio comparativo", comparativo_bytes,
            file_name=f"relatorio_comparativo_{candidatura.nome_urna}.html",
        )
    with col6:
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
        xlsx_path = resolve_path(f"outputs/reports/dados_{candidatura.numero}_{_sufixo_arquivo_rel}.xlsx")
        exportar_excel(xlsx_path, planilhas)
        st.download_button("Baixar dados (Excel)", xlsx_path.read_bytes(), file_name=xlsx_path.name)

    col7, col8 = st.columns(2)
    with col7:
        estrategia_pdf_path = resolve_path(
            f"outputs/reports/relatorio_estrategia_{candidatura.numero}_{_sufixo_arquivo_rel}.pdf"
        )
        gerar_relatorio_estrategia_pdf(dados_relatorio, estrategia_pdf_path)
        st.download_button(
            "Baixar relatorio de estrategia (PDF)", estrategia_pdf_path.read_bytes(), file_name=estrategia_pdf_path.name,
        )
    with col8:
        comparativo_pdf_path = resolve_path(
            f"outputs/reports/relatorio_comparativo_{candidatura.numero}_{_sufixo_arquivo_rel}.pdf"
        )
        gerar_relatorio_comparativo_pdf(dados_relatorio, comparativo_pdf_path)
        st.download_button(
            "Baixar relatorio comparativo (PDF)", comparativo_pdf_path.read_bytes(), file_name=comparativo_pdf_path.name,
        )
