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
from datetime import date, datetime, timezone
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


def valor_normalizado_numerico(campo: str, valor: int | float | None) -> float | None:
    """Normaliza uma resposta numerica real (numero_territorios_presenca,
    seguidores_redes, capacidade_arrecadacao) usando o teto de referencia
    declarado em config/weights.yaml - normalizacao linear, saturando em
    100. Mais preciso que faixa categorica (Nenhuma/Baixa/.../Muito Alta)
    para perguntas que tem resposta numerica natural."""
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
    # Nome completo usado em candidaturas ANTERIORES (so relevante quando
    # ja_disputou_eleicao == SIM) - usado por src/godfather_analysis.py:
    # analisar_padrinho_politico (funcao generica por nome+UF, reaproveitada
    # aqui pra buscar a PROPRIA trajetoria real do candidato no TSE, nao so
    # a do padrinho) - quando encontrado, mostra IDP/IVE/IEC/QEC real dele
    # em vez de depender so de autoavaliacao pra secao Trajetoria.
    nome_completo_eleitoral: str | None = None


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
    # Texto livre complementar (opcional) - a faixa acima continua
    # alimentando o indice (precisa ser categorica pra ficar comparavel
    # entre candidatos), este campo so entra na narrativa/estrategia,
    # nunca em formula.
    contexto_relacionamento_liderancas: str | None = None
    # Lista de bairros/regioes REAIS onde o candidato declara ja ter
    # presenca, contato ou vinculo pessoal (mora, nasceu, trabalha) - dado
    # declarado (nunca inferido/fabricado), usado pelo modulo de
    # territorios sugeridos (src/territory_recommendations.py) como um dos
    # 3 sinais reais para recomendar onde priorizar campanha.
    bairros_presenca_declarados: list[str] = field(default_factory=list)
    relacionamento_vereadores: NivelIntensidade | None = None
    relacionamento_prefeitos: NivelIntensidade | None = None
    relacionamento_deputados: NivelIntensidade | None = None
    relacionamento_entidades: NivelIntensidade | None = None
    liderancas_regionais: NivelIntensidade | None = None
    apoio_do_partido: NivelIntensidade | None = None


@dataclass
class ApoioInstitucional:
    """Rede de apoio institucional detalhada - substitui a pergunta
    generica 'relacionamento com entidades' (que continua existindo em
    BaseEleitoral) por sinais especificos e mais uteis pro plano de
    campanha real. Alimenta o Indice de Capilaridade Institucional (conta
    quantos tipos distintos de apoio existem - ver campos_numericos)."""

    apoio_sindicato: SimNao | None = None
    sindicatos_declarados: list[str] = field(default_factory=list)
    # Texto livre, nunca categorico forcado - tema sensivel demais pra
    # espremer numa escala Nenhuma/Baixa/.../Muito Alta.
    proximidade_religiosa: str | None = None
    apoio_movimento_social: SimNao | None = None
    movimento_social_qual: str | None = None
    apoio_associacao_empresarial: SimNao | None = None
    associacao_empresarial_qual: str | None = None
    midia_local_alinhada: SimNao | None = None
    midia_local_qual: str | None = None


@dataclass
class EstruturaCampanha:
    """Estrutura e equipe de campanha - alimenta o Indice de Estrutura de
    Campanha."""

    coordenador_definido: SimNao | None = None
    tesoureiro_definido: SimNao | None = None
    advogado_eleitoral_contratado: SimNao | None = None
    numero_cabos_eleitorais: int | None = None  # contagem real, nao faixa


@dataclass
class Elegibilidade:
    """Situacao juridico-partidaria - fatos declarados (nao autoavaliacao
    categorica), usados pro Indice de Prontidao Juridico-Partidaria e pra
    narrativa/alertas do relatorio. As DATAS ficam so na narrativa, NUNCA
    entram em formula: o prazo legal exato de filiacao partidaria e
    desincompatibilizacao muda por cargo e e definido em lei/resolucao do
    TSE especifica de cada eleicao - este projeto nao replica esse calculo
    (risco real de aplicar uma regra desatualizada ou errada), so registra
    a data declarada pra quem monta a estrategia conferir contra a regra
    vigente."""

    data_filiacao_partidaria: date | None = None
    prestacao_contas_em_dia: SimNao | None = None
    pendencia_justica_eleitoral: SimNao | None = None
    contexto_pendencia_justica: str | None = None
    data_domicilio_eleitoral: date | None = None


