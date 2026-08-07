"""Demonstracao end-to-end do Modulo Candidato (Modo 1 da expansao SIET):
questionario -> 20 indices -> arquetipo. Dados 100% ficticios (secao 34).

Rodar de dentro da raiz do projeto:
    .venv\\Scripts\\python.exe scripts\\demo_modulo_candidato.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.indicators.candidate_indices import calcular_indices_candidato
from src.profiles.candidate_archetype import classificar_arquetipo
from src.questionnaire.candidate_questionnaire import (
    BaseEleitoral,
    Comunicacao,
    IdentificacaoAnalise,
    NivelIntensidade as N,
    Posicionamento,
    Recursos,
    RespostaQuestionario,
    SimNao,
    Trajetoria,
)

# ---------------------------------------------------------------------
# Questionario ficticio: professora universitaria, atuacao comunitaria
# forte, pouca estrutura partidaria, presenca digital moderada.
# ---------------------------------------------------------------------
resposta = RespostaQuestionario(
    identificacao=IdentificacaoAnalise(
        cargo_pretendido="Vereadora",
        uf="SP",
        municipio_base="Município Fictício",
        partido_definido=SimNao.SIM,
        ja_disputou_eleicao=SimNao.NAO,
    ),
    trajetoria=Trajetoria(
        tempo_atuacao_publica=N.ALTA,
        mandato_anterior=SimNao.NAO,
        experiencia_politica_geral=N.MODERADA,
        atuacao_administrativa=N.BAIXA,
        projetos_realizados=N.ALTA,
        resultados_concretos=N.ALTA,
    ),
    base_eleitoral=BaseEleitoral(
        numero_territorios_presenca=8,
        estrutura_bairros=N.MODERADA,
        apoiadores_mobilizaveis=N.ALTA,
        capacidade_eventos=N.MODERADA,
        relacionamento_liderancas=N.ALTA,
        relacionamento_vereadores=N.BAIXA,
        relacionamento_prefeitos=N.NENHUMA,
        relacionamento_deputados=N.NENHUMA,
        relacionamento_entidades=N.ALTA,
        liderancas_regionais=N.BAIXA,
        apoio_do_partido=N.MODERADA,
    ),
    comunicacao=Comunicacao(
        conhecimento_espontaneo=N.BAIXA,
        oratoria=N.ALTA,
        desempenho_videos=N.MODERADA,
        entrevistas=N.MODERADA,
        debates=N.ALTA,
        resposta_criticas=N.MODERADA,
        seguidores_redes=N.MODERADA,
        engajamento=N.MODERADA,
        producao_conteudo=N.BAIXA,
        equipe_comunicacao=N.NENHUMA,
        rejeicao_percebida=N.BAIXA,
    ),
    recursos=Recursos(
        disponibilidade_tempo=N.ALTA,
        capacidade_investimento_legal=N.BAIXA,
        capacidade_arrecadacao=N.BAIXA,
        equipe=N.BAIXA,
        transporte=N.MODERADA,
        locais_reuniao=N.MODERADA,
        audiovisual=N.NENHUMA,
        disponibilidade_viagens=N.MODERADA,
    ),
    posicionamento=Posicionamento(
        temas_identificacao=["educação", "primeira infância"],
        resistencia_ataques=N.MODERADA,
        disciplina=N.ALTA,
    ),
)

indices = calcular_indices_candidato(resposta)
arquetipo = classificar_arquetipo(indices)

print(f"Analise ficticia - {resposta.identificacao.cargo_pretendido}/{resposta.identificacao.uf}")
print(f"Taxa de preenchimento do questionario: {resposta.taxa_preenchimento()}%")
print(f"Cobertura geral dos indices: {indices.cobertura_geral_pct}%\n")

print(f"{'Indice':35s} {'Nota':>6s}  {'Classificacao':16s} {'Cobertura':>10s}")
print("-" * 75)
for nome, r in indices.indices.items():
    marca = " (nota alta = pior)" if r.pior_quando_alto else ""
    print(f"{nome:35s} {r.valor:6.1f}  {r.classificacao:16s} {r.cobertura_pct:8.1f}%{marca}")

print(f"\nArquetipo principal: {arquetipo.arquetipo_principal}")
print(f"Arquetipos secundarios: {arquetipo.arquetipos_secundarios}")
print(f"Cargos compativeis (do arquetipo principal): {arquetipo.cargos_compativeis}")
print(f"Evidencia (condicao satisfeita): {arquetipo.evidencias.get(arquetipo.arquetipo_principal)}")

print(
    "\nAVISO METODOLOGICO: todos os indices acima sao autoavaliacao "
    "categorica declarada no questionario - nao sao medicao objetiva de "
    "dado eleitoral (diferente dos indices de territorio do SIET, "
    "calculados a partir de TSE/IBGE reais). Ver ETAPA1_ARQUITETURA.md secao 4."
)
