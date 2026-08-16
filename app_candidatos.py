"""Host dedicado ao Questionario Completo de Novos Candidatos (SIET V2).

Segundo ponto de entrada do MESMO repositorio de `app.py` (nao e um projeto
separado - reaproveita `src/` inteiro, mesmo `requirements.txt`, mesmo
`config/`). Rodar local:

    .venv\\Scripts\\python.exe -m streamlit run app_candidatos.py --server.port 8541

Ou publicado no Streamlit Community Cloud como um 2o app apontando pro
mesmo repo, "Main file path" = app_candidatos.py.

Diferente de app.py (que tem 4 modos + o fluxo de candidatura real), este
host tem UMA pagina so: o questionario de autoavaliacao do Modulo Candidato
(Modo 1), agora com 13 secoes (as 7 originais + Elegibilidade, Apoio
Institucional, Estrutura de Campanha, Chapa/Cronograma, Perfil Demografico
e Pesquisa Propria - plano de melhoria pos-lancamento) mais uma ponte
opcional para o questionario completo de pauta (Modo 3) por cada pauta
prioritaria marcada - em vez do miniformulario de 2 campos que a Matriz
Integrada usa hoje. A renderizacao do resultado (KPIs, indices, rivais,
territorio, etc.) mora em src/questionnaire/render.py, reaproveitada
tambem pela pagina "Candidatos Analisados" de app.py. Ao final, salva a
resposta (local + commit no GitHub quando publicado) via
src/questionnaire/persistence.py.
"""
from __future__ import annotations

import streamlit as st

from src.uf_nomes import UF_NOME
from src.ui_helpers import (
    _CARGOS_MODO1,
    _explicacao,
    _fmt,
    _nivel,
    _simnao,
    render_css,
)