@dataclass
class Chapa:
    """Composicao de chapa/coligacao - relevante pra cargos proporcionais
    (Vereador/Dep. Estadual/Dep. Federal) e pra Vice em cargos majoritarios.
    Fato declarado, narrativa do relatorio - nao entra em indice numerico."""

    coligacao_formada: SimNao | None = None
    nome_coligacao: str | None = None
    candidato_vice: str | None = None


@dataclass
class Cronograma:
    """Prontidao de material e cronograma de campanha - fato declarado,
    checklist/narrativa do relatorio, nao entra em indice numerico."""

    numero_urna_definido: SimNao | None = None
    numero_urna: int | None = None
    material_grafico_pronto: SimNao | None = None
    data_convencao_partidaria: date | None = None


@dataclass
class PerfilDemografico:
    """Perfil demografico autodeclarado - mesmas categorias que o registro
    real de candidatos do TSE (consulta_cand) usa, pra permitir comparacao
    direta no futuro.

    LIMITACAO ATUAL, documentada e nao escondida: o pacote de dados
    nacionais deste projeto (config/data_sources.yaml:pacote_cloud) NAO
    inclui as colunas demograficas do TSE (foram removidas na reducao pra
    caber no pacote publicado na nuvem - ver scripts/preparar_dados_nacionais.py).
    Por isso, por enquanto, estes campos alimentam so a narrativa/relatorio -
    nao ha comparacao automatica contra candidatos reais parecidos ainda
    (exigiria reprocessar o pipeline local e republicar o release
    'dados-v2' com essas colunas, fora do escopo desta rodada)."""

    data_nascimento: date | None = None
    genero: str | None = None
    cor_raca_autodeclarada: str | None = None
    escolaridade: str | None = None
    ocupacao_atual: str | None = None
    estado_civil: str | None = None


@dataclass
class RedesSociais:
    """Handles/links de redes sociais - usados so como evidencia citavel na
    narrativa do relatorio (nunca scraping automatico - mesmo principio de
    'nunca chama busca externa automatica' ja documentado em
    src/godfather_analysis.py). Diferente de `Comunicacao.seguidores_redes`
    (numero agregado, entra em indice) - aqui sao os links/handles em si."""

    instagram: str | None = None
    tiktok: str | None = None
    x_twitter: str | None = None
    facebook: str | None = None
    youtube: str | None = None


@dataclass
class PesquisaPropria:
    """Pesquisa eleitoral propria ja realizada (opcional) - sempre
    autodeclarada, nunca tratada como dado verificado (rotular sempre como
    tal na UI/relatorio). Campo deixado pronto pra um cruzamento futuro com
    o Agregador de Pesquisas Eleitorais (projeto irmao deste) - nao
    implementado nesta rodada, fora de escopo."""

    ja_realizou_pesquisa: SimNao | None = None
    instituto_declarado: str | None = None
    data_pesquisa: date | None = None
    percentual_declarado: float | None = None


@dataclass
class Comunicacao:
    """Secao 8.4 do briefing."""

    conhecimento_espontaneo: NivelIntensidade | None = None
    oratoria: NivelIntensidade | None = None
    desempenho_videos: NivelIntensidade | None = None
    entrevistas: NivelIntensidade | None = None
    debates: NivelIntensidade | None = None
    resposta_criticas: NivelIntensidade | None = None
    seguidores_redes: int | None = None  # numero real, nao faixa (ver valor_normalizado_numerico)
    engajamento: NivelIntensidade | None = None
    producao_conteudo: NivelIntensidade | None = None
    equipe_comunicacao: NivelIntensidade | None = None
    rejeicao_percebida: NivelIntensidade | None = None


