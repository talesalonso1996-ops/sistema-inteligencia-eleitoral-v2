"""Schema interno padronizado (contrato de saida dos adaptadores em
src/adapters/) - permite que qualquer consumidor externo (ou uma futura
eleicao, 2026/2028) trate 2022 e 2024 de forma identica sem conhecer o
formato bruto de cada ano.

IMPORTANTE: os modulos de analise portados do V1 (electoral_metrics.py,
competitor_analysis.py, etc.) continuam consumindo o formato ja existente
(`Candidatura`, dataframes com colunas como `numero`/`cargo`/`QT_VOTOS`) -
esse schema padronizado NAO substitui esse formato internamente (portar
por copia, sem reescrever logica interna, e o que preserva a metodologia
ja validada). Ele e o contrato PUBLICO de `ElectionAdapter.normalize_*`,
para uso por integracoes futuras/novos modulos que queiram um formato
estavel entre anos, sem se acoplar aos nomes de coluna brutos do TSE."""
from __future__ import annotations

CANDIDATE_FIELDS: tuple[str, ...] = (
    "election_year",
    "election_type",
    "round_number",
    "state_code",
    "state_name",
    "municipality_code",
    "municipality_name",
    "office_code",
    "office_name",
    "candidate_sequence",
    "candidate_number",
    "candidate_name",
    "ballot_name",
    "party_number",
    "party_abbreviation",
    "party_name",
    "federation_name",
    "coalition_name",
    "candidacy_status",
    "result_status",
    "is_elected",
)

VOTE_FIELDS: tuple[str, ...] = (
    "election_year",
    "round_number",
    "state_code",
    "municipality_code",
    "electoral_zone",
    "electoral_section",
    "polling_place_code",
    "office_code",
    "candidate_sequence",
    "candidate_number",
    "nominal_votes",
    "valid_votes",
    "blank_votes",
    "null_votes",
    "registered_voters",
    "attendance",
    "abstention",
)

TERRITORY_FIELDS: tuple[str, ...] = (
    "state_code",
    "municipality_code",
    "municipality_name",
    "region_code",
    "region_name",
    "district_code",
    "district_name",
    "neighborhood_code",
    "neighborhood_name",
    "electoral_zone",
    "polling_place_code",
    "electoral_section",
    "latitude",
    "longitude",
    "geometry",
)
