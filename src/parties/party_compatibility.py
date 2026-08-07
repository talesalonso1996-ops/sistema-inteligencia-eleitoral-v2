"""Compatibilidade partidaria (secao 22 do briefing de expansao SIET).

Mesma logica metodologica do modulo de rivais (`src/rivals/hypothetical_rivals.py`):
como o candidato ainda nao disputou, nao existe "desempenho do partido dele"
para medir diretamente. Em vez de opiniao/afinidade ideologica, este modulo
mede o HISTORICO REAL do partido na mesma disputa comparavel mais recente
(reaproveitando `resolver_disputa_comparavel_cargo`, o mesmo dado real usado
para identificar rivais) - quantos candidatos o partido lancou, quantos se
elegeram, a melhor colocacao e como isso se compara ao piso real de quem se
elegeu naquela disputa."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..candidate_finder import Candidatura
from ..rivals.hypothetical_rivals import DisputaComparavel, resolver_disputa_comparavel_cargo
from ..utils import get_logger

logger = get_logger(__name__)


@dataclass
class ResultadoCompatibilidadePartidaria:
    disputa: DisputaComparavel
    partido_sigla: str
    n_candidatos_partido: int = 0
    n_eleitos_partido: int = 0
    melhor_colocacao_partido: int | None = None
    votos_melhor_candidato_partido: int | None = None
    piso_real_da_disputa: int | None = None  # menor total_votos entre os eleitos da disputa comparavel
    taxa_sucesso_partido: float | None = None  # n_eleitos_partido / n_candidatos_partido, quando houver candidatos
    candidatos_partido: list[Candidatura] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def avaliar_compatibilidade_partidaria(
    partido_sigla: str, cargo_pretendido_label: str, uf: str, municipio_base: str
) -> ResultadoCompatibilidadePartidaria:
    """Avalia o historico real de `partido_sigla` na disputa comparavel mais
    recente para o cargo/UF/municipio informados. Nunca infere afinidade
    ideologica ou probabilidade de apoio - apenas o que o partido de fato
    fez na disputa real mais proxima disponivel."""
    disputa = resolver_disputa_comparavel_cargo(cargo_pretendido_label, uf, municipio_base)
    sigla_alvo = partido_sigla.strip().upper()

    if not disputa.candidatos:
        return ResultadoCompatibilidadePartidaria(disputa=disputa, partido_sigla=sigla_alvo, avisos=list(disputa.avisos))

    eleitos = [c for c in disputa.candidatos if c.resultado_final.upper().startswith("ELEITO")]
    piso_real = min((c.total_votos for c in eleitos), default=None)

    candidatos_partido = sorted(
        (c for c in disputa.candidatos if c.partido_sigla.strip().upper() == sigla_alvo),
        key=lambda c: c.total_votos,
        reverse=True,
    )

    avisos = list(disputa.avisos)
    if not candidatos_partido:
        avisos.append(
            f"O partido {sigla_alvo} nao lancou candidato a {disputa.cargo_tse} em {uf}"
            f"{'/' + disputa.municipio_nome if disputa.municipio_nome else ''} em {disputa.ano} - "
            f"sem historico real direto para avaliar compatibilidade nessa disputa comparavel."
        )
        return ResultadoCompatibilidadePartidaria(
            disputa=disputa, partido_sigla=sigla_alvo, piso_real_da_disputa=piso_real, avisos=avisos,
        )

    eleitos_partido = [c for c in candidatos_partido if c.resultado_final.upper().startswith("ELEITO")]
    ordenados_geral = sorted(disputa.candidatos, key=lambda c: c.total_votos, reverse=True)
    melhor_do_partido = candidatos_partido[0]
    melhor_colocacao = ordenados_geral.index(melhor_do_partido) + 1

    return ResultadoCompatibilidadePartidaria(
        disputa=disputa,
        partido_sigla=sigla_alvo,
        n_candidatos_partido=len(candidatos_partido),
        n_eleitos_partido=len(eleitos_partido),
        melhor_colocacao_partido=melhor_colocacao,
        votos_melhor_candidato_partido=melhor_do_partido.total_votos,
        piso_real_da_disputa=piso_real,
        taxa_sucesso_partido=round(len(eleitos_partido) / len(candidatos_partido), 3),
        candidatos_partido=candidatos_partido,
        avisos=avisos,
    )