@dataclass
class Recursos:
    """Secao 8.5 do briefing."""

    disponibilidade_tempo: NivelIntensidade | None = None
    capacidade_investimento_legal: NivelIntensidade | None = None
    capacidade_arrecadacao: float | None = None  # valor real em R$, nao faixa (ver valor_normalizado_numerico)
    equipe: NivelIntensidade | None = None
    transporte: NivelIntensidade | None = None
    locais_reuniao: NivelIntensidade | None = None
    audiovisual: NivelIntensidade | None = None
    disponibilidade_viagens: NivelIntensidade | None = None
    # Patrimonio pessoal ATUAL declarado (R$, valor real, nao faixa) -
    # DIFERENTE de capacidade_arrecadacao (meta de arrecadacao de CAMPANHA).
    # Nao entra em nenhum indice/formula (evitaria misturar autoavaliacao
    # com dado real no mesmo numero) - so alimenta uma comparacao direta
    # contra o patrimonio REAL declarado ao TSE pelos rivais projetados
    # (src/candidate_assets.py:carregar_patrimonio_candidato, ja resolvido
    # como Candidatura real em src/rivals/hypothetical_rivals.py).
    patrimonio_pessoal_declarado: float | None = None
    # Orcamento detalhado (secao 12 do plano de melhoria) - separa a meta
    # de arrecadacao unica (capacidade_arrecadacao acima) em fontes, pra
    # narrativa/planejamento financeiro mais preciso. Nao entram em nenhum
    # indice (evita duplicar peso com capacidade_arrecadacao, que ja mede
    # a meta agregada).
    recursos_proprios_estimados: float | None = None
    doacoes_terceiros_estimadas: float | None = None
    expectativa_fundo_eleitoral: float | None = None
    agencia_publicidade_contratada: SimNao | None = None


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
    # IDs de pauta do catalogo REAL de 35 pautas (config/policy_areas.yaml,
    # mesmo catalogo do Modo 3) - diferente de temas_identificacao (texto
    # livre, so narrativa), este campo referencia pautas reais e estruturadas
    # para permitir cruzamento automatico com dado real do Censo IBGE por
    # territorio (src/territory_recommendations.py) - nunca inferido a
    # partir do texto livre (evita match fuzzy/impreciso).
    pautas_prioritarias: list[str] = field(default_factory=list)
    # Visao do PROPRIO candidato sobre o cenario competitivo - SEMPRE numa
    # camada separada do dado real (nunca substitui, so compara). Na tela
    # de resultado, cruzado contra src/rivals/hypothetical_rivals.py
    # (rivais projetados REAIS) pra mostrar convergencia/divergencia entre
    # percepcao declarada e dado real - o valor esta na diferenca entre
    # os dois, nunca em tratar a percepcao como fato.
    adversarios_declarados: list[str] = field(default_factory=list)
    aliados_declarados: list[str] = field(default_factory=list)
    # Riscos e vulnerabilidades factuais - aprofunda resistencia_ataques
    # (que continua existindo, autoavaliacao categorica). Tema sensivel:
    # sempre autodeclarado pelo proprio candidato, nunca puxado de fonte
    # externa sem ele declarar primeiro.
    processo_judicial_conhecido: SimNao | None = None
    contexto_processo_judicial: str | None = None
    controversia_publica_conhecida: SimNao | None = None
    contexto_controversia_publica: str | None = None


@dataclass
class Objetivos:
    """Secao 8.7 do briefing."""

    objetivo_principal: str | None = None  # "vencer" | "capital_politico" | "conhecimento" | "base_futura" | "fortalecer_partido" | "representar_pauta"
    horizonte_temporal: str | None = None  # "esta_eleicao" | "proxima_eleicao" | "longo_prazo"
    risco_aceito: NivelIntensidade | None = None
    aceita_outro_cargo: SimNao = SimNao.NAO


