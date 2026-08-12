"""Testes da integracao de 2026 (Eleicoes Gerais, eleicao AINDA NAO
OCORRIDA - 1o turno em outubro/2026) em candidate_finder.buscar_candidatos_disputa.

2026 cobre SOMENTE registro de candidaturas (consulta_cand_2026_BR.parquet,
gerado por scripts/preparar_consulta_cand_2026.py a partir do CSV oficial do
TSE, inspecionado via DuckDB em 2026-08-11 - ver
config/data_sources.yaml: eleicoes.2026). Nao ha votacao_secao_2026 (nem
pode haver antes da eleicao) - os testes abaixo travam o comportamento de
degradacao graciosa (sempre 0 votos, nunca uma tentativa de download) e o
fato de que TODAS as candidaturas tem DS_SIT_TOT_TURNO='#NULO' (ainda sem
decisao) sem que isso as exclua do resultado - ao contrario do que acontece
em anos ja decididos (2022/2024/2018), onde '#NULO' marca candidatura
invalidada e e' filtrada."""
from src.candidate_assets import carregar_patrimonio_candidato
from src.candidate_finder import buscar_candidatos_disputa


def test_governador_sp_2026_encontra_candidatos_reais_sem_tentar_baixar_votos():
    resultado = buscar_candidatos_disputa(2026, "GOVERNADOR", uf="SP", turno=1)
    assert resultado, "esperava pelo menos 1 candidato real a Governador/SP em 2026"
    numeros = {c.numero for c in resultado}
    assert 10 in numeros  # Tarcisio (numero real do PSD/Republicanos), candidato a reeleicao
    for c in resultado:
        assert c.ano_eleicao == 2026
        assert c.total_votos == 0
        assert c.zonas_com_votos == 0


def test_deputado_federal_sp_2026_tem_muitos_candidatos_registrados():
    resultado = buscar_candidatos_disputa(2026, "DEPUTADO FEDERAL", uf="SP", turno=1)
    assert len(resultado) > 100


def test_2026_nao_filtra_por_ds_sit_tot_turno_nulo():
    """Em 2022/2024, DS_SIT_TOT_TURNO='#NULO' marca candidatura invalidada
    e e' excluida do resultado. Em 2026 (eleicao futura) TODAS as
    candidaturas tem esse valor (ainda sem decisao) - se o filtro nao
    fosse desligado para este ano, buscar_candidatos_disputa nunca
    retornaria nada para 2026."""
    resultado = buscar_candidatos_disputa(2026, "GOVERNADOR", uf="SP", turno=1)
    assert resultado
    assert all(c.resultado_final == "#NULO" for c in resultado)


def test_bens_declarados_funciona_para_candidatura_2026_ainda_nao_ocorrida():
    """bem_candidato_2026 ja existe (candidato declara bens no ato do
    registro, antes da eleicao) - precisa funcionar mesmo sem nenhum dado
    de votacao para este ano. Elmano de Freitas (13, CE) conferido
    manualmente em 2026-08-11: 12 itens, ~R$ 366 mil."""
    candidatura = buscar_candidatos_disputa(2026, "GOVERNADOR", uf="CE", turno=1, numero=13)[0]
    perfil = carregar_patrimonio_candidato(candidatura)
    assert perfil.disponivel
    assert perfil.valor_total_bens > 0
    assert perfil.n_itens_declarados > 0


def test_2022_continua_filtrando_ds_sit_tot_turno_nulo_normalmente():
    """Guarda de regressao: a mudanca para 2026 nao pode afetar o
    comportamento ja existente de anos com eleicao decidida."""
    resultado = buscar_candidatos_disputa(2022, "GOVERNADOR", uf="SP", turno=1)
    assert resultado
    assert all(c.resultado_final != "#NULO" for c in resultado)
