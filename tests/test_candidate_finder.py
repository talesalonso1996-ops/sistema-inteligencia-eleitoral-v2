from src.candidate_finder import buscar_candidaturas, eleicao_mais_recente, registro_candidatos_disputa
from src.geographic_analysis import _UFS_BRASIL


def test_buscar_candidaturas_encontra_multiplas_para_numero_ambiguo():
    candidaturas = buscar_candidaturas(15900)
    assert len(candidaturas) > 1, "numero 15900 deve aparecer em varios municipios/UFs"
    municipios = {c.municipio for c in candidaturas}
    assert "SÃO PAULO" in municipios


def test_candidaturas_cobrem_mais_de_uma_uf():
    """O numero 15900 e' um numero de vereador comum - deve aparecer em
    municipios de VARIAS UFs, nao so SP (busca e' nacional)."""
    candidaturas = buscar_candidaturas(15900)
    ufs = {c.uf for c in candidaturas}
    assert len(ufs) > 1
    assert "SP" in ufs


def test_candidaturas_tem_campos_obrigatorios_preenchidos():
    candidaturas = buscar_candidaturas(15900)
    for c in candidaturas:
        assert c.numero == 15900
        assert c.uf in _UFS_BRASIL
        assert c.ano_eleicao == 2024
        assert c.total_votos >= 0
        assert c.partido_sigla


def test_eleicao_mais_recente_filtra_por_ano_e_turno_maximos():
    candidaturas = buscar_candidaturas(15900)
    mais_recentes = eleicao_mais_recente(candidaturas)
    assert mais_recentes, "deveria haver ao menos uma candidatura na eleicao mais recente"
    ano_max = max(c.ano_eleicao for c in candidaturas)
    assert all(c.ano_eleicao == ano_max for c in mais_recentes)


def test_numero_inexistente_retorna_lista_vazia():
    candidaturas = buscar_candidaturas(999999)
    assert candidaturas == []


def test_registro_candidatos_disputa_exclui_situacao_nula():
    """Caso real verificado: Pitangueiras/SP, numero 30000, vereador - o
    registro (consulta_cand) mantinha 2 linhas para esse numero (a
    candidatura anulada '#NULO' + a substituta que de fato concorreu).
    Sem filtrar '#NULO', essa candidatura aparecia duplicada na tabela de
    Concorrencia (merge how="left" em ranking_disputa)."""
    candidatura = next(c for c in buscar_candidaturas(30000) if c.municipio == "PITANGUEIRAS")
    registro = registro_candidatos_disputa(candidatura)
    assert not (registro["resultado_final"] == "#NULO").any()
    assert (registro["numero"] == 30000).sum() == 1
