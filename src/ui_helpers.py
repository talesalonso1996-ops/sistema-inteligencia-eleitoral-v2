"""Widgets/estilo Streamlit compartilhados entre `app.py` (SIET completo) e
`app_candidatos.py` (host dedicado ao questionario de novos candidatos).
Extraido de `app.py` para os dois hosts nunca divergirem em aparencia ou
nas regras de conversao categoria->rotulo."""
from __future__ import annotations

import streamlit as st

CSS_DASHBOARD = """
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
"""


def render_css() -> None:
    st.markdown(CSS_DASHBOARD, unsafe_allow_html=True)


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
    import pandas as pd

    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "n/d"
    return f"{v:,.0f}".replace(",", ".")


# --------------------------------------------------------- Modulo Candidato
_CARGOS_MODO1 = [
    "Vereador", "Prefeito", "Deputado Estadual", "Deputado Distrital",
    "Deputado Federal", "Senador", "Governador", "Presidente",
]


def _opcoes_nivel(NivelIntensidade):
    return {
        "-- nao respondido --": None,
        "Nenhuma": NivelIntensidade.NENHUMA,
        "Baixa": NivelIntensidade.BAIXA,
        "Moderada": NivelIntensidade.MODERADA,
        "Alta": NivelIntensidade.ALTA,
        "Muito alta": NivelIntensidade.MUITO_ALTA,
    }


def _opcoes_simnao(SimNao):
    return {"-- nao respondido --": None, "Sim": SimNao.SIM, "Nao": SimNao.NAO}


# Import tardio (evita ciclo: candidate_questionnaire nao depende de ui_helpers)
from .questionnaire.candidate_questionnaire import NivelIntensidade, SimNao  # noqa: E402

_OPCOES_NIVEL = _opcoes_nivel(NivelIntensidade)
_OPCOES_SIMNAO = _opcoes_simnao(SimNao)


def _nivel(label: str, key: str, help: str | None = None):
    return _OPCOES_NIVEL[st.selectbox(label, list(_OPCOES_NIVEL.keys()), key=key, help=help)]


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
