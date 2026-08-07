"""Schema do questionario de pauta/plataforma politica (secao 10 do
briefing de expansao SIET) e a regra de conversao categoria -> nota 0-100.

Reaproveita a MESMA escala categorica e as MESMAS classes NivelIntensidade/
SimNao de candidate_questionnaire.py (nao cria uma segunda tabela de
conversao - mesma razao documentada la: manter os indices comparaveis).

IMPORTANTE (mesmo aviso metodologico de candidate_questionnaire.py): os
campos de gravidade/urgencia/aderencia/credibilidade/saturacao/etc. abaixo
sao AUTOAVALIACAO de quem preenche o formulario - nao sao dado oficial de
politica publica (esse dado viria dos conectores da secao 6.3 do briefing
- DATASUS/INEP/SICONFI/SNIS -, que nao estao integrados nesta etapa; ver
ETAPA1_ARQUITETURA.md secao 1, linha "Pautas / plataforma"). Os UNICOS
campos com fonte externa verificavel aqui sao os do proprio
config/policy_areas.yaml (competencia federativa, base legal) - carregados,
nunca digitados no formulario."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .candidate_questionnaire import NivelIntensidade, SimNao, valor_normativo
from ..utils import load_yaml


def policy_areas_config() -> dict:
    return load_yaml("config/policy_areas.yaml")


def policy_weights_config() -> dict:
    return load_yaml("config/policy_weights.yaml")


def pautas_disponiveis() -> list[str]:
    """Lista as chaves validas de pauta_id (config/policy_areas.yaml)."""
    return list(policy_areas_config()["pautas"].keys())


@dataclass
class PropostaPauta:
    """Uma pauta/proposta dentro da plataforma de um candidato (secao 10
    do briefing). `pauta_id` deve ser uma chave de config/policy_areas.yaml
    - a competencia federativa e o orgao responsavel NAO sao perguntados
    aqui, sao lidos de la (dado documentado, nao digitado)."""

    pauta_id: str
    cargo_analisado: str  # mesmos rotulos de _CARGOS_MODO1 em app.py / IdentificacaoAnalise.cargo_pretendido

    # ---- descricao livre (nao entra em formula de indice, alimenta o
    # texto da plataforma gerada por platform_builder.py) ----
    problema_central: str = ""
    publico_afetado: str = ""
    territorio_afetado: str = ""
    proposta_principal: str = ""
    propostas_complementares: list[str] = field(default_factory=list)

    # ---- autoavaliacao categorica (secao 10 do briefing) ----
    gravidade_problema: NivelIntensidade | None = None
    urgencia: NivelIntensidade | None = None
    abrangencia_territorial: NivelIntensidade | None = None
    aderencia_candidato: NivelIntensidade | None = None
    credibilidade_candidato: NivelIntensidade | None = None
    experiencia_anterior_candidato: NivelIntensidade | None = None
    saturacao_outros_candidatos: NivelIntensidade | None = None
    diferenciacao: NivelIntensidade | None = None
    risco_juridico: NivelIntensidade | None = None
    risco_fiscal: NivelIntensidade | None = None
    risco_rejeicao: NivelIntensidade | None = None
    potencial_comunicacao: NivelIntensidade | None = None
    potencial_mobilizacao: NivelIntensidade | None = None
    coerencia_com_outras_pautas: NivelIntensidade | None = None

    # ---- sim/nao (secao 10 do briefing) ----
    dados_comprovam_problema: SimNao | None = None
    existe_estimativa_custo: SimNao | None = None
    existe_fonte_financiamento: SimNao | None = None
    existe_prazo_definido: SimNao | None = None
    existe_indicador_resultado: SimNao | None = None
    existe_meta_definida: SimNao | None = None
    depende_outro_ente: SimNao | None = None
    exige_alteracao_legislativa: SimNao | None = None
    exige_parceria: SimNao | None = None

    id_pauta_analise: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def area(self) -> dict:
        """Metadados reais da pauta (competencia, base legal, orgaos) -
        lidos de config/policy_areas.yaml, nunca inferidos."""
        pautas = policy_areas_config()["pautas"]
        if self.pauta_id not in pautas:
            raise ValueError(
                f"pauta_id '{self.pauta_id}' nao existe em config/policy_areas.yaml. "
                f"Opcoes validas: {list(pautas.keys())}"
            )
        return pautas[self.pauta_id]

    def campos_numericos(self) -> dict[str, float | None]:
        """Achata as respostas categoricas em {nome_campo: nota_0_100},
        mesma convencao de RespostaQuestionario.campos_numericos()."""
        out: dict[str, float | None] = {}
        diretos = {
            "gravidade_problema": self.gravidade_problema,
            "urgencia": self.urgencia,
            "abrangencia_territorial": self.abrangencia_territorial,
            "aderencia_candidato": self.aderencia_candidato,
            "credibilidade_candidato": self.credibilidade_candidato,
            "experiencia_anterior_candidato": self.experiencia_anterior_candidato,
            "saturacao_outros_candidatos": self.saturacao_outros_candidatos,
            "diferenciacao": self.diferenciacao,
            "risco_juridico": self.risco_juridico,
            "risco_fiscal": self.risco_fiscal,
            "risco_rejeicao": self.risco_rejeicao,
            "potencial_comunicacao": self.potencial_comunicacao,
            "potencial_mobilizacao": self.potencial_mobilizacao,
            "coerencia_com_outras_pautas": self.coerencia_com_outras_pautas,
        }
        for nome, resposta in diretos.items():
            out[nome] = valor_normativo(resposta)

        binarios = {
            "dados_comprovam_problema": self.dados_comprovam_problema,
            "existe_estimativa_custo": self.existe_estimativa_custo,
            "existe_fonte_financiamento": self.existe_fonte_financiamento,
            "existe_prazo_definido": self.existe_prazo_definido,
            "existe_indicador_resultado": self.existe_indicador_resultado,
            "existe_meta_definida": self.existe_meta_definida,
            "depende_outro_ente": self.depende_outro_ente,
            "exige_alteracao_legislativa": self.exige_alteracao_legislativa,
            "exige_parceria": self.exige_parceria,
        }
        for nome, resposta in binarios.items():
            out[nome] = valor_normativo(resposta)

        # campos derivados (inversos) - usados so por indices especificos
        # (viabilidade juridica/fiscal/operacional), nao sao perguntas
        # novas, mesmo padrao de "indisciplina" em candidate_questionnaire.py
        def inverso(chave: str) -> float | None:
            v = out.get(chave)
            return None if v is None else round(100.0 - v, 1)

        out["baixo_risco_juridico"] = inverso("risco_juridico")
        out["baixo_risco_fiscal"] = inverso("risco_fiscal")
        out["nao_exige_alteracao_legislativa"] = inverso("exige_alteracao_legislativa")
        out["nao_depende_outro_ente"] = inverso("depende_outro_ente")
        out["baixa_saturacao"] = inverso("saturacao_outros_candidatos")

        return out

    def taxa_preenchimento(self) -> float:
        valores = self.campos_numericos().values()
        respondidos = sum(1 for v in valores if v is not None)
        return round(100.0 * respondidos / len(valores), 1) if valores else 0.0
