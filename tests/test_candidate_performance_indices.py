"""Testes dos 4 indices de desempenho eleitoral real (IDP/IVE/IEC/QEC) -
src/indicators/candidate_performance_indices.py. Casos reais conhecidos:
LUCAS PAVANATO (1o colocado geral, Vereador/Sao Paulo 2024, eleito por QP,
161.386 votos), GARRY DERALUS (suplente, mesma disputa, 420 votos) e
TARCISIO GOMES DE FREITAS (Governador/SP 2022, 1o turno, 9.881.995 votos,
foi a 2o turno)."""
from src.candidate_finder import (
    buscar_candidatos_disputa,
    registro_candidatos_disputa,
    registro_candidatos_disputa_generalizado,
    votos_da_candidatura,
    votos_da_candidatura_generalizado,
    votos_da_disputa,
    votos_da_disputa_generalizado,
)
from src.indicators.candidate_performance_indices import calcular_indices_desempenho_real

_SP_CAPITAL = 71072


def _pavanato_e_deralus():
    """LUCAS PAVANATO (numero 22022, 1o colocado geral, eleito por QP,
    161.386 votos) e GARRY DERALUS (numero 13010, suplente, 420 votos) -
    mesma disputa real, Vereador/Sao Paulo 2024."""
    pavanato = buscar_candidatos_disputa(2024, "VEREADOR", "SP", municipio_codigo=_SP_CAPITAL, turno=1, numero=22022)[0]
    deralus = buscar_candidatos_disputa(2024, "VEREADOR", "SP", municipio_codigo=_SP_CAPITAL, turno=1, numero=13010)[0]
    return pavanato, deralus


def test_candidato_forte_tem_idp_alto_e_candidato_fraco_idp_baixo():
    """LUCAS PAVANATO (1o colocado geral, eleito) precisa ter IDP muito mais
    alto que GARRY DERALUS (suplente, 420 votos), na mesma disputa."""
    pavanato, deralus = _pavanato_e_deralus()

    vd = votos_da_disputa(pavanato)
    rd = registro_candidatos_disputa(pavanato)

    r_pavanato = calcular_indices_desempenho_real(
        pavanato, votos_da_candidatura(pavanato), vd, rd, "NR_ZONA",
    )
    r_deralus = calcular_indices_desempenho_real(
        deralus, votos_da_candidatura(deralus), vd, rd, "NR_ZONA",
    )
    assert r_pavanato.idp.valor > r_deralus.idp.valor
    assert r_pavanato.idp.classificacao == "excelente"
    assert r_deralus.idp.classificacao in ("critico", "fraco")


def test_todos_os_valores_ficam_entre_0_e_100():
    pavanato, _ = _pavanato_e_deralus()
    vc = votos_da_candidatura(pavanato)
    vd = votos_da_disputa(pavanato)
    rd = registro_candidatos_disputa(pavanato)
    r = calcular_indices_desempenho_real(pavanato, vc, vd, rd, "NR_ZONA")
    for indice in (r.idp, r.ive, r.iec, r.qec):
        assert 0.0 <= indice.valor <= 100.0
        assert 0.0 <= indice.cobertura_pct <= 100.0


def test_ive_e_o_unico_com_nota_alta_e_pior():
    pavanato, _ = _pavanato_e_deralus()
    vc = votos_da_candidatura(pavanato)
    vd = votos_da_disputa(pavanato)
    rd = registro_candidatos_disputa(pavanato)
    r = calcular_indices_desempenho_real(pavanato, vc, vd, rd, "NR_ZONA")
    assert r.ive.nota_alta_e_pior is True
    assert r.idp.nota_alta_e_pior is False
    assert r.iec.nota_alta_e_pior is False
    assert r.qec.nota_alta_e_pior is False


def test_qec_funciona_em_disputa_majoritaria_real():
    """Achado real documentado em config/indicators.yaml: QEC (baseado em
    'dominio' de territorio, margem >= 15%) fica perto de zero em disputas
    proporcionais concorridas, mas funciona bem em disputas majoritarias -
    valida isso com Tarcisio (Governador/SP 2022, 1o turno)."""
    tarcisio = buscar_candidatos_disputa(2022, "GOVERNADOR", "SP", turno=1, numero=10)[0]
    vc = votos_da_candidatura_generalizado(tarcisio)
    vd = votos_da_disputa_generalizado(tarcisio)
    rd = registro_candidatos_disputa_generalizado(tarcisio)
    r = calcular_indices_desempenho_real(tarcisio, vc, vd, rd, "CD_MUNICIPIO")
    assert r.qec.valor > 30
    assert r.qec.cobertura_pct > 0


def test_idp_degrada_graciosamente_quando_ainda_nao_ha_eleito_no_turno(caplog):
    """1o turno de disputa que teve 2o turno (ex.: Governador) nao tem
    NENHUM candidato com resultado_final='ELEITO' ainda - proximidade_eleicao
    fica indisponivel e o peso e redistribuido, nunca inventado."""
    tarcisio = buscar_candidatos_disputa(2022, "GOVERNADOR", "SP", turno=1, numero=10)[0]
    vc = votos_da_candidatura_generalizado(tarcisio)
    vd = votos_da_disputa_generalizado(tarcisio)
    rd = registro_candidatos_disputa_generalizado(tarcisio)
    r = calcular_indices_desempenho_real(tarcisio, vc, vd, rd, "CD_MUNICIPIO")
    assert r.idp.cobertura_pct < 100.0
    assert r.idp.valor == 100.0  # 1o colocado disparado mesmo com o componente ausente


def test_mesma_disputa_reaproveita_vd_rd_para_calcular_indices_de_qualquer_rival():
    """Confirma o design central do modulo: vd/rd sao os MESMOS objetos para
    o candidato-alvo e qualquer rival da mesma disputa - so vc muda."""
    pavanato, deralus = _pavanato_e_deralus()
    vd = votos_da_disputa(pavanato)
    rd = registro_candidatos_disputa(pavanato)

    r_pavanato = calcular_indices_desempenho_real(pavanato, votos_da_candidatura(pavanato), vd, rd, "NR_ZONA")
    r_deralus = calcular_indices_desempenho_real(deralus, votos_da_candidatura(deralus), vd, rd, "NR_ZONA")
    assert r_pavanato.valores() != r_deralus.valores()
