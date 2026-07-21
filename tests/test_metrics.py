from src.electoral_metrics import (
    desempenho_territorial,
    enriquecer_com_comparecimento_abstencao,
    indice_concentracao_hhi,
    indice_participacao_territorial,
    resultado_geral,
)
from src.potential_index import calcular_indice_performance
from src.competitor_analysis import zonas_de_disputa


def test_resultado_geral_consistencia(candidatura_sp, dados_disputa):
    vc, vd, rd = dados_disputa
    rg = resultado_geral(candidatura_sp, vd, rd)

    assert rg.total_votos == candidatura_sp.total_votos
    assert 1 <= rg.colocacao_geral <= rg.total_concorrentes
    assert 0 <= rg.pct_votos_validos <= 100
    assert rg.votos_primeiro_colocado >= rg.total_votos
    assert rg.total_eleitos > 0


def test_desempenho_territorial_soma_bate_com_total_do_candidato(candidatura_sp, dados_disputa):
    vc, vd, rd = dados_disputa
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, "NR_ZONA")
    assert int(terr["votos_candidato"].sum()) == candidatura_sp.total_votos


def test_hhi_entre_zero_e_um(candidatura_sp, dados_disputa):
    vc, vd, rd = dados_disputa
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, "NR_ZONA")
    hhi = indice_concentracao_hhi(terr)
    assert 0 <= hhi <= 1


def test_indice_performance_dentro_de_0_100(candidatura_sp, dados_disputa):
    vc, vd, rd = dados_disputa
    terr = desempenho_territorial(candidatura_sp, vc, vd, rd, "NR_ZONA")
    hhi = indice_concentracao_hhi(terr)
    terr_class = zonas_de_disputa(terr, vd, rd, candidatura_sp, "NR_ZONA")
    indice = calcular_indice_performance(terr_class, hhi)

    assert indice["indice_performance"].between(0, 100).all()
    assert indice["classificacao"].notna().all()


def test_enriquecer_com_comparecimento_abstencao_adiciona_qt_aptos(candidatura_prefeito_sp):
    """Regressao: a funcao lia QT_APTOS do arquivo de detalhe por secao mas
    nunca agregava essa coluna no dataframe retornado - isso fazia o
    componente 'comparecimento' do indice de performance (potential_index.py)
    ficar sempre redistribuido (a checagem `'QT_APTOS' in df.columns` nunca
    era verdadeira). QT_APTOS agora precisa estar presente e ser > 0."""
    from src.candidate_finder import registro_candidatos_disputa, votos_da_candidatura, votos_da_disputa

    vc = votos_da_candidatura(candidatura_prefeito_sp)
    vd = votos_da_disputa(candidatura_prefeito_sp)
    rd = registro_candidatos_disputa(candidatura_prefeito_sp)
    terr = desempenho_territorial(candidatura_prefeito_sp, vc, vd, rd, "NR_ZONA")
    terr = enriquecer_com_comparecimento_abstencao(
        terr, candidatura_prefeito_sp.codigo_municipio_tse, candidatura_prefeito_sp.cargo, "NR_ZONA"
    )
    assert "QT_APTOS" in terr.columns
    assert terr["QT_APTOS"].notna().any()
    assert (terr["QT_APTOS"].dropna() > 0).all()


def test_indice_participacao_territorial_percentuais_plausiveis(candidatura_prefeito_sp):
    from src.candidate_finder import registro_candidatos_disputa, votos_da_candidatura, votos_da_disputa

    vc = votos_da_candidatura(candidatura_prefeito_sp)
    vd = votos_da_disputa(candidatura_prefeito_sp)
    rd = registro_candidatos_disputa(candidatura_prefeito_sp)
    terr = desempenho_territorial(candidatura_prefeito_sp, vc, vd, rd, "NR_ZONA")
    terr = enriquecer_com_comparecimento_abstencao(
        terr, candidatura_prefeito_sp.codigo_municipio_tse, candidatura_prefeito_sp.cargo, "NR_ZONA"
    )
    participacao = indice_participacao_territorial(terr)
    assert participacao["pct_comparecimento"].dropna().between(0, 100).all()
    assert participacao["pct_abstencao"].dropna().between(0, 100).all()
    # comparecimento + abstencao devem somar ~100% do eleitorado apto
    soma = participacao["pct_comparecimento"] + participacao["pct_abstencao"]
    assert soma.dropna().sub(100).abs().lt(0.5).all()
    assert participacao["pct_brancos"].dropna().between(0, 100).all()
    assert participacao["pct_nulos"].dropna().between(0, 100).all()


def test_indice_participacao_territorial_sem_dados_fica_none():
    import pandas as pd

    vazio = pd.DataFrame({"NR_ZONA": [1, 2]})
    participacao = indice_participacao_territorial(vazio)
    assert participacao["pct_abstencao"].isna().all()