@dataclass
class RespostaQuestionario:
    """Agrega todas as secoes do questionario (base da secao 8 do briefing,
    ampliada com elegibilidade, apoio institucional, estrutura de campanha,
    chapa, cronograma, perfil demografico, redes sociais e pesquisa
    propria). Uma instancia = uma analise de candidato."""

    identificacao: IdentificacaoAnalise
    trajetoria: Trajetoria = field(default_factory=Trajetoria)
    base_eleitoral: BaseEleitoral = field(default_factory=BaseEleitoral)
    apoio_institucional: ApoioInstitucional = field(default_factory=ApoioInstitucional)
    comunicacao: Comunicacao = field(default_factory=Comunicacao)
    redes_sociais: RedesSociais = field(default_factory=RedesSociais)
    recursos: Recursos = field(default_factory=Recursos)
    estrutura_campanha: EstruturaCampanha = field(default_factory=EstruturaCampanha)
    posicionamento: Posicionamento = field(default_factory=Posicionamento)
    objetivos: Objetivos = field(default_factory=Objetivos)
    elegibilidade: Elegibilidade = field(default_factory=Elegibilidade)
    chapa: Chapa = field(default_factory=Chapa)
    cronograma: Cronograma = field(default_factory=Cronograma)
    perfil_demografico: PerfilDemografico = field(default_factory=PerfilDemografico)
    pesquisa_propria: PesquisaPropria = field(default_factory=PesquisaPropria)
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
        out["seguidores_redes"] = valor_normalizado_numerico(
            "seguidores_redes", self.comunicacao.seguidores_redes
        )
        out["capacidade_arrecadacao"] = valor_normalizado_numerico(
            "capacidade_arrecadacao", self.recursos.capacidade_arrecadacao
        )
        out["mandato_anterior"] = valor_normativo(self.trajetoria.mandato_anterior)
        out["partido_definido"] = valor_normativo(self.identificacao.partido_definido)
        out["numero_cabos_eleitorais"] = valor_normalizado_numerico(
            "numero_cabos_eleitorais", self.estrutura_campanha.numero_cabos_eleitorais
        )
        out["prestacao_contas_em_dia"] = valor_normativo(self.elegibilidade.prestacao_contas_em_dia)
        out["coordenador_definido"] = valor_normativo(self.estrutura_campanha.coordenador_definido)
        out["tesoureiro_definido"] = valor_normativo(self.estrutura_campanha.tesoureiro_definido)
        out["advogado_eleitoral_contratado"] = valor_normativo(
            self.estrutura_campanha.advogado_eleitoral_contratado
        )

        campos_categoricos_diretos = {
            "conhecimento_espontaneo": self.comunicacao.conhecimento_espontaneo,
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

        # ausencia_pendencia_justica e o inverso de pendencia_justica_eleitoral
        # (mesmo padrao de indisciplina acima) - usado no Indice de Prontidao
        # Juridico-Partidaria: pendencia=SIM deve PIORAR o indice, entao o
        # campo que entra na formula e a ausencia (100 - valor).
        pendencia_justica = valor_normativo(self.elegibilidade.pendencia_justica_eleitoral)
        out["ausencia_pendencia_justica"] = (
            None if pendencia_justica is None else round(100.0 - pendencia_justica, 1)
        )

        # capilaridade_institucional_contagem: quantos TIPOS distintos de
        # apoio institucional foram declarados como SIM, entre os
        # respondidos (nao e media de nivel, e contagem - diferente do
        # resto dos campos aqui). None so se NENHUM dos 4 foi respondido -
        # nunca preenche com estimativa (mesma regra do resto do modulo).
        flags_institucionais = [
            self.apoio_institucional.apoio_sindicato,
            self.apoio_institucional.apoio_movimento_social,
            self.apoio_institucional.apoio_associacao_empresarial,
            self.apoio_institucional.midia_local_alinhada,
        ]
        respondidas = [f for f in flags_institucionais if f is not None]
        if respondidas:
            n_sim = sum(1 for f in respondidas if f == SimNao.SIM)
            out["capilaridade_institucional_contagem"] = round(100.0 * n_sim / len(respondidas), 1)
        else:
            out["capilaridade_institucional_contagem"] = None

        return out

    def taxa_preenchimento(self) -> float:
        """% de campos numericos efetivamente respondidos - usado como
        cobertura_pct nos indices (mesmo padrao de IDP/IVE/IEC/QEC de
        sessoes anteriores: nunca esconder quanto do indice e dado real)."""
        valores = self.campos_numericos().values()
        respondidos = sum(1 for v in valores if v is not None)
        return round(100.0 * respondidos / len(valores), 1) if valores else 0.0
