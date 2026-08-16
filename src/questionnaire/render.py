"""Renderizacao do resultado da analise de um candidato (Modulo Candidato,
questionario completo). Extraido de `app_candidatos.py` (onde vivia inline)
pra ser reaproveitado tambem pela pagina "Candidatos Analisados" do SIET
principal (`app.py`) - antes disso, candidato ja salvo so aparecia como
`st.json()` cru, sem nenhuma analise. Mesma funcao roda nos 2 lugares:
resposta recem-preenchida (`app_candidatos.py`) ou recarregada do disco
(`app.py` + `persistence.carregar_resposta_bruta` -> reconstruida em
dataclasses)."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd
import streamlit as st

from ..candidate_assets import carregar_patrimonio_candidato
from ..godfather_analysis import analisar_padrinho_politico
from ..indicators.candidate_indices import calcular_indices_candidato
from ..indicators.policy_indices import calcular_indices_pauta
from ..parties.party_compatibility import avaliar_compatibilidade_partidaria
from ..platforms.platform_builder import montar_plataforma, verificar_gate_competencia
from ..profiles.candidate_archetype import classificar_arquetipo
from ..profiles.policy_classification import classificar_pauta
from ..rivals.hypothetical_rivals import identificar_rivais_projetados
from ..territory_recommendations import montar_territorios_sugeridos
from ..ui_helpers import _explicacao, _kpi, _rotulo_classificacao, _tom_indice
from .candidate_questionnaire import RespostaQuestionario, SimNao
from .policy_questionnaire import PropostaPauta, policy_areas_config


@lru_cache(maxsize=1)
def _pautas_labels() -> dict[str, str]:
    return {pauta_id: dados["label"] for pauta_id, dados in policy_areas_config()["pautas"].items()}


def _linha_se_preenchida(rotulo: str, valor) -> tuple[str, str] | None:
    if valor is None or valor == "" or valor == []:
        return None
    if isinstance(valor, list):
        valor = ", ".join(str(v) for v in valor)
    return (rotulo, str(valor))


def renderizar_analise_completa(
    resposta: RespostaQuestionario, propostas_pauta: list[PropostaPauta] | None = None
) -> None:
    """Ponto de entrada unico: KPIs, arquetipo, elegibilidade, apoio
    institucional, estrutura de campanha, trajetoria real (autobusca ou
    padrinho), territorio/pautas, rivais + patrimonio + compatibilidade,
    pautas detalhadas, perfil demografico, redes sociais, pesquisa propria.
    Nunca lanca excecao por secao opcional vazia - cada bloco checa o que
    precisa antes de desenhar."""
    propostas_pauta = propostas_pauta or []
    pautas_labels = _pautas_labels()

    indices = calcular_indices_candidato(resposta)
    arquetipo = classificar_arquetipo(indices)

    st.caption(
        f"Taxa de preenchimento do questionario: {resposta.taxa_preenchimento()}% - "
        f"Cobertura geral dos indices: {indices.cobertura_geral_pct}%"
    )
    st.warning(
        "Aviso metodologico: os indices abaixo sao autoavaliacao categorica declarada "
        "neste formulario - nao sao medicao objetiva de dado eleitoral."
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

    r_juridico = indices["prontidao_juridico_partidaria"]
    r_institucional = indices["capilaridade_institucional"]
    r_estrutura = indices["estrutura_campanha"]
    kpis2 = st.columns(3)
    _kpi(kpis2[0], "Prontidao Juridico-Partidaria", f"{r_juridico.valor:.0f}/100", _rotulo_classificacao(r_juridico), _tom_indice(r_juridico.valor, False))
    _kpi(kpis2[1], "Capilaridade Institucional", f"{r_institucional.valor:.0f}/100", _rotulo_classificacao(r_institucional), _tom_indice(r_institucional.valor, False))
    _kpi(kpis2[2], "Estrutura de Campanha", f"{r_estrutura.valor:.0f}/100", _rotulo_classificacao(r_estrutura), _tom_indice(r_estrutura.valor, False))

    with st.expander(f"Os {len(indices.indices)} indices"):
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

    # ------------------------------------------------------------ Contexto
    st.subheader("Contexto declarado")
    _linhas_contexto = [
        _linha_se_preenchida("Imagem que deseja projetar", resposta.posicionamento.imagem_desejada),
        _linha_se_preenchida("Estilo de lideranca", resposta.posicionamento.estilo_lideranca),
        _linha_se_preenchida("Contexto sobre relacionamento com liderancas", resposta.base_eleitoral.contexto_relacionamento_liderancas),
        _linha_se_preenchida("Cargo ja definido", resposta.identificacao.cargo_definido.value),
        _linha_se_preenchida("Aceita disputar outro cargo se necessario", resposta.identificacao.aceita_outros_cargos.value),
        _linha_se_preenchida("Aceita mudar de municipio-base", resposta.identificacao.aceita_outros_municipios.value),
        _linha_se_preenchida("Ja possui domicilio eleitoral", resposta.identificacao.possui_domicilio_eleitoral.value),
        _linha_se_preenchida("Objetivo principal", (resposta.objetivos.objetivo_principal or "").replace("_", " ") or None),
        _linha_se_preenchida("Horizonte temporal", (resposta.objetivos.horizonte_temporal or "").replace("_", " ") or None),
        _linha_se_preenchida("Aceita concorrer a outro cargo no futuro mesmo perdendo este", resposta.objetivos.aceita_outro_cargo.value),
    ]
    for item in _linhas_contexto:
        if item:
            st.markdown(f"**{item[0]}:** {item[1]}")
    st.caption("Texto/flags livres acima - nao entram em nenhum indice numerico, so na narrativa da estrategia.")

    # -------------------------------------------------------- Elegibilidade
    elegibilidade = resposta.elegibilidade
    if any([
        elegibilidade.data_filiacao_partidaria, elegibilidade.prestacao_contas_em_dia,
        elegibilidade.pendencia_justica_eleitoral, elegibilidade.data_domicilio_eleitoral,
    ]):
        st.divider()
        st.markdown("### ⚖️ Elegibilidade e situacao juridico-partidaria")
        _explicacao(
            "Datas declaradas ficam so na narrativa (nunca em formula) - o prazo legal exato de "
            "filiacao/desincompatibilizacao muda por cargo e por eleicao, conferir contra a regra "
            "vigente antes de decidir qualquer coisa em cima disso."
        )
        if elegibilidade.pendencia_justica_eleitoral == SimNao.SIM:
            st.warning("Pendencia conhecida na Justica Eleitoral declarada.")
            if elegibilidade.contexto_pendencia_justica:
                st.caption(elegibilidade.contexto_pendencia_justica)
        for item in [
            _linha_se_preenchida("Filiado ao partido desde", elegibilidade.data_filiacao_partidaria),
            _linha_se_preenchida("Domicilio eleitoral desde", elegibilidade.data_domicilio_eleitoral),
            _linha_se_preenchida("Prestacao de contas de campanhas anteriores em dia", elegibilidade.prestacao_contas_em_dia.value if elegibilidade.prestacao_contas_em_dia else None),
        ]:
            if item:
                st.markdown(f"**{item[0]}:** {item[1]}")

    # ---------------------------------------------- Apoio institucional
    ai = resposta.apoio_institucional
    apoios_declarados = []
    if ai.apoio_sindicato == SimNao.SIM:
        apoios_declarados.append(f"Sindicato(s): {', '.join(ai.sindicatos_declarados) or 'nao especificado'}")
    if ai.apoio_movimento_social == SimNao.SIM:
        apoios_declarados.append(f"Movimento social: {ai.movimento_social_qual or 'nao especificado'}")
    if ai.apoio_associacao_empresarial == SimNao.SIM:
        apoios_declarados.append(f"Associacao empresarial/comercial: {ai.associacao_empresarial_qual or 'nao especificado'}")
    if ai.midia_local_alinhada == SimNao.SIM:
        apoios_declarados.append(f"Midia local alinhada: {ai.midia_local_qual or 'nao especificado'}")
    if apoios_declarados or ai.proximidade_religiosa:
        st.divider()
        st.markdown("### 🤝 Rede de apoio institucional declarada")
        for linha in apoios_declarados:
            st.markdown(f"- {linha}")
        if ai.proximidade_religiosa:
            st.markdown(f"- Proximidade religiosa: {ai.proximidade_religiosa}")
        if not apoios_declarados and ai.proximidade_religiosa is None:
            st.caption("Nenhum apoio institucional especifico declarado.")

    # -------------------------------------------- Estrutura de campanha
    ec = resposta.estrutura_campanha
    rec = resposta.recursos
    if any([
        ec.coordenador_definido, ec.tesoureiro_definido, ec.advogado_eleitoral_contratado,
        ec.numero_cabos_eleitorais, rec.recursos_proprios_estimados, rec.doacoes_terceiros_estimadas,
        rec.expectativa_fundo_eleitoral, rec.agencia_publicidade_contratada,
    ]):
        st.divider()
        st.markdown("### 🏗️ Estrutura de campanha e orcamento")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Coordenador definido:** {ec.coordenador_definido.value if ec.coordenador_definido else 'nao respondido'}")
        c2.markdown(f"**Tesoureiro definido:** {ec.tesoureiro_definido.value if ec.tesoureiro_definido else 'nao respondido'}")
        c3.markdown(f"**Advogado eleitoral contratado:** {ec.advogado_eleitoral_contratado.value if ec.advogado_eleitoral_contratado else 'nao respondido'}")
        if ec.numero_cabos_eleitorais is not None:
            st.markdown(f"**Cabos eleitorais/voluntarios mobilizaveis:** {ec.numero_cabos_eleitorais}")
        linhas_orcamento = [
            _linha_se_preenchida("Recursos proprios estimados (R$)", f"{rec.recursos_proprios_estimados:,.2f}" if rec.recursos_proprios_estimados is not None else None),
            _linha_se_preenchida("Doacoes de terceiros estimadas (R$)", f"{rec.doacoes_terceiros_estimadas:,.2f}" if rec.doacoes_terceiros_estimadas is not None else None),
            _linha_se_preenchida("Expectativa de Fundo Eleitoral/Partidario (R$)", f"{rec.expectativa_fundo_eleitoral:,.2f}" if rec.expectativa_fundo_eleitoral is not None else None),
            _linha_se_preenchida("Agencia de publicidade contratada", rec.agencia_publicidade_contratada.value if rec.agencia_publicidade_contratada else None),
        ]
        for item in linhas_orcamento:
            if item:
                st.markdown(f"**{item[0]}:** {item[1]}")

    # ------------------------------------------------- Chapa e cronograma
    chapa, crono = resposta.chapa, resposta.cronograma
    if any([chapa.coligacao_formada, chapa.nome_coligacao, chapa.candidato_vice, crono.numero_urna_definido, crono.material_grafico_pronto, crono.data_convencao_partidaria]):
        st.divider()
        st.markdown("### 🗳️ Chapa, coligacao e cronograma")
        for item in [
            _linha_se_preenchida("Chapa/coligacao formada", chapa.coligacao_formada.value if chapa.coligacao_formada else None),
            _linha_se_preenchida("Nome da coligacao", chapa.nome_coligacao),
            _linha_se_preenchida("Candidato(a) a vice", chapa.candidato_vice),
            _linha_se_preenchida("Numero de urna definido", crono.numero_urna if crono.numero_urna_definido == SimNao.SIM else (crono.numero_urna_definido.value if crono.numero_urna_definido else None)),
            _linha_se_preenchida("Material grafico pronto (logo/slogan)", crono.material_grafico_pronto.value if crono.material_grafico_pronto else None),
            _linha_se_preenchida("Data prevista de convencao partidaria", crono.data_convencao_partidaria),
        ]:
            if item:
                st.markdown(f"**{item[0]}:** {item[1]}")

    # ------------------------------------------------ Perfil demografico
    pd_ = resposta.perfil_demografico
    if any([pd_.data_nascimento, pd_.genero, pd_.cor_raca_autodeclarada, pd_.escolaridade, pd_.ocupacao_atual, pd_.estado_civil]):
        st.divider()
        st.markdown("### 🧑 Perfil demografico declarado")
        _explicacao(
            "Mesmas categorias que o TSE usa pra candidatos reais - por enquanto so alimenta a "
            "narrativa: o pacote de dados nacionais deste projeto nao inclui as colunas "
            "demograficas do TSE (removidas na reducao pra caber no pacote da nuvem), entao nao ha "
            "comparacao automatica contra candidatos reais parecidos ainda."
        )
        cols_demo = st.columns(3)
        for i, item in enumerate([
            _linha_se_preenchida("Data de nascimento", pd_.data_nascimento),
            _linha_se_preenchida("Genero", pd_.genero),
            _linha_se_preenchida("Cor/raca autodeclarada", pd_.cor_raca_autodeclarada),
            _linha_se_preenchida("Escolaridade", pd_.escolaridade),
            _linha_se_preenchida("Ocupacao atual", pd_.ocupacao_atual),
            _linha_se_preenchida("Estado civil", pd_.estado_civil),
        ]):
            if item:
                cols_demo[i % 3].markdown(f"**{item[0]}:** {item[1]}")

    # ---------------------------------------------------- Redes sociais
    rs = resposta.redes_sociais
    handles = [
        _linha_se_preenchida("Instagram", rs.instagram), _linha_se_preenchida("TikTok", rs.tiktok),
        _linha_se_preenchida("X/Twitter", rs.x_twitter), _linha_se_preenchida("Facebook", rs.facebook),
        _linha_se_preenchida("YouTube", rs.youtube),
    ]
    if any(handles):
        st.divider()
        st.markdown("### 📱 Redes sociais declaradas")
        for item in handles:
            if item:
                st.markdown(f"- **{item[0]}:** {item[1]}")
        st.caption("Links usados so como evidencia citavel na narrativa - nunca coletados automaticamente.")

    # --------------------------------- Riscos e vulnerabilidades factuais
    pos = resposta.posicionamento
    if pos.processo_judicial_conhecido == SimNao.SIM or pos.controversia_publica_conhecida == SimNao.SIM:
        st.divider()
        st.markdown("### ⚠️ Riscos e vulnerabilidades declaradas")
        if pos.processo_judicial_conhecido == SimNao.SIM:
            st.warning("Processo judicial relevante e publicamente conhecido declarado.")
            if pos.contexto_processo_judicial:
                st.caption(pos.contexto_processo_judicial)
        if pos.controversia_publica_conhecida == SimNao.SIM:
            st.warning("Controversia publica significativa declarada.")
            if pos.contexto_controversia_publica:
                st.caption(pos.contexto_controversia_publica)

    # ------------------------------------------ Trajetoria real (autobusca)
    analise_propria = None
    if resposta.identificacao.ja_disputou_eleicao == SimNao.SIM:
        st.divider()
        st.markdown("### 🔎 Trajetoria eleitoral real (autobusca no TSE)")
        nome_proprio = resposta.identificacao.nome_completo_eleitoral
        if not nome_proprio:
            st.info(
                "Informe o 'Nome completo usado em candidaturas anteriores' no formulario para "
                "cruzar com o registro real do TSE e substituir parte da autoavaliacao por dado "
                "real ja disputado."
            )
        else:
            analise_propria = analisar_padrinho_politico(nome_proprio, resposta.identificacao.uf)
            if analise_propria.encontrado_no_tse:
                cp = analise_propria.candidatura_encontrada
                st.success(
                    f"Encontrado no TSE: **{cp.nome_urna}** ({cp.nome_completo}) - "
                    f"{cp.cargo.title()}/{cp.uf} - eleicao {cp.ano_eleicao} - {cp.resultado_final}."
                )
                kpis_prop = st.columns(4)
                _kpi(kpis_prop[0], "Cargo disputado", cp.cargo.title())
                _kpi(kpis_prop[1], "Votos (disputa real)", f"{cp.total_votos:,}".replace(",", "."))
                _kpi(kpis_prop[2], "Indice de Desempenho Politico (IDP) real", f"{analise_propria.indice_forca_idp:.0f}/100")
                _kpi(kpis_prop[3], "Classificacao", analise_propria.classificacao_forca.replace("_", " ").title())
                if analise_propria.top_territorios is not None and not analise_propria.top_territorios.empty:
                    st.markdown("**Territorios reais de melhor desempenho:**")
                    st.dataframe(analise_propria.top_territorios, use_container_width=True, hide_index=True)
            else:
                st.warning(
                    f"'{nome_proprio}' nao foi encontrado no registro de candidatos do TSE "
                    f"(2018/2022/2024) na UF {resposta.identificacao.uf} - a trajetoria segue so "
                    f"em autoavaliacao categorica."
                )

    # -------------------------------------------------------------- Padrinho
    analise_padrinho = None
    if resposta.identificacao.possui_padrinho_politico == SimNao.SIM:
        st.divider()
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
                label_pauta = pautas_labels.get(ranking_pauta.pauta_id, ranking_pauta.pauta_id)
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

        if analise_propria is not None and analise_propria.encontrado_no_tse:
            st.caption(
                "Trajetoria real encontrada para este candidato (secao acima) - a comparacao "
                "abaixo ja pode usar o IDP real dele, nao so autoavaliacao."
            )
        else:
            st.caption(
                "Assimetria metodologica: os rivais acima tem indices de desempenho real (IDP/IVE/IEC/QEC, "
                "calculados sobre voto ja disputado) - o candidato deste questionario ainda nao tem um "
                "equivalente, porque isso exige voto real de uma eleicao ja disputada (ou, se ele ja "
                "disputou antes, informar o nome completo eleitoral acima pra autobusca encontrar). Os "
                "indices mostrados para ele (Prontidao/Competitividade/Potencial/Risco) sao autoavaliacao "
                "categorica, nao a mesma escala do IDP dos rivais - nunca compare os dois numeros diretamente."
            )

        if resposta.posicionamento.adversarios_declarados or resposta.posicionamento.aliados_declarados:
            st.markdown("**Percepcao declarada pelo candidato vs. rivais reais calculados**")
            nomes_rivais_reais = {r.candidatura.nome_urna.upper() for r in resultado_rivais.rivais}
            for adversario in resposta.posicionamento.adversarios_declarados:
                convergiu = any(adversario.strip().upper() in nome or nome in adversario.strip().upper() for nome in nomes_rivais_reais)
                st.markdown(f"- **{adversario}** (declarado como adversario) - {'✅ tambem aparece nos rivais reais calculados' if convergiu else '— nao aparece no top de rivais reais calculados'}")
            for aliado in resposta.posicionamento.aliados_declarados:
                st.markdown(f"- **{aliado}** (declarado como aliado)")
            st.caption("Comparacao informativa - a percepcao declarada nunca substitui o calculo real acima.")

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

    # ---------------------------------------------------------- Pesquisa propria
    pp = resposta.pesquisa_propria
    if pp.ja_realizou_pesquisa == SimNao.SIM:
        st.divider()
        st.markdown("### 📊 Pesquisa eleitoral propria declarada")
        _explicacao("Sempre autodeclarada - nunca tratada como dado verificado, diferente do resto do SIET.")
        for item in [
            _linha_se_preenchida("Instituto", pp.instituto_declarado),
            _linha_se_preenchida("Data da pesquisa", pp.data_pesquisa),
            _linha_se_preenchida("Percentual declarado", f"{pp.percentual_declarado}%" if pp.percentual_declarado is not None else None),
        ]:
            if item:
                st.markdown(f"**{item[0]}:** {item[1]}")

    # ---------------------------------------------------------- Pautas detalhadas
    if propostas_pauta:
        st.divider()
        st.subheader("Pautas detalhadas (Modo 3 completo)")
        for proposta in propostas_pauta:
            indices_pauta = calcular_indices_pauta(proposta)
            classificacao_pauta = classificar_pauta(indices_pauta)
            gate = verificar_gate_competencia(proposta.pauta_id, proposta.cargo_analisado)
            plataforma = montar_plataforma(proposta, indices_pauta, classificacao_pauta)
            with st.container(border=True):
                st.markdown(f"**{pautas_labels.get(proposta.pauta_id, proposta.pauta_id)}**")
                r_geral = indices_pauta["indice_geral_prioridade"]
                kpis_pauta = st.columns(2)
                _kpi(kpis_pauta[0], "Indice Geral de Prioridade", f"{r_geral.valor:.0f}/100", _rotulo_classificacao(r_geral), _tom_indice(r_geral.valor, False))
                gate_txt = "APROVADO" if gate.aprovado else "REPROVADO"
                _kpi(kpis_pauta[1], "Gate de competencia do cargo", gate_txt, gate.motivo, "bom" if gate.aprovado else "ruim")
                st.markdown(f"**Orgao responsavel:** {plataforma.orgao_responsavel}")
                st.markdown(f"**Custo estimado:** {plataforma.custo_estimado}")
