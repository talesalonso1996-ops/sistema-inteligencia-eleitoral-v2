"""Trava a correcao do bug real de producao: para cargos MAJORITARIOS
(Prefeito/Governador/Senador/Presidente), o numero de urna do candidato
costuma SER o proprio numero do partido (ex.: Ricardo Nunes = 15 = MDB) -
o filtro de "voto de legenda" nao pode se basear so em NR_VOTAVEL bater com
um numero de partido (removia TODOS os votos reais desses candidatos,
deixando resultado_geral()/ranking_disputa() vazios/quebrados). A correcao
em src/vote_filtering.py tambem exige NM_VOTAVEL ser o nome do PARTIDO."""
from src.candidate_finder import votos_da_disputa, registro_candidatos_disputa
from src.competitor_analysis import ranking_disputa
from src.electoral_metrics import resultado_geral
from src.vote_filtering import votos_legenda, votos_nominais, votos_validos


def test_ranking_disputa_prefeito_nao_fica_vazio(candidatura_prefeito_sp):
    """Caso real que quebrava antes da correcao: ranking_disputa() para
    Prefeito de Sao Paulo 2024 retornava 0 linhas."""
    vd = votos_da_disputa(candidatura_prefeito_sp)
    rd = registro_candidatos_disputa(candidatura_prefeito_sp)
    ranking = ranking_disputa(vd, rd)
    assert len(ranking) == 10
    assert (ranking["total_votos"] > 0).all()


def test_resultado_geral_prefeito_nao_quebra(candidatura_prefeito_sp):
    """Caso real que quebrava antes da correcao: resultado_geral() para
    Prefeito de Sao Paulo 2024 levantava IndexError (ranking vazio)."""
    vd = votos_da_disputa(candidatura_prefeito_sp)
    rd = registro_candidatos_disputa(candidatura_prefeito_sp)
    resultado = resultado_geral(candidatura_prefeito_sp, vd, rd)
    assert resultado.colocacao_geral == 1
    assert resultado.total_votos == candidatura_prefeito_sp.total_votos
    assert 0 < resultado.pct_votos_validos < 100


def test_votos_legenda_prefeito_fica_vazio(candidatura_prefeito_sp):
    """Nao existe voto de legenda em cargo majoritario - votos_legenda()
    deve retornar vazio mesmo com a colisao numero-candidato==numero-partido."""
    vd = votos_da_disputa(candidatura_prefeito_sp)
    rd = registro_candidatos_disputa(candidatura_prefeito_sp)
    legenda = votos_legenda(votos_validos(vd), rd)
    assert legenda.empty


def test_votos_nominais_prefeito_preserva_todos_os_votos_validos(candidatura_prefeito_sp):
    vd = votos_da_disputa(candidatura_prefeito_sp)
    rd = registro_candidatos_disputa(candidatura_prefeito_sp)
    validos = votos_validos(vd)
    nominais = votos_nominais(vd, rd)
    assert len(nominais) == len(validos)
    assert int(nominais["QT_VOTOS"].sum()) == int(validos["QT_VOTOS"].sum())


def test_votos_legenda_vereador_continua_identico(dados_disputa):
    """Nao regressao: para Vereador (proporcional), a correcao deve manter
    exatamente o mesmo resultado de antes (verificado manualmente: 100% das
    linhas com NR_VOTAVEL=numero_partido tambem tem NM_VOTAVEL=nome_partido
    neste caso real)."""
    _, vd, rd = dados_disputa
    numeros_partido = set(rd["numero_partido"].dropna().unique())
    linhas_por_numero = vd[vd["NR_VOTAVEL"].isin(numeros_partido)]
    legenda = votos_legenda(vd, rd)
    assert len(legenda) == len(linhas_por_numero)
