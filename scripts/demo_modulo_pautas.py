"""Demonstracao end-to-end do Modulo de Pautas/Plataforma (Modo 3 da
expansao SIET): proposta -> 20 indices -> classificacao de prioridade ->
plataforma (com gate de competencia do cargo). Dados 100% ficticios.

Rodar de dentro da raiz do projeto:
    .venv\\Scripts\\python.exe scripts\\demo_modulo_pautas.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.indicators.policy_indices import calcular_indices_pauta
from src.platforms.platform_builder import montar_plataforma
from src.profiles.policy_classification import classificar_pauta
from src.questionnaire.candidate_questionnaire import NivelIntensidade as N
from src.questionnaire.candidate_questionnaire import SimNao
from src.questionnaire.policy_questionnaire import PropostaPauta

# ---------------------------------------------------------------------
# Pauta ficticia: fila de espera em creches, proposta de um Prefeito.
# ---------------------------------------------------------------------
proposta = PropostaPauta(
    pauta_id="primeira_infancia",
    cargo_analisado="Prefeito",
    problema_central="Fila de espera de 800 criancas por vaga em creche no municipio ficticio.",
    publico_afetado="Familias com criancas de 0 a 3 anos, sobretudo na regiao periferica",
    territorio_afetado="Bairros da regiao periferica do municipio ficticio",
    proposta_principal="Construir 4 novos CEIs nos bairros com maior fila",
    propostas_complementares=["Ampliar convenios com creches comunitarias", "Programa de auxilio-creche emergencial"],
    gravidade_problema=N.MUITO_ALTA,
    urgencia=N.ALTA,
    abrangencia_territorial=N.ALTA,
    aderencia_candidato=N.ALTA,
    credibilidade_candidato=N.MODERADA,
    experiencia_anterior_candidato=N.MODERADA,
    saturacao_outros_candidatos=N.MODERADA,
    diferenciacao=N.MODERADA,
    risco_juridico=N.BAIXA,
    risco_fiscal=N.ALTA,
    risco_rejeicao=N.BAIXA,
    potencial_comunicacao=N.ALTA,
    potencial_mobilizacao=N.ALTA,
    coerencia_com_outras_pautas=N.MODERADA,
    dados_comprovam_problema=SimNao.SIM,
    existe_estimativa_custo=SimNao.NAO,
    existe_fonte_financiamento=SimNao.NAO,
    existe_prazo_definido=SimNao.NAO,
    existe_indicador_resultado=SimNao.SIM,
    existe_meta_definida=SimNao.NAO,
    depende_outro_ente=SimNao.SIM,
    exige_alteracao_legislativa=SimNao.NAO,
    exige_parceria=SimNao.SIM,
)

indices = calcular_indices_pauta(proposta)
classificacao = classificar_pauta(indices)
plataforma = montar_plataforma(proposta, indices, classificacao)

print(f"Pauta: {proposta.area()['label']} ({proposta.pauta_id})")
print(f"Cargo analisado: {proposta.cargo_analisado}")
print(f"Taxa de preenchimento: {proposta.taxa_preenchimento()}% | Cobertura dos indices: {indices.cobertura_geral_pct}%\n")

print(f"{'Indice':30s} {'Nota':>6s}  {'Classificacao':16s} {'Cobertura':>10s}")
print("-" * 70)
for nome, r in indices.indices.items():
    marca = " (nota alta = pior)" if r.pior_quando_alto else ""
    print(f"{nome:30s} {r.valor:6.1f}  {r.classificacao:16s} {r.cobertura_pct:8.1f}%{marca}")

print(f"\nClassificacao principal: {classificacao.classificacao_principal}")
print(f"Tambem aplicavel: {classificacao.tambem_aplicavel}")

print("\n--- Plataforma gerada ---")
print(f"Gate de competencia: {'APROVADO' if plataforma.gate.aprovado else 'REPROVADO'} - {plataforma.gate.motivo}")
print(f"Orgao responsavel: {plataforma.orgao_responsavel}")
print(f"Custo estimado: {plataforma.custo_estimado}")
print(f"Fonte de recursos: {plataforma.fonte_recursos}")
print(f"Parceiros: {plataforma.parceiros}")
print(f"Causas: {plataforma.causas}")
print(f"Justificativa tecnica: {plataforma.justificativa_tecnica}")

print(
    "\nAVISO METODOLOGICO: os indices e a classificacao acima sao "
    "autoavaliacao categorica declarada no formulario de pauta - nao sao "
    "dado oficial de politica publica. O orgao responsavel e a base legal "
    "SAO reais, lidos de config/policy_areas.yaml."
)
