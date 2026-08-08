"""Schema do questionario de autoavaliacao do candidato (secao 8 do
briefing de expansao SIET) e a regra de conversao categoria -> nota 0-100.

Mantem o mesmo padrao do resto do projeto: dataclasses tipadas (sem
dependencia nova de pydantic - o projeto ja usa dataclasses em todo
`src/`), config normativa em YAML (`config/weights.yaml`), nada
hardcoded no codigo que devesse estar em config.

IMPORTANTE (ver ETAPA1_ARQUITETURA.md secao 4): as respostas aqui sao
AUTOAVALIACAO CATEGORICA declarada pelo proprio candidato ou por quem
preenche em seu nome - nao sao fatos eleitorais verificados como o resto
do SIET. Nenhuma resposta deste modulo deve ser apresentada como medicao
objetiva."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from ..utils import indicators_config, load_yaml  # noqa: F401  (indicators_config mantido p/ paridade futura)


def weights_config() -> dict:
    return load_yaml("config/weights.yaml")


class NivelIntensidade(str, Enum):
    """Escala padrao de 5 faixas usada na maior parte do questionario -
    ver `escala_categorica` em config/weights.yaml. Reaproveitar uma unica
    escala em vez de uma por pergunta mantem os indices comparaveis entre
    si (mesma logica de normalizacao 0-100 usada em todo o SIET)."""

    NENHUMA = "nenhuma"
    BAIXA = "baixa"
    MODERADA = "moderada"
    ALTA = "alta"
    MUITO_ALTA = "muito_alta"


class SimNao(str, Enum):
    NAO = "nao"
    SIM = "sim"


def valor_normativo(nivel: NivelIntensidade | SimNao | None) -> float | None:
    """Converte uma resposta categorica na nota 0-100 declarada em
    config/weights.yaml. Retorna None quando a pergunta nao foi respondida
    (nunca preenche com estimativa - ver secao 4 da arquitetura)."""
    if nivel is None:
        return None
    cfg = weights_config()
    if isinstance(nivel, SimNao):
        return float(cfg["escala_binaria"][nivel.value])
    return float(cfg["escala_categorica"][nivel.value])


def valor_normalizado_numerico(campo: str, valor: int | None) -> float | None:
    """Normaliza uma resposta numerica (hoje so `numero_territorios_presenca`)
    usando o teto de referencia declarado em config/weights.yaml -
    normalizacao linear, saturando em 100."""
    if valor is None:
        return None
    teto = weights_config()["normalizacao_numerica"][campo]["teto_referencia"]
    return round(min(100.0, 100.0 * max(0, valor) / teto), 1)


@dataclass
class IdentificacaoAnalise:
    """Secao 8.1 do briefing."""

    cargo_pretendido: str  # ex.: "Deputado Estadual"
    uf: str
    municipio_base: str
    cargo_definido: SimNao = SimNao.SIM
    aceita_outros_municipios: SimNao = SimNao.NAO
    aceita_outros_cargos: SimNao = SimNao.NAO
    # partido_definido alimenta o indice de apoio_partidario (config/weights.yaml)
    # - por isso, diferente dos demais campos desta secao (que sao so
    # contexto da analise, nao entram em formula), fica None por padrao:
    # None = "nao respondido", diferente de SimNao.NAO = "respondido que
    # nao tem partido definido". Mesma regra do resto do questionario.
    partido_definido: SimNao | None = None
    # Sigla do partido (ex.: "PSB") - so preenchido quando partido_definido
    # == SIM. Usado pelos modulos de rivais/compatibilidade partidaria
    # (secoes 17/22) para comparar com partido de candidatos REAIS da
    # disputa comparavel - nao alimenta nenhum indice do Modulo Candidato
    # em si (por isso fica fora de campos_numericos()).
    partido_sigla: str | None = None
    possui_domicilio_eleitoral: SimNao = SimNao.SIM
    ja_disputou_eleicao: SimNao = SimNao.NAO
    # Mesmo tratamento de partido_definido/partido_sigla acima: fato
    # declarado (nao autoavaliacao categorica, nao alimenta formula de
    # indice - por isso fora de campos_numericos()), usado por quem monta
    # a estrategia/relatorio do candidato para levar em conta o vinculo de
    # apadrinhamento politico (fonte de apoio real, mas tambem risco de
    # associacao caso o padrinho tenha desgaste publico) - nunca inferido,
    # so aparece quando declarado explicitamente.
    possui_padrinho_politico: SimNao | None = None
    nome_padrinho_politico: str | None = None


@dataclass
class Trajetoria:
    """Secao 8.2 do briefing."""

    tempo_atuacao_publica: NivelIntensidade | None = None
    mandato_anterior: SimNao | None = None
    experiencia_politica_geral: NivelIntensidade | None = None
    atuacao_administrativa: NivelIntensidade | None = None
    projetos_realizados: NivelIntensidade | None = None
    resultados_concretos: NivelIntensidade | None = None


@dataclass
class BaseEleitoral:
    """Secao 8.3 do briefing."""

    numero_territorios_presenca: int | None = None  # contagem, nao faixa
    estrutura_bairros: NivelIntensidade | None = None
    apoiadores_mobilizaveis: NivelIntensidade | None = None
    capacidade_eventos: NivelIntensidade | None = None
    relacionamento_liderancas: NivelIntensidade | None = None
    relacionamento_vereadores: NivelIntensidade | None = None
    relacionamento_prefeitos: NivelIntensidade | None = None
    relacionamento_deputados: NivelIntensidade | None = None
    relacionamento_entidades: NivelIntensidade | None = None
    liderancas_regionais: NivelIntensidade | None = None
    apoio_do_partido: NivelIntensidade | None = None


@dataclass
class Comunicacao:
    """Secao 8.4 do briefing."""

    conhecimento_espontaneo: NivelIntensidade | None = None
    oratoria: NivelIntensidade | None = None
    desempenho_videos: NivelIntensidade | None = None
    entrevistas: NivelIntensidade | None = None
    debates: NivelIntensidade | None = None
    resposta_criticas: NivelIntensidade | None = None
    seguidores_redes: NivelIntensidade | None = None
    engajamento: NivelIntensidade | None = None
    producao_conteudo: NivelIntensidade | None = None
    equipe_comunicacao: NivelIntensidade | None = None
    rejeicao_percebida: NivelIntensidade | None = None


@dataclass
class Recursos:
    """Secao 8.5 do briefing."""

    disponibilidade_tempo: NivelIntensidade | None = None
    capacidade_investimento_legal: NivelIntensidade | None = None
    capacidade_arrecadacao: NivelIntensidade | None = None
    equipe: NivelIntensidade | None = None
    transporte: NivelIntensidade | None = None
    locais_reuniao: NivelIntensidade | None = None
    audiovisual: NivelIntensidade | None = None
    disponibilidade_viagens: NivelIntensidade | None = None


@dataclass
class Posicionamento:
    """Secao 8.6 do briefing. Campos qualitativos (texto/lista) usados na
    narrativa do relatorio e nos arquetipos - nao entram em formula
    numerica de indice, exceto resistencia_ataques/disciplina."""

    temas_identificacao: list[str] = field(default_factory=list)
    imagem_desejada: str | None = None
    estilo_lideranca: str | None = None
    resistencia_ataques: NivelIntensidade | None = None
    disciplina: NivelIntensidade | None = None
    disposicao_negociacao: NivelIntensidade | None = None
    disposicao_confronto: NivelIntensidade | None = None


@dataclass
class Objetivos:
    """Secao 8.7 do briefing."""

    objetivo_principal: str | None = None  # "vencer" | "capital_politico" | "conhecimento" | "base_futura" | "fortalecer_partido" | "representar_pauta"
    horizonte_temporal: str | None = None  # "esta_eleicao" | "proxima_eleicao" | "longo_prazo"
    risco_aceito: NivelIntensidade | None = None
    aceita_outro_cargo: SimNao = SimNao.NAO


@dataclass
class RespostaQuestionario:
    """Agrega as 7 secoes do questionario (secao 8 do briefing). Uma
    instancia = uma analise de candidato."""

    identificacao: IdentificacaoAnalise
    trajetoria: Trajetoria = field(default_factory=Trajetoria)
    base_eleitoral: BaseEleitoral = field(default_factory=BaseEleitoral)
    comunicacao: Comunicacao = field(default_factory=Comunicacao)
    recursos: Recursos = field(default_factory=Recursos)
    posicionamento: Posicionamento = field(default_factory=Posicionamento)
    objetivos: Objetivos = field(default_factory=Objetivos)
    id_analise: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def campos_numericos(self) -> dict[str, float | None]:
        """Achata todas as respostas em um dict {nome_campo: nota_0_100},
        na mesma nomenclatura usada em config/weights.yaml (indices_candidato.*.pesos).
        Campo nao respondido vira None (nunca 0 - 0 significaria "resposta
        NENHUMA", que e uma resposta real, diferente de "nao respondido")."""
        out: dict[str, float | None] = {}

        out["numero_territorios_presenca"] = valor_normalizado_numerico(
            "numero_territorios_presenca", self.base_eleitoral.numero_territorios_presenca
        )
        out["mandato_anterior"] = valor_normativo(self.trajetoria.mandato_anterior)
        out["partido_definido"] = valor_normativo(self.identificacao.partido_definido)

        campos_categoricos_diretos = {
            "conhecimento_espontaneo": self.comunicacao.conhecimento_espontaneo,
            "seguidores_redes": self.comunicacao.seguidores_redes,
            "estrutura_bairros": self.base_eleitoral.estrutura_bairros,
            "apoiadores_mobilizaveis": self.base_eleitoral.apoiadores_mobilizaveis,
            "capacidade_eventos": self.base_eleitoral.capacidade_eventos,
            "relacionamento_liderancas": self.base_eleitoral.relacionamento_liderancas,
            "relacionamento_vereadores": self.base_eleitoral.relacionamento_vereadores,
            "relacionamento_prefeitos": self.base_eleitoral.relacionamento_prefeitos,
            "relacionamento_deputados": self.base_eleitoral.relacionamento_deputados,
            "relacionamento_entidades": self.base_eleitoral.relacionamento_entidades,
            "liderancas_regionais": self.base_eleitoral.liderancas_regionais,
            "apoio_do_partido": self.base_eleitoral.apoio_do_partido,
            "equipe": self.recursos.equipe,
            "transporte": self.recursos.transporte,
            "locais_reuniao": self.recursos.locais_reuniao,
            "audiovisual": self.recursos.audiovisual,
            "capacidade_investimento_legal": self.recursos.capacidade_investimento_legal,
            "capacidade_arrecadacao": self.recursos.capacidade_arrecadacao,
            "oratoria": self.comunicacao.oratoria,
            "desempenho_videos": self.comunicacao.desempenho_videos,
            "entrevistas": self.comunicacao.entrevistas,
            "debates": self.comunicacao.debates,
            "resposta_criticas": self.comunicacao.resposta_criticas,
            "engajamento": self.comunicacao.engajamento,
            "producao_conteudo": self.comunicacao.producao_conteudo,
            "equipe_comunicacao": self.comunicacao.equipe_comunicacao,
            "projetos_realizados": self.trajetoria.projetos_realizados,
            "resultados_concretos": self.trajetoria.resultados_concretos,
            "tempo_atuacao_publica": self.trajetoria.tempo_atuacao_publica,
            "experiencia_politica_geral": self.trajetoria.experiencia_politica_geral,
            "atuacao_administrativa": self.trajetoria.atuacao_administrativa,
            "disponibilidade_tempo": self.recursos.disponibilidade_tempo,
            "disponibilidade_viagens": self.recursos.disponibilidade_viagens,
            "resistencia_ataques": self.posicionamento.resistencia_ataques,
            "disciplina": self.posicionamento.disciplina,
            "rejeicao_percebida": self.comunicacao.rejeicao_percebida,
        }
        for nome, resposta in campos_categoricos_diretos.items():
            out[nome] = valor_normativo(resposta)

        # indisciplina e o inverso de disciplina - usado so no indice de
        # risco_reputacional (config/weights.yaml), nao e uma pergunta
        # separada do questionario.
        disciplina = out.get("disciplina")
        out["indisciplina"] = None if disciplina is None else round(100.0 - disciplina, 1)

        return out

    def taxa_preenchimento(self) -> float:
        """% de campos numericos efetivamente respondidos - usado como
        cobertura_pct nos indices (mesmo padrao de IDP/IVE/IEC/QEC de
        sessoes anteriores: nunca esconder quanto do indice e dado real)."""
        valores = self.campos_numericos().values()
        respondidos = sum(1 for v in valores if v is not None)
        return round(100.0 * respondidos / len(valores), 1) if valores else 0.0