from src.questionnaire.candidate_questionnaire import (
    ApoioInstitucional,
    BaseEleitoral,
    Chapa,
    Comunicacao,
    Cronograma,
    Elegibilidade,
    EstruturaCampanha,
    IdentificacaoAnalise,
    NivelIntensidade,
    Objetivos,
    PerfilDemografico,
    PesquisaPropria,
    Posicionamento,
    Recursos,
    RedesSociais,
    RespostaQuestionario,
    SimNao,
    Trajetoria,
)
from src.questionnaire.policy_questionnaire import PropostaPauta, policy_areas_config
from src.questionnaire.persistence import salvar_e_sincronizar
from src.questionnaire.render import renderizar_analise_completa

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
    nome_completo_eleitoral = st.text_input(
        "Nome completo usado em candidaturas anteriores (se ja disputou eleicao)",
        key="q_nome_eleitoral",
        help="So preenche se 'Ja disputou eleicao antes?' for Sim. Usado pra buscar a PROPRIA "
             "trajetoria real no registro do TSE (2018/2022/2024) e mostrar indice de desempenho "
             "real (IDP), em vez de depender so de autoavaliacao na secao Trajetoria abaixo.",
    )

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
        apoiadores_mobilizaveis = _nivel(
            "Apoiadores mobilizaveis", "q_apoiadores",
            help="Alta = consegue reunir 50+ pessoas com aviso de poucos dias. Moderada = "
                 "consegue reunir um grupo menor (10-30) com esforco. Baixa = so familia/circulo "
                 "proximo.",
        )
        capacidade_eventos = _nivel(
            "Capacidade de realizar eventos", "q_eventos",
            help="Alta = ja organizou evento publico com 100+ pessoas. Moderada = ja organizou "
                 "reuniao/evento menor. Baixa = nunca organizou evento proprio.",
        )
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
            "Conhecimento espontaneo (eleitores que reconhecem o nome sem ajuda)", "q_conhecimento",
            help="Alta = estranhos no territorio reconhecem seu nome sem voce se apresentar. "
                 "Moderada = reconhecido dentro do seu circulo/bairro. Baixa = so quem ja te "
                 "conhece pessoalmente.",
        )
        oratoria = _nivel(
            "Oratoria", "q_oratoria",
            help="Alta = ja discursou pra publico de 100+ pessoas com boa recepcao. Moderada = "
                 "confortavel falando em grupos pequenos/reunioes. Baixa = pouca ou nenhuma "
                 "experiencia falando em publico.",
        )
        desempenho_videos = _nivel(
            "Desempenho em videos", "q_videos",
            help="Alta = ja produziu video com alcance real (milhares de visualizacoes organicas). "
                 "Moderada = ja gravou video mas com alcance limitado. Baixa = nunca gravou/nao se "
                 "sente confortavel.",
        )
        entrevistas = _nivel(
            "Desempenho em entrevistas", "q_entrevistas",
            help="Alta = ja deu entrevista em veiculo de alcance regional/estadual (radio/TV/portal). "
                 "Moderada = ja deu entrevista em veiculo local/pequeno. Baixa = nunca deu entrevista.",
        )
        debates = _nivel(
            "Desempenho em debates", "q_debates",
            help="Alta = ja participou de debate publico formal (eleitoral ou institucional). "
                 "Moderada = ja debateu em contexto informal (reuniao, audiencia). Baixa = nunca "
                 "participou de debate.",
        )
        resposta_criticas = _nivel(
            "Resposta a criticas", "q_resp_criticas",
            help="Alta = ja respondeu critica publica de forma que reduziu o desgaste (evidencia "
                 "concreta). Moderada = ja respondeu mas sem certeza do efeito. Baixa = nunca foi "
                 "testado publicamente ou historico de piorar a situacao ao responder.",
        )
        seguidores_redes = st.number_input(
            "Numero total de seguidores nas redes sociais (some todas as redes, deixe em branco se nao souber)",
            min_value=0, step=100, value=None, key="q_seguidores",
        )
        engajamento = _nivel(
            "Engajamento nas redes sociais", "q_engajamento",
            help="Alta = posts costumam gerar comentarios/compartilhamentos reais, nao so curtidas. "
                 "Moderada = engajamento ocasional. Baixa = posts raramente geram interacao.",
        )
        producao_conteudo = _nivel(
            "Producao propria de conteudo", "q_conteudo",
            help="Alta = publica conteudo proprio (nao repost) com regularidade (varias vezes por "
                 "semana). Moderada = publica de vez em quando. Baixa = quase nunca produz conteudo "
                 "proprio.",
        )
        equipe_comunicacao = _nivel("Equipe de comunicacao", "q_equipe_com")
        rejeicao_percebida = _nivel(
            "Rejeicao percebida (quanto maior, pior)", "q_rejeicao",
            help="Alta = ha sinal concreto de rejeicao relevante (ex.: pesquisa/feedback recorrente "
                 "negativo). Moderada = rejeicao pontual conhecida. Baixa/Nenhuma = sem sinal "
                 "relevante de rejeicao ate agora.",
        )

    with st.expander("4b. Redes sociais (handles/links)"):
        _explicacao(
            "Usados so como link de evidencia citavel na narrativa do relatorio - nunca coletados "
            "automaticamente (o sistema nunca faz scraping/busca externa)."
        )
        c_ig, c_tt, c_x = st.columns(3)
        instagram = c_ig.text_input("Instagram", key="q_instagram")
        tiktok = c_tt.text_input("TikTok", key="q_tiktok")
        x_twitter = c_x.text_input("X/Twitter", key="q_x_twitter")
        c_fb, c_yt = st.columns(2)
        facebook = c_fb.text_input("Facebook", key="q_facebook")
        youtube = c_yt.text_input("YouTube", key="q_youtube")

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
        st.markdown("**Orcamento detalhado (opcional)**")
        c_r1, c_r2, c_r3 = st.columns(3)
        recursos_proprios_estimados = c_r1.number_input(
            "Recursos proprios estimados (R$)", min_value=0.0, step=1000.0, value=None,
            key="q_recursos_proprios", format="%.2f",
        )
        doacoes_terceiros_estimadas = c_r2.number_input(
            "Doacoes de terceiros estimadas (R$)", min_value=0.0, step=1000.0, value=None,
            key="q_doacoes_terceiros", format="%.2f",
        )
        expectativa_fundo_eleitoral = c_r3.number_input(
            "Expectativa de Fundo Eleitoral/Partidario (R$)", min_value=0.0, step=1000.0, value=None,
            key="q_fundo_eleitoral", format="%.2f",
        )
        agencia_publicidade_contratada = _simnao("Agencia de publicidade ja contratada?", "q_agencia_publicidade")

    with st.expander("5b. Estrutura de campanha"):
        c_ec1, c_ec2, c_ec3 = st.columns(3)
        with c_ec1:
            coordenador_definido = _simnao("Coordenador de campanha definido?", "q_coordenador")
        with c_ec2:
            tesoureiro_definido = _simnao("Tesoureiro definido?", "q_tesoureiro")
        with c_ec3:
            advogado_eleitoral_contratado = _simnao("Advogado eleitoral contratado?", "q_advogado")
        numero_cabos_eleitorais = st.number_input(
            "Numero estimado de cabos eleitorais/voluntarios mobilizaveis (deixe em branco se nao souber)",
            min_value=0, max_value=1000, step=1, value=None, key="q_cabos_eleitorais",
        )

    with st.expander("6. Posicionamento"):
        temas = st.text_input("Temas de maior identificacao (separados por virgula)", key="q_temas")
        imagem_desejada = st.text_input("Imagem que deseja projetar (texto livre, opcional)", key="q_imagem_desejada")
        estilo_lideranca = st.text_input("Estilo de lideranca (texto livre, opcional)", key="q_estilo_lideranca")
        resistencia_ataques = _nivel(
            "Resistencia a ataques/criticas publicas", "q_resistencia",
            help="Alta = ja passou por ataque publico relevante e manteve a base de apoio. "
                 "Moderada = nunca foi testado com ataque forte, mas tem preparo. Baixa = sem "
                 "experiencia e sem preparo especifico pra lidar com ataques.",
        )
        disciplina = _nivel(
            "Disciplina (agenda, partido, mensagem)", "q_disciplina",
            help="Alta = historico de cumprir agenda/compromissos e manter mensagem consistente. "
                 "Moderada = geralmente consistente, com excecoes pontuais. Baixa = historico de "
                 "inconsistencia frequente.",
        )
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
        st.markdown("**Cenario competitivo, na sua visao (opcional)**")
        _explicacao(
            "Percepcao declarada por voce - sempre comparada, nunca misturada, com os rivais REAIS "
            "calculados pelo sistema mais abaixo (secao de rivais projetados)."
        )
        adversarios_texto = st.text_input(
            "Seus principais adversarios, na sua visao (separados por virgula)", key="q_adversarios",
        )
        aliados_texto = st.text_input(
            "Seus principais aliados/apoiadores publicos (separados por virgula)", key="q_aliados",
        )
        st.markdown("**Riscos e vulnerabilidades (opcional, tema sensivel - sempre autodeclarado)**")
        c_risco1, c_risco2 = st.columns(2)
        with c_risco1:
            processo_judicial_conhecido = _simnao(
                "Ha processo judicial relevante e publicamente conhecido em andamento?", "q_processo_judicial",
            )
        with c_risco2:
            controversia_publica_conhecida = _simnao(
                "Ha controversia publica significativa envolvendo seu nome?", "q_controversia",
            )
        contexto_processo_judicial = st.text_input(
            "Contexto do processo judicial (se houver)", key="q_contexto_processo",
        )
        contexto_controversia_publica = st.text_input(
            "Contexto da controversia publica (se houver)", key="q_contexto_controversia",
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

    with st.expander("8. Elegibilidade e situacao juridico-partidaria"):
        _explicacao(
            "Datas ficam so na narrativa (nunca em formula) - prazo legal exato muda por cargo/ano, "
            "confira contra a regra vigente antes de decidir algo em cima disso."
        )
        c_e1, c_e2 = st.columns(2)
        data_filiacao_partidaria = c_e1.date_input(
            "Filiado ao partido desde (deixe em branco se nao souber/nao se aplica)",
            value=None, key="q_data_filiacao",
        )
        data_domicilio_eleitoral = c_e2.date_input(
            "Domicilio eleitoral desde (deixe em branco se nao souber)", value=None, key="q_data_domicilio",
        )
        prestacao_contas_em_dia = _simnao(
            "Prestacao de contas de campanhas anteriores em dia?", "q_prestacao_contas",
        )
        pendencia_justica_eleitoral = _simnao(
            "Ha pendencia conhecida na Justica Eleitoral?", "q_pendencia_justica",
        )
        contexto_pendencia_justica = st.text_input(
            "Contexto da pendencia (se houver)", key="q_contexto_pendencia",
        )

    with st.expander("9. Rede de apoio institucional"):
        c_ai1, c_ai2 = st.columns(2)
        with c_ai1:
            apoio_sindicato = _simnao("Tem apoio de sindicato(s)?", "q_apoio_sindicato")
        sindicatos_texto = st.text_input(
            "Quais sindicatos (separados por virgula)", key="q_sindicatos_quais",
        )
        proximidade_religiosa = st.text_input(
            "Proximidade com lideranca religiosa/denominacao predominante da base (texto livre, opcional)",
            key="q_proximidade_religiosa",
        )
        c_ai3, c_ai4 = st.columns(2)
        with c_ai3:
            apoio_movimento_social = _simnao("Participa de movimento social organizado?", "q_movimento_social")
        movimento_social_qual = c_ai4.text_input("Qual movimento", key="q_movimento_social_qual")
        c_ai5, c_ai6 = st.columns(2)
        with c_ai5:
            apoio_associacao_empresarial = _simnao("Tem apoio de associacao empresarial/comercial?", "q_associacao_empresarial")
        associacao_empresarial_qual = c_ai6.text_input("Qual associacao", key="q_associacao_qual")
        c_ai7, c_ai8 = st.columns(2)
        with c_ai7:
            midia_local_alinhada = _simnao("Tem veiculo de midia local alinhado?", "q_midia_local")
        midia_local_qual = c_ai8.text_input("Qual veiculo", key="q_midia_local_qual")

    with st.expander("10. Chapa, coligacao e cronograma"):
        c_ch1, c_ch2 = st.columns(2)
        with c_ch1:
            coligacao_formada = _simnao("Chapa/coligacao ja formada?", "q_coligacao_formada")
        nome_coligacao = c_ch2.text_input("Nome da coligacao (se souber)", key="q_nome_coligacao")
        candidato_vice = st.text_input(
            "Candidato(a) a vice (so pra cargo majoritario: Prefeito/Governador/Presidente)",
            key="q_candidato_vice",
        )
        c_cr1, c_cr2 = st.columns(2)
        with c_cr1:
            numero_urna_definido = _simnao("Numero de urna ja definido?", "q_numero_urna_definido")
        numero_urna = c_cr2.number_input(
            "Numero de urna (se definido)", min_value=0, step=1, value=None, key="q_numero_urna",
        )
        c_cr3, c_cr4 = st.columns(2)
        with c_cr3:
            material_grafico_pronto = _simnao("Material grafico pronto (logo/slogan)?", "q_material_pronto")
        data_convencao_partidaria = c_cr4.date_input(
            "Data prevista de convencao partidaria (se souber)", value=None, key="q_data_convencao",
        )

    with st.expander("11. Perfil demografico (opcional)"):
        _explicacao(
            "Mesmas categorias que o TSE usa pra candidatos reais. LIMITACAO ATUAL: o pacote de "
            "dados deste projeto nao inclui as colunas demograficas do TSE - por enquanto estes "
            "campos alimentam so a narrativa, sem comparacao automatica contra candidatos reais "
            "parecidos ainda."
        )
        c_pd1, c_pd2, c_pd3 = st.columns(3)
        data_nascimento = c_pd1.date_input(
            "Data de nascimento (opcional)", value=None, key="q_data_nascimento",
        )
        genero = c_pd2.selectbox(
            "Genero", ["-- nao respondido --", "Masculino", "Feminino", "Nao binario", "Prefere nao informar"],
            key="q_genero",
        )
        cor_raca_autodeclarada = c_pd3.selectbox(
            "Cor/raca autodeclarada",
            ["-- nao respondido --", "Branca", "Preta", "Parda", "Amarela", "Indigena"],
            key="q_cor_raca",
        )
        c_pd4, c_pd5, c_pd6 = st.columns(3)
        escolaridade = c_pd4.selectbox(
            "Escolaridade",
            ["-- nao respondido --", "Le e escreve", "Ensino fundamental", "Ensino medio",
             "Ensino superior incompleto", "Ensino superior completo", "Pos-graduacao"],
            key="q_escolaridade",
        )
        ocupacao_atual = c_pd5.text_input("Ocupacao atual", key="q_ocupacao")
        estado_civil = c_pd6.selectbox(
            "Estado civil",
            ["-- nao respondido --", "Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viuvo(a)", "Uniao estavel"],
            key="q_estado_civil",
        )

    with st.expander("12. Pesquisa eleitoral propria (opcional)"):
        _explicacao("Sempre autodeclarada - nunca tratada como dado verificado.")
        ja_realizou_pesquisa = _simnao("Ja realizou alguma pesquisa (formal ou informal)?", "q_ja_pesquisa")
        c_pp1, c_pp2, c_pp3 = st.columns(3)
        instituto_declarado = c_pp1.text_input("Instituto (se houver)", key="q_instituto_pesquisa")
        data_pesquisa = c_pp2.date_input("Data da pesquisa", value=None, key="q_data_pesquisa")
        percentual_declarado = c_pp3.number_input(
            "Percentual declarado (%)", min_value=0.0, max_value=100.0, step=0.5, value=None,
            key="q_percentual_pesquisa",
        )

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
            nome_completo_eleitoral=nome_completo_eleitoral.strip() if ja_disputou == SimNao.SIM and nome_completo_eleitoral.strip() else None,
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
        apoio_institucional=ApoioInstitucional(
            apoio_sindicato=apoio_sindicato,
            sindicatos_declarados=[s.strip() for s in sindicatos_texto.split(",") if s.strip()],
            proximidade_religiosa=proximidade_religiosa.strip() or None,
            apoio_movimento_social=apoio_movimento_social, movimento_social_qual=movimento_social_qual.strip() or None,
            apoio_associacao_empresarial=apoio_associacao_empresarial,
            associacao_empresarial_qual=associacao_empresarial_qual.strip() or None,
            midia_local_alinhada=midia_local_alinhada, midia_local_qual=midia_local_qual.strip() or None,
        ),
        comunicacao=Comunicacao(
            conhecimento_espontaneo=conhecimento_espontaneo, oratoria=oratoria, desempenho_videos=desempenho_videos,
            entrevistas=entrevistas, debates=debates, resposta_criticas=resposta_criticas,
            seguidores_redes=seguidores_redes, engajamento=engajamento, producao_conteudo=producao_conteudo,
            equipe_comunicacao=equipe_comunicacao, rejeicao_percebida=rejeicao_percebida,
        ),
        redes_sociais=RedesSociais(
            instagram=instagram.strip() or None, tiktok=tiktok.strip() or None,
            x_twitter=x_twitter.strip() or None, facebook=facebook.strip() or None,
            youtube=youtube.strip() or None,
        ),
        recursos=Recursos(
            disponibilidade_tempo=disponibilidade_tempo, capacidade_investimento_legal=capacidade_investimento_legal,
            capacidade_arrecadacao=capacidade_arrecadacao, patrimonio_pessoal_declarado=patrimonio_pessoal,
            equipe=equipe, transporte=transporte, locais_reuniao=locais_reuniao, audiovisual=audiovisual,
            disponibilidade_viagens=disponibilidade_viagens,
            recursos_proprios_estimados=recursos_proprios_estimados,
            doacoes_terceiros_estimadas=doacoes_terceiros_estimadas,
            expectativa_fundo_eleitoral=expectativa_fundo_eleitoral,
            agencia_publicidade_contratada=agencia_publicidade_contratada,
        ),
        estrutura_campanha=EstruturaCampanha(
            coordenador_definido=coordenador_definido, tesoureiro_definido=tesoureiro_definido,
            advogado_eleitoral_contratado=advogado_eleitoral_contratado,
            numero_cabos_eleitorais=int(numero_cabos_eleitorais) if numero_cabos_eleitorais is not None else None,
        ),
        posicionamento=Posicionamento(
            temas_identificacao=[t.strip() for t in temas.split(",") if t.strip()],
            imagem_desejada=imagem_desejada.strip() or None, estilo_lideranca=estilo_lideranca.strip() or None,
            resistencia_ataques=resistencia_ataques, disciplina=disciplina,
            disposicao_negociacao=disposicao_negociacao, disposicao_confronto=disposicao_confronto,
            pautas_prioritarias=pautas_prioritarias,
            adversarios_declarados=[a.strip() for a in adversarios_texto.split(",") if a.strip()],
            aliados_declarados=[a.strip() for a in aliados_texto.split(",") if a.strip()],
            processo_judicial_conhecido=processo_judicial_conhecido,
            contexto_processo_judicial=contexto_processo_judicial.strip() or None,
            controversia_publica_conhecida=controversia_publica_conhecida,
            contexto_controversia_publica=contexto_controversia_publica.strip() or None,
        ),
        objetivos=Objetivos(
            objetivo_principal=_OPCOES_OBJETIVO_PRINCIPAL[objetivo_principal_label],
            horizonte_temporal=_OPCOES_HORIZONTE[horizonte_temporal_label],
            risco_aceito=risco_aceito,
            aceita_outro_cargo=aceita_outro_cargo if aceita_outro_cargo is not None else SimNao.NAO,
        ),
        elegibilidade=Elegibilidade(
            data_filiacao_partidaria=data_filiacao_partidaria, prestacao_contas_em_dia=prestacao_contas_em_dia,
            pendencia_justica_eleitoral=pendencia_justica_eleitoral,
            contexto_pendencia_justica=contexto_pendencia_justica.strip() or None,
            data_domicilio_eleitoral=data_domicilio_eleitoral,
        ),
        chapa=Chapa(
            coligacao_formada=coligacao_formada, nome_coligacao=nome_coligacao.strip() or None,
            candidato_vice=candidato_vice.strip() or None,
        ),
        cronograma=Cronograma(
            numero_urna_definido=numero_urna_definido,
            numero_urna=int(numero_urna) if numero_urna is not None else None,
            material_grafico_pronto=material_grafico_pronto,
            data_convencao_partidaria=data_convencao_partidaria,
        ),
        perfil_demografico=PerfilDemografico(
            data_nascimento=data_nascimento,
            genero=genero if genero != "-- nao respondido --" else None,
            cor_raca_autodeclarada=cor_raca_autodeclarada if cor_raca_autodeclarada != "-- nao respondido --" else None,
            escolaridade=escolaridade if escolaridade != "-- nao respondido --" else None,
            ocupacao_atual=ocupacao_atual.strip() or None,
            estado_civil=estado_civil if estado_civil != "-- nao respondido --" else None,
        ),
        pesquisa_propria=PesquisaPropria(
            ja_realizou_pesquisa=ja_realizou_pesquisa, instituto_declarado=instituto_declarado.strip() or None,
            data_pesquisa=data_pesquisa, percentual_declarado=percentual_declarado,
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

propostas_pauta_salvas: dict = st.session_state.get("cq_propostas_pauta", {})
renderizar_analise_completa(resposta, list(propostas_pauta_salvas.values()))

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
