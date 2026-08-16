"""Host dedicado ao Questionario Completo de Novos Candidatos (SIET V2).

Segundo ponto de entrada do MESMO repositorio de `app.py` (nao e um projeto
separado - reaproveita `src/` inteiro, mesmo `requirements.txt`, mesmo
`config/`). Rodar local:

    .venv\\Scripts\\python.exe -m streamlit run app_candidatos.py --server.port 8541

Ou publicado no Streamlit Community Cloud como um 2o app apontando pro
mesmo repo, "Main file path" = app_candidatos.py.

Diferente de app.py (que tem 4 modos + o fluxo de candidatura real), este
host tem UMA pagina so: o questionario de autoavaliacao do Modulo Candidato
(Modo 1), agora COMPLETO (todas as 8 secoes do schema, incluindo a secao
Objetivos e os campos que existiam no schema mas nunca eram coletados no
app grande) mais uma ponte opcional para o questionario completo de pauta
(Modo 3) por cada pauta prioritaria marcada - em vez do miniformulario de 2
campos que a Matriz Integrada usa hoje. Ao final, salva a resposta (local +
commit no GitHub quando publicado) via src/questionnaire/persistence.py.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.uf_nomes import UF_NOME
from src.ui_helpers import (
    _CARGOS_MODO1,
    _explicacao,
    _fmt,
    _kpi,
    _nivel,
    _rotulo_classificacao,
    _simnao,
    _tom_indice,
    render_css,
)

from src.indicators.candidate_indices import calcular_indices_candidato
from src.profiles.candidate_archetype import classificar_arquetipo
from src.questionnaire.candidate_questionnaire import (
    BaseEleitoral,
    Comunicacao,
    IdentificacaoAnalise,
    NivelIntensidade,
    Objetivos,
    Posicionamento,
    Recursos,
    RespostaQuestionario,
    SimNao,
    Trajetoria,
)
from src.questionnaire.policy_questionnaire import PropostaPauta, pautas_disponiveis, policy_areas_config
from src.questionnaire.persistence import salvar_e_sincronizar

from src.indicators.policy_indices import calcular_indices_pauta
from src.profiles.policy_classification import classificar_pauta
from src.platforms.platform_builder import montar_plataforma, verificar_gate_competencia

from src.godfather_analysis import analisar_padrinho_politico
from src.territory_recommendations import montar_territorios_sugeridos
from src.parties.party_compatibility import avaliar_compatibilidade_partidaria
from src.rivals.hypothetical_rivals import identificar_rivais_projetados
from src.candidate_assets import carregar_patrimonio_candidato

st.set_page_config(page_title="SIET - Questionario de Novos Candidatos", layout="wide", page_icon="\U0001F5F3")

from src.cloud_data_bootstrap import garantir_dados_cloud  # noqa: E402

with st.spinner("Preparando dados (primeira execucao neste ambiente pode levar ~1 min)..."):
    _dados_ok = garantir_dados_cloud()
if not _dados_ok:
    st.error(
        "Nao foi possivel baixar o pacote de dados necessario. Verifique a "
        "conexao ou tente novamente em alguns minutos."
    )
    st.stop()

render_css()

_PAUTAS_LABELS = {pauta_id: dados["label"] for pauta_id, dados in policy_areas_config()["pautas"].items()}

_OPCOES_OBJETIVO_PRINCIPAL = {
    "-- nao respondido --": None,
    "Vencer a eleicao": "vencer",
    "Construir capital politico": "capital_politico",
    "Ganhar conhecimento/visibilidade": "conhecimento",
    "Construir base para eleicoes futuras": "base_futura",
    "Fortalecer o partido": "fortalecer_partido",
    "Representar uma pauta especifica": "representar_pauta",
}
_OPCOES_HORIZONTE = {
    "-- nao respondido --": None,
    "Esta eleicao": "esta_eleicao",
    "Proxima eleicao": "proxima_eleicao",
    "Longo prazo": "longo_prazo",
}

st.title("Questionario Completo de Novos Candidatos")
_explicacao(
    "Autoavaliacao estruturada - <strong>nao e dado eleitoral verificado</strong>, diferente do "
    "resto do SIET (calculado a partir de TSE/IBGE reais). Quanto mais completo, mais rica fica "
    "a analise: rivais projetados, compatibilidade partidaria e territorios sugeridos usam dado "
    "REAL do TSE/IBGE cruzado com o que voce responder aqui. Perguntas deixadas em "
    "\"-- nao respondido --\" ficam de fora do calculo de cada indice, e a cobertura de cada um "
    "aparece junto ao resultado - nunca e preenchida com estimativa. As respostas ficam salvas "
    "(ver aviso de sincronizacao ao final) para o SIET completo poder analisar depois."
)

# --------------------------------------------------------------- Formulario
with st.form("form_questionario_completo"):
    st.subheader("1. Identificacao da analise")
    c1, c2, c3 = st.columns(3)
    cargo_pretendido = c1.selectbox("Cargo pretendido", _CARGOS_MODO1, key="q_cargo")
    uf = c2.selectbox("UF", list(UF_NOME.keys()), key="q_uf")
    municipio_base = c3.text_input("Municipio-base", key="q_municipio")

    c4, c5, c6 = st.columns(3)
    with c4:
        cargo_definido = _simnao("Cargo ja definido (ou ainda em aberto)?", "q_cargo_definido")
    with c5:
        aceita_outros_cargos = _simnao("Aceitaria disputar outro cargo, se necessario?", "q_aceita_outros_cargos")
    with c6:
        aceita_outros_municipios = _simnao("Aceitaria mudar de municipio-base?", "q_aceita_outros_municipios")

    c7, c8, c9 = st.columns(3)
    with c7:
        possui_domicilio = _simnao("Ja possui domicilio eleitoral na UF/municipio acima?", "q_domicilio")
    with c8:
        partido_definido = _simnao("Partido definido?", "q_partido_definido")
    with c9:
        ja_disputou = _simnao("Ja disputou eleicao antes?", "q_ja_disputou")

    partido_sigla = st.text_input(
        "Sigla do partido (se definido)", key="q_partido_sigla",
        help="Usado para os rivais projetados e a compatibilidade partidaria abaixo - "
             "so preenche se 'Partido definido?' for Sim.",
    )
    c12, c13 = st.columns(2)
    with c12:
        possui_padrinho = _simnao("Possui padrinho politico?", "q_possui_padrinho")
    with c13:
        nome_padrinho = st.text_input(
            "Nome do padrinho politico (se houver)", key="q_nome_padrinho",
            help="So preenche se 'Possui padrinho politico?' for Sim. Vinculo de apadrinhamento "
                 "e fonte real de apoio, mas tambem risco de associacao (desgaste do padrinho "
                 "reflete no afilhado).",
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
            "Numero de bairros/cidades onde tem presenca organizada (deixe em branco se nao souber)",
            min_value=0, max_value=200, step=1, value=None, key="q_num_territorios",
        )
        estrutura_bairros = _nivel("Estrutura nos bairros/cidades de presenca", "q_estrutura_bairros")
        st.caption(
            "Essa nota (Estrutura nos bairros) e autoavaliacao geral, so usada nos indices do "
            "candidato - quem alimenta a sugestao real de territorio (abaixo) e a lista de "
            "'Bairros/regioes' logo adiante, cruzada com o Censo IBGE."
        )
        apoiadores_mobilizaveis = _nivel("Apoiadores mobilizaveis", "q_apoiadores")
        capacidade_eventos = _nivel("Capacidade de realizar eventos", "q_eventos")
        relacionamento_liderancas = _nivel("Relacionamento com liderancas comunitarias", "q_rel_liderancas")
        contexto_relacionamento_liderancas = st.text_input(
            "Contexto sobre o relacionamento com liderancas (opcional)", key="q_rel_liderancas_contexto",
            help="Texto livre complementar - nao entra em nenhum indice, so na narrativa da estrategia.",
        )
        relacionamento_vereadores = _nivel("Relacionamento com vereadores", "q_rel_vereadores")
        relacionamento_prefeitos = _nivel("Relacionamento com prefeitos", "q_rel_prefeitos")
        relacionamento_deputados = _nivel("Relacionamento com deputados", "q_rel_deputados")
        relacionamento_entidades = _nivel("Relacionamento com entidades/associacoes", "q_rel_entidades")
        liderancas_regionais = _nivel("Relacionamento com liderancas regionais", "q_liderancas_regionais")
        apoio_do_partido = _nivel("Apoio do partido a esta candidatura", "q_apoio_partido")
        bairros_presenca = st.text_input(
            "Bairros/regioes onde ja tem presenca, contato ou vinculo pessoal (separados por virgula)",
            key="q_bairros_presenca",
            help="Dado real declarado por voce - usado na secao 'Territorios e Pautas Sugeridas' "
                 "abaixo, junto com o perfil censitario real do IBGE, para sugerir onde priorizar campanha.",
        )

    with st.expander("4. Comunicacao"):
        conhecimento_espontaneo = _nivel(
            "Conhecimento espontaneo (eleitores que reconhecem o nome sem ajuda)", "q_conhecimento"
        )
        oratoria = _nivel("Oratoria", "q_oratoria")
        desempenho_videos = _nivel("Desempenho em videos", "q_videos")
        entrevistas = _nivel("Desempenho em entrevistas", "q_entrevistas")
        debates = _nivel("Desempenho em debates", "q_debates")
        resposta_criticas = _nivel("Resposta a criticas", "q_resp_criticas")
        seguidores_redes = st.number_input(
            "Numero total de seguidores nas redes sociais (some todas as redes, deixe em branco se nao souber)",
            min_value=0, step=100, value=None, key="q_seguidores",
        )
        engajamento = _nivel("Engajamento nas redes sociais", "q_engajamento")
        producao_conteudo = _nivel("Producao propria de conteudo", "q_conteudo")
        equipe_comunicacao = _nivel("Equipe de comunicacao", "q_equipe_com")
        rejeicao_percebida = _nivel("Rejeicao percebida (quanto maior, pior)", "q_rejeicao")

    with st.expander("5. Recursos"):
        disponibilidade_tempo = _nivel("Disponibilidade de tempo", "q_disp_tempo")
        capacidade_investimento_legal = _nivel("Capacidade de investimento legal proprio", "q_investimento")
        capacidade_arrecadacao = st.number_input(
            "Meta de arrecadacao de campanha em R$ (deixe em branco se nao souber)",
            min_value=0.0, step=1000.0, value=None, key="q_arrecadacao", format="%.2f",
        )
        patrimonio_pessoal = st.number_input(
            "Patrimonio pessoal ATUAL declarado em R$ (deixe em branco se nao souber)",
            min_value=0.0, step=1000.0, value=None, key="q_patrimonio",
            help="DIFERENTE da meta de arrecadacao acima (que e da CAMPANHA) - este e o patrimonio "
                 "pessoal seu, hoje. Usado so pra comparar contra o patrimonio REAL declarado ao TSE "
                 "pelos rivais projetados (abaixo) - nunca entra em nenhum indice.",
        )
        equipe = _nivel("Equipe disponivel", "q_equipe")
        transporte = _nivel("Transporte", "q_transporte")
        locais_reuniao = _nivel("Locais para reuniao", "q_locais")
        audiovisual = _nivel("Estrutura audiovisual", "q_audiovisual")
        disponibilidade_viagens = _nivel("Disponibilidade para viagens", "q_disp_viagens")

    with st.expander("6. Posicionamento"):
        temas = st.text_input("Temas de maior identificacao (separados por virgula)", key="q_temas")
        imagem_desejada = st.text_input("Imagem que deseja projetar (texto livre, opcional)", key="q_imagem_desejada")
        estilo_lideranca = st.text_input("Estilo de lideranca (texto livre, opcional)", key="q_estilo_lideranca")
        resistencia_ataques = _nivel("Resistencia a ataques/criticas publicas", "q_resistencia")
        disciplina = _nivel("Disciplina (agenda, partido, mensagem)", "q_disciplina")
        disposicao_negociacao = _nivel("Disposicao para negociacao politica", "q_disp_negociacao")
        disposicao_confronto = _nivel("Disposicao para confronto/embate publico", "q_disp_confronto")
        pautas_prioritarias = st.multiselect(
            "Pautas prioritarias (catalogo real de politica publica)",
            list(_PAUTAS_LABELS.keys()), format_func=lambda k: _PAUTAS_LABELS[k], key="q_pautas_prioritarias",
            help="Usado na secao 'Territorios e Pautas Sugeridas' abaixo. Depois de enviar este "
                 "formulario, cada pauta marcada aqui ganha um formulario proprio (opcional) para "
                 "detalhar de verdade - alimenta a Matriz Integrada com dado completo em vez do "
                 "miniformulario reduzido.",
        )

    with st.expander("7. Objetivos"):
        objetivo_principal_label = st.selectbox(
            "Objetivo principal desta candidatura", list(_OPCOES_OBJETIVO_PRINCIPAL.keys()), key="q_objetivo_principal",
        )
        horizonte_temporal_label = st.selectbox(
            "Horizonte temporal", list(_OPCOES_HORIZONTE.keys()), key="q_horizonte_temporal",
        )
        risco_aceito = _nivel("Nivel de risco aceito na estrategia", "q_risco_aceito")
        aceita_outro_cargo = _simnao("Aceitaria concorrer a outro cargo no futuro, mesmo perdendo este?", "q_aceita_outro_cargo_futuro")

    enviado = st.form_submit_button("Calcular e revisar", type="primary")

if enviado:
    st.session_state["cq_resposta"] = RespostaQuestionario(
        identificacao=IdentificacaoAnalise(
            cargo_pretendido=cargo_pretendido,
            uf=uf,
            municipio_base=municipio_base or "-- nao informado --",
            cargo_definido=cargo_definido if cargo_definido is not None else SimNao.SIM,
            aceita_outros_municipios=aceita_outros_municipios if aceita_outros_municipios is not None else SimNao.NAO,
            aceita_outros_cargos=aceita_outros_cargos if aceita_outros_cargos is not None else SimNao.NAO,
            partido_definido=partido_definido,
            partido_sigla=partido_sigla.strip().upper() if partido_definido == SimNao.SIM and partido_sigla.strip() else None,
            possui_domicilio_eleitoral=possui_domicilio if possui_domicilio is not None else SimNao.SIM,
            ja_disputou_eleicao=ja_disputou if ja_disputou is not None else SimNao.NAO,
            possui_padrinho_politico=possui_padrinho,
            nome_padrinho_politico=nome_padrinho.strip() if possui_padrinho == SimNao.SIM and nome_padrinho.strip() else None,
        ),
        trajetoria=Trajetoria(
            tempo_atuacao_publica=tempo_atuacao_publica, mandato_anterior=mandato_anterior,
            experiencia_politica_geral=experiencia_politica_geral, atuacao_administrativa=atuacao_administrativa,
            projetos_realizados=projetos_realizados, resultados_concretos=resultados_concretos,
        ),
        base_eleitoral=BaseEleitoral(
            numero_territorios_presenca=int(numero_territorios) if numero_territorios is not None else None,
            estrutura_bairros=estrutura_bairros, apoiadores_mobilizaveis=apoiadores_mobilizaveis,
            capacidade_eventos=capacidade_eventos, relacionamento_liderancas=relacionamento_liderancas,
            contexto_relacionamento_liderancas=contexto_relacionamento_liderancas.strip() or None,
            bairros_presenca_declarados=[b.strip() for b in bairros_presenca.split(",") if b.strip()],
            relacionamento_vereadores=relacionamento_vereadores, relacionamento_prefeitos=relacionamento_prefeitos,
            relacionamento_deputados=relacionamento_deputados, relacionamento_entidades=relacionamento_entidades,
            liderancas_regionais=liderancas_regionais, apoio_do_partido=apoio_do_partido,
        ),
        comunicacao=Comunicacao(
            conhecimento_espontaneo=conhecimento_espontaneo, oratoria=oratoria, desempenho_videos=desempenho_videos,
            entrevistas=entrevistas, debates=debates, resposta_criticas=resposta_criticas,
            seguidores_redes=seguidores_redes, engajamento=engajamento, producao_conteudo=producao_conteudo,
            equipe_comunicacao=equipe_comunicacao, rejeicao_percebida=rejeicao_percebida,
        ),
        recursos=Recursos(
            disponibilidade_tempo=disponibilidade_tempo, capacidade_investimento_legal=capacidade_investimento_legal,
            capacidade_arrecadacao=capacidade_arrecadacao, patrimonio_pessoal_declarado=patrimonio_pessoal,
            equipe=equipe, transporte=transporte, locais_reuniao=locais_reuniao, audiovisual=audiovisual,
            disponibilidade_viagens=disponibilidade_viagens,
        ),
        posicionamento=Posicionamento(
            temas_identificacao=[t.strip() for t in temas.split(",") if t.strip()],
            imagem_desejada=imagem_desejada.strip() or None, estilo_lideranca=estilo_lideranca.strip() or None,
            resistencia_ataques=resistencia_ataques, disciplina=disciplina,
            disposicao_negociacao=disposicao_negociacao, disposicao_confronto=disposicao_confronto,
            pautas_prioritarias=pautas_prioritarias,
        ),
        objetivos=Objetivos(
            objetivo_principal=_OPCOES_OBJETIVO_PRINCIPAL[objetivo_principal_label],
            horizonte_temporal=_OPCOES_HORIZONTE[horizonte_temporal_label],
            risco_aceito=risco_aceito,
            aceita_outro_cargo=aceita_outro_cargo if aceita_outro_cargo is not None else SimNao.NAO,
        ),
    )
    st.session_state["cq_propostas_pauta"] = {}
    st.session_state["cq_salvo"] = False

resposta: RespostaQuestionario | None = st.session_state.get("cq_resposta")
if resposta is None:
    st.stop()

# ---------------------------------------------------- Ponte Modo 1 -> Modo 3
if resposta.posicionamento.pautas_prioritarias:
    st.divider()
    st.subheader("Detalhar pautas prioritarias (opcional, recomendado)")
    _explicacao(
        "Cada pauta marcada acima pode ser detalhada aqui com o questionario completo de pauta "
        "(mesmo usado no Modo 3 do SIET) - isso alimenta a Matriz Integrada com dado completo, "
        "em vez do miniformulario reduzido de 2 campos que ela usa quando nao ha pauta detalhada."
    )
    propostas_pauta: dict = st.session_state.setdefault("cq_propostas_pauta", {})
    for pauta_id in resposta.posicionamento.pautas_prioritarias:
        label_pauta = _PAUTAS_LABELS.get(pauta_id, pauta_id)
        pronto = "✅ detalhada" if pauta_id in propostas_pauta else "— nao detalhada ainda"
        with st.expander(f"{label_pauta} ({pronto})"):
            with st.form(f"form_pauta_{pauta_id}"):
                problema_central = st.text_area("Problema central que a proposta pretende enfrentar", key=f"pp_problema_{pauta_id}")
                c1, c2 = st.columns(2)
                publico_afetado = c1.text_input("Publico afetado (agregado, nunca individual)", key=f"pp_publico_{pauta_id}")
                territorio_afetado = c2.text_input("Territorio afetado", key=f"pp_territorio_{pauta_id}")
                proposta_principal = st.text_area("Proposta principal", key=f"pp_proposta_{pauta_id}")
                propostas_complementares = st.text_input("Propostas complementares (separadas por virgula)", key=f"pp_complementares_{pauta_id}")

                gravidade_problema = _nivel("Gravidade do problema", f"pp_gravidade_{pauta_id}")
                urgencia = _nivel("Urgencia", f"pp_urgencia_{pauta_id}")
                abrangencia_territorial = _nivel("Abrangencia territorial do problema", f"pp_abrangencia_{pauta_id}")
                aderencia_candidato = _nivel("Aderencia a sua trajetoria", f"pp_aderencia_{pauta_id}")
                credibilidade_candidato = _nivel("Sua credibilidade nesta pauta", f"pp_credibilidade_{pauta_id}")
                experiencia_anterior_candidato = _nivel("Sua experiencia anterior com o tema", f"pp_experiencia_{pauta_id}")
                saturacao_outros_candidatos = _nivel("Saturacao (quanto outros candidatos ja ocupam esta pauta)", f"pp_saturacao_{pauta_id}")
                diferenciacao = _nivel("Diferenciacao desta proposta frente as existentes", f"pp_diferenciacao_{pauta_id}")

                dados_comprovam_problema = _simnao("Existem dados que comprovam o problema?", f"pp_dados_{pauta_id}")
                existe_estimativa_custo = _simnao("Existe estimativa de custo?", f"pp_custo_{pauta_id}")
                existe_fonte_financiamento = _simnao("Existe fonte de financiamento identificada?", f"pp_financiamento_{pauta_id}")
                existe_prazo_definido = _simnao("Existe prazo definido?", f"pp_prazo_{pauta_id}")
                existe_indicador_resultado = _simnao("Existe indicador de resultado?", f"pp_indicador_{pauta_id}")
                existe_meta_definida = _simnao("Existe meta definida?", f"pp_meta_{pauta_id}")
                depende_outro_ente = _simnao("Depende de outro ente federativo?", f"pp_depende_{pauta_id}")
                exige_alteracao_legislativa = _simnao("Exige alteracao legislativa?", f"pp_lei_{pauta_id}")
                exige_parceria = _simnao("Exige parceria (privada/terceiro setor)?", f"pp_parceria_{pauta_id}")
                risco_juridico = _nivel("Risco juridico percebido", f"pp_risco_juridico_{pauta_id}")
                risco_fiscal = _nivel("Risco fiscal percebido", f"pp_risco_fiscal_{pauta_id}")
                risco_rejeicao = _nivel("Risco de rejeicao publica percebido", f"pp_risco_rejeicao_{pauta_id}")
                potencial_comunicacao = _nivel("Potencial de comunicacao da pauta", f"pp_potencial_com_{pauta_id}")
                potencial_mobilizacao = _nivel("Potencial de mobilizacao da pauta", f"pp_potencial_mob_{pauta_id}")
                coerencia_com_outras_pautas = _nivel("Coerencia com as demais pautas", f"pp_coerencia_{pauta_id}")

                pauta_enviada = st.form_submit_button("Salvar detalhamento desta pauta")
            if pauta_enviada:
                propostas_pauta[pauta_id] = PropostaPauta(
                    pauta_id=pauta_id, cargo_analisado=resposta.identificacao.cargo_pretendido,
                    problema_central=problema_central, publico_afetado=publico_afetado,
                    territorio_afetado=territorio_afetado, proposta_principal=proposta_principal,
                    propostas_complementares=[t.strip() for t in propostas_complementares.split(",") if t.strip()],
                    gravidade_problema=gravidade_problema, urgencia=urgencia,
                    abrangencia_territorial=abrangencia_territorial, aderencia_candidato=aderencia_candidato,
                    credibilidade_candidato=credibilidade_candidato,
                    experiencia_anterior_candidato=experiencia_anterior_candidato,
                    saturacao_outros_candidatos=saturacao_outros_candidatos, diferenciacao=diferenciacao,
                    risco_juridico=risco_juridico, risco_fiscal=risco_fiscal, risco_rejeicao=risco_rejeicao,
                    potencial_comunicacao=potencial_comunicacao, potencial_mobilizacao=potencial_mobilizacao,
                    coerencia_com_outras_pautas=coerencia_com_outras_pautas,
                    dados_comprovam_problema=dados_comprovam_problema, existe_estimativa_custo=existe_estimativa_custo,
                    existe_fonte_financiamento=existe_fonte_financiamento, existe_prazo_definido=existe_prazo_definido,
                    existe_indicador_resultado=existe_indicador_resultado, existe_meta_definida=existe_meta_definida,
                    depende_outro_ente=depende_outro_ente, exige_alteracao_legislativa=exige_alteracao_legislativa,
                    exige_parceria=exige_parceria,
                )
                st.success(f"'{label_pauta}' detalhada - entra na analise final abaixo.")

# ------------------------------------------------------------------ Resultado
st.divider()
st.subheader("Resultado")

indices = calcular_indices_candidato(resposta)
arquetipo = classificar_arquetipo(indices)

st.caption(
    f"Taxa de preenchimento do questionario: {resposta.taxa_preenchimento()}% - "
    f"Cobertura geral dos indices: {indices.cobertura_geral_pct}%"
)
st.warning(
    "Aviso metodologico: os indices abaixo sao autoavaliacao categorica declarada neste "
    "formulario - nao sao medicao objetiva de dado eleitoral."
)

r_prontidao = indices["prontidao_eleitoral"]
r_competitividade = indices["competitividade_inicial"]
r_potencial = indices["potencial_crescimento"]
r_risco = indices["risco_reputacional"]
kpis = st.columns(4)
_kpi(kpis[0], "Prontidao Eleitoral", f"{r_prontidao.valor:.0f}/100", _rotulo_classificacao(r_prontidao), _tom_indice(r_prontidao.valor, False))
_kpi(kpis[1], "Competitividade Inicial", f"{r_competitividade.valor:.0f}/100", _rotulo_classificacao(r_competitividade), _tom_indice(r_competitividade.valor, False))
_kpi(kpis[2], "Potencial de Crescimento", f"{r_potencial.valor:.0f}/100", _rotulo_classificacao(r_potencial), _tom_indice(r_potencial.valor, False))
_kpi(kpis[3], "Risco Reputacional", f"{r_risco.valor:.0f}/100", _rotulo_classificacao(r_risco), _tom_indice(r_risco.valor, True))

with st.expander("Os 20 indices"):
    linhas = [
        {
            "Indice": nome.replace("_", " ").title(), "Nota": r.valor, "Classificacao": _rotulo_classificacao(r),
            "Cobertura": f"{r.cobertura_pct:.0f}%", "Leitura": "nota alta = pior" if r.pior_quando_alto else "nota alta = melhor",
        }
        for nome, r in indices.indices.items()
    ]
    st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)

st.subheader("Arquetipo politico-eleitoral")
if arquetipo.arquetipo_principal:
    st.markdown(f"**Principal:** {arquetipo.arquetipo_principal.replace('_', ' ').title()}")
    if arquetipo.arquetipos_secundarios:
        st.markdown(f"**Secundarios:** {', '.join(a.replace('_', ' ').title() for a in arquetipo.arquetipos_secundarios)}")
    if arquetipo.cargos_compativeis:
        st.markdown(f"**Cargos compativeis (arquetipo principal):** {', '.join(arquetipo.cargos_compativeis)}")
    st.caption(f"Evidencia: `{arquetipo.evidencias.get(arquetipo.arquetipo_principal)}`")
else:
    st.markdown("Nenhum arquetipo com evidencia suficiente nas respostas informadas.")

# Contexto narrativo - inclui os campos que ate a rodada anterior existiam no
# schema mas nunca eram coletados nem mostrados (secao Objetivos completa +
# flags de Identificacao/Posicionamento).
st.subheader("Contexto declarado")
_linhas_contexto = [
    ("Imagem que deseja projetar", resposta.posicionamento.imagem_desejada),
    ("Estilo de lideranca", resposta.posicionamento.estilo_lideranca),
    ("Contexto sobre relacionamento com liderancas", resposta.base_eleitoral.contexto_relacionamento_liderancas),
    ("Cargo ja definido", resposta.identificacao.cargo_definido.value),
    ("Aceita disputar outro cargo se necessario", resposta.identificacao.aceita_outros_cargos.value),
    ("Aceita mudar de municipio-base", resposta.identificacao.aceita_outros_municipios.value),
    ("Ja possui domicilio eleitoral", resposta.identificacao.possui_domicilio_eleitoral.value),
    ("Objetivo principal", (resposta.objetivos.objetivo_principal or "").replace("_", " ") or None),
    ("Horizonte temporal", (resposta.objetivos.horizonte_temporal or "").replace("_", " ") or None),
    ("Aceita concorrer a outro cargo no futuro mesmo perdendo este", resposta.objetivos.aceita_outro_cargo.value),
]
for rotulo, valor in _linhas_contexto:
    if valor:
        st.markdown(f"**{rotulo}:** {valor}")
st.caption("Texto/flags livres acima - nao entram em nenhum indice numerico, so na narrativa da estrategia.")

# -------------------------------------------------------------------- Padrinho
analise_padrinho = None
if resposta.identificacao.possui_padrinho_politico == SimNao.SIM:
    st.markdown("### 🤝 Padrinho politico")
    nome_padrinho_decl = resposta.identificacao.nome_padrinho_politico
    if not nome_padrinho_decl:
        st.info("Nome do padrinho nao informado - preencha o campo acima para cruzar com o TSE.")
    else:
        analise_padrinho = analisar_padrinho_politico(nome_padrinho_decl, resposta.identificacao.uf)
        if analise_padrinho.encontrado_no_tse:
            cp = analise_padrinho.candidatura_encontrada
            st.success(
                f"Encontrado no TSE: **{cp.nome_urna}** ({cp.nome_completo}) - {cp.cargo.title()}/{cp.uf} "
                f"- eleicao {cp.ano_eleicao} - {cp.resultado_final}."
            )
            kpis_padrinho = st.columns(4)
            _kpi(kpis_padrinho[0], "Cargo disputado", cp.cargo.title())
            _kpi(kpis_padrinho[1], "Votos (disputa real)", f"{cp.total_votos:,}".replace(",", "."))
            _kpi(kpis_padrinho[2], "Indice de Desempenho Politico (IDP)", f"{analise_padrinho.indice_forca_idp:.0f}/100")
            _kpi(kpis_padrinho[3], "Classificacao", analise_padrinho.classificacao_forca.replace("_", " ").title())
        else:
            st.warning(f"'{nome_padrinho_decl}' nao foi encontrado no registro de candidatos do TSE (2018/2022/2024) na UF {resposta.identificacao.uf}.")
            for aviso in analise_padrinho.limitacoes:
                st.caption(aviso)

# --------------------------------------------------- Territorios e pautas
if resposta.identificacao.municipio_base and resposta.identificacao.municipio_base != "-- nao informado --":
    st.divider()
    st.markdown("### 🗺️ Territorios e Pautas Sugeridas")
    with st.spinner("Cruzando pautas prioritarias com o Censo IBGE 2022 por distrito..."):
        resultado_territorios = montar_territorios_sugeridos(
            resposta.identificacao.uf, resposta.identificacao.municipio_base,
            resposta.posicionamento.pautas_prioritarias, resposta.base_eleitoral.bairros_presenca_declarados,
        )
    for aviso in resultado_territorios.perfil.avisos:
        st.warning(aviso)
    if not resultado_territorios.perfil.territorios.empty:
        for ranking_pauta in resultado_territorios.rankings_por_pauta:
            label_pauta = _PAUTAS_LABELS.get(ranking_pauta.pauta_id, ranking_pauta.pauta_id)
            with st.container(border=True):
                st.markdown(f"**{label_pauta}**")
                if not ranking_pauta.tem_proxy_territorial or ranking_pauta.ranking is None:
                    st.caption(ranking_pauta.aviso)
                else:
                    top5 = ranking_pauta.ranking.head(5)
                    st.dataframe(
                        top5[["territorio", "score_oportunidade", "populacao_total"]],
                        use_container_width=True, hide_index=True,
                        column_config={"score_oportunidade": st.column_config.ProgressColumn("Oportunidade real (0-100)", min_value=0, max_value=100)},
                    )
        if analise_padrinho is not None and analise_padrinho.encontrado_no_tse and analise_padrinho.top_territorios is not None:
            with st.container(border=True):
                st.markdown(f"**Territorios reais do padrinho ({analise_padrinho.nome_declarado})**")
                st.dataframe(analise_padrinho.top_territorios, use_container_width=True, hide_index=True)
        for limitacao in resultado_territorios.limitacoes:
            st.caption(limitacao)

# --------------------------------------------- Rivais + compatibilidade + patrimonio
st.divider()
st.subheader("Rivais projetados, compatibilidade partidaria e patrimonio")
_explicacao(
    "Nao e autoavaliacao: usa dado real de votacao do TSE da disputa comparavel mais recente "
    "para o cargo/UF/municipio informados. A premissa hipotetica, sempre declarada, e que essa "
    "disputa passada e um proxy razoavel de quem disputara a proxima eleicao."
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
            "Colocacao": r.colocacao, "Nome de urna": r.candidatura.nome_urna, "Partido": r.candidatura.partido_sigla,
            "Votos (disputa comparavel)": r.candidatura.total_votos, "Resultado (disputa comparavel)": r.candidatura.resultado_final,
            "Indice de rivalidade": r.indice_rivalidade, "Classificacao": r.classificacao.replace("_", " ").title(),
        }
        for r in resultado_rivais.rivais
    ]
    st.dataframe(pd.DataFrame(linhas_rivais), use_container_width=True, hide_index=True)
    st.caption(
        "Assimetria metodologica: os rivais acima tem indices de desempenho real (IDP/IVE/IEC/QEC, "
        "calculados sobre voto ja disputado) - o candidato deste questionario ainda nao tem um "
        "equivalente, porque isso exige voto real de uma eleicao ja disputada. Os indices mostrados "
        "acima para ele (Prontidao/Competitividade/Potencial/Risco) sao autoavaliacao categorica, "
        "nao a mesma escala do IDP dos rivais - nunca compare os dois numeros diretamente."
    )

    if resposta.recursos.patrimonio_pessoal_declarado is not None:
        st.markdown("**Comparativo de patrimonio (declarado vs. rivais reais/TSE)**")
        linhas_patrimonio = [{"Quem": "Voce (declarado neste formulario)", "Patrimonio (R$)": resposta.recursos.patrimonio_pessoal_declarado, "Fonte": "Autoavaliacao"}]
        for r in resultado_rivais.rivais[:5]:
            perfil_pat = carregar_patrimonio_candidato(r.candidatura)
            linhas_patrimonio.append({
                "Quem": r.candidatura.nome_urna,
                "Patrimonio (R$)": perfil_pat.valor_total_bens if perfil_pat.disponivel else None,
                "Fonte": "TSE (bem_candidato)" if perfil_pat.disponivel else "Indisponivel",
            })
        st.dataframe(pd.DataFrame(linhas_patrimonio), use_container_width=True, hide_index=True)
        st.caption("Patrimonio dos rivais e autodeclarado por eles ao TSE - nao e auditoria patrimonial.")

if resposta.identificacao.partido_sigla:
    resultado_partido = avaliar_compatibilidade_partidaria(
        resposta.identificacao.partido_sigla, resposta.identificacao.cargo_pretendido,
        resposta.identificacao.uf, resposta.identificacao.municipio_base,
    )
    st.markdown(f"**Compatibilidade partidaria real: {resultado_partido.partido_sigla}**")
    for aviso in resultado_partido.avisos:
        if aviso not in disputa.avisos:
            st.warning(aviso)
    if resultado_partido.n_candidatos_partido:
        kpis_partido = st.columns(4)
        _kpi(kpis_partido[0], "Candidatos do partido (disputa comparavel)", str(resultado_partido.n_candidatos_partido))
        _kpi(kpis_partido[1], "Eleitos do partido (disputa comparavel)", str(resultado_partido.n_eleitos_partido))
        _kpi(kpis_partido[2], "Taxa de sucesso do partido", f"{resultado_partido.taxa_sucesso_partido * 100:.0f}%" if resultado_partido.taxa_sucesso_partido is not None else "n/d")
        _kpi(kpis_partido[3], "Melhor colocacao do partido", f"{resultado_partido.melhor_colocacao_partido}o lugar" if resultado_partido.melhor_colocacao_partido else "n/d")
else:
    st.caption("Informe a sigla do partido no formulario acima para ver a compatibilidade partidaria real.")

# ---------------------------------------------------------- Pautas detalhadas
propostas_pauta_salvas: dict = st.session_state.get("cq_propostas_pauta", {})
if propostas_pauta_salvas:
    st.divider()
    st.subheader("Pautas detalhadas (Modo 3 completo)")
    for pauta_id, proposta in propostas_pauta_salvas.items():
        indices_pauta = calcular_indices_pauta(proposta)
        classificacao_pauta = classificar_pauta(indices_pauta)
        gate = verificar_gate_competencia(proposta.pauta_id, proposta.cargo_analisado)
        plataforma = montar_plataforma(proposta, indices_pauta, classificacao_pauta)
        with st.container(border=True):
            st.markdown(f"**{_PAUTAS_LABELS.get(pauta_id, pauta_id)}**")
            r_geral = indices_pauta["indice_geral_prioridade"]
            kpis_pauta = st.columns(2)
            _kpi(kpis_pauta[0], "Indice Geral de Prioridade", f"{r_geral.valor:.0f}/100", _rotulo_classificacao(r_geral), _tom_indice(r_geral.valor, False))
            gate_txt = "APROVADO" if gate.aprovado else "REPROVADO"
            _kpi(kpis_pauta[1], "Gate de competencia do cargo", gate_txt, gate.motivo, "bom" if gate.aprovado else "ruim")
            st.markdown(f"**Orgao responsavel:** {plataforma.orgao_responsavel}")
            st.markdown(f"**Custo estimado:** {plataforma.custo_estimado}")

# -------------------------------------------------------------------- Salvar
st.divider()
st.subheader("Salvar esta analise")
if not st.session_state.get("cq_salvo"):
    if st.button("Salvar e sincronizar com o SIET", type="primary"):
        caminho, sincronizado = salvar_e_sincronizar(resposta, list(propostas_pauta_salvas.values()))
        st.session_state["cq_salvo"] = True
        st.session_state["cq_caminho"] = str(caminho)
        st.session_state["cq_sincronizado"] = sincronizado
        st.rerun()
else:
    st.success(f"Salvo em `{st.session_state.get('cq_caminho')}`.")
    if st.session_state.get("cq_sincronizado"):
        st.info("Sincronizado com o GitHub - o SIET local vai enxergar este candidato apos um `git pull`.")
    else:
        st.warning(
            "Nao sincronizado com o GitHub (token nao configurado ou falha de rede) - a resposta "
            "ficou salva so localmente neste host. Se este e o host publico, avise quem administra "
            "o sistema para configurar o segredo GITHUB_TOKEN."
        )
