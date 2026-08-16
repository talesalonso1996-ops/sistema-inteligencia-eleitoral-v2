# Sistema de Inteligencia Eleitoral

Sistema que, a partir apenas do **numero de um candidato**, localiza a
candidatura nas Eleicoes Municipais 2024 em **qualquer municipio/UF do
Brasil**, cruza dados oficiais do TSE e do IBGE (Censo Demografico 2022) e
gera analises de resultado, concorrencia, territorio, demografia,
estatistica e um relatorio executivo (HTML/PDF/Excel).

Todos os dados usados sao oficiais e locais - nenhum numero e inventado ou
estimado sem origem documentada (ver `config/data_sources.yaml`).

## Como rodar

```powershell
cd sistema_inteligencia_eleitoral
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Abra `http://localhost:8501`, digite o numero do candidato e escolha a
candidatura correta na lista (o mesmo numero pode pertencer a candidatos
de cargos/municipios diferentes).

## Fontes de dados

Todas documentadas em `config/data_sources.yaml` (fonte, ano, arquivo,
metodologia). Resumo:

| Fonte | Conteudo | Uso |
|---|---|---|
| TSE - `consulta_cand_2024` (Brasil) | Identidade, partido, coligacao, situacao, resultado final | Identificacao do candidato em qualquer UF |
| TSE - `votacao_secao_2024_{UF}` (por UF, sob demanda) | Votos por candidato/secao | Metricas, ranking, territorio |
| TSE - `eleitorado_local_votacao_2024` (Brasil) | Coordenadas de cada local de votacao | Mapas, join espacial |
| TSE - `detalhe_votacao_secao_2024` (Brasil) | Comparecimento/abstencao/brancos/nulos por secao | Indice de performance |
| IBGE - malha de setores/bairros CD2022 (por UF, sob demanda) | Malhas de setor censitario e bairro | Geografia, Voronoi |
| IBGE - Agregados por Setores Censitarios 2022 (Brasil: demografia, cor/raca, alfabetizacao, renda do responsavel) | Perfil demografico por setor | Demografia, correlacao, regressao, clustering |
| MTE - RAIS Estabelecimentos / Novo CAGED (Brasil, por municipio) | Vinculos formais ativos, saldo de admissoes/desligamentos | Contexto economico do municipio |

Duas categorias de fonte: **nacionais** (registro de candidatos, eleitorado
por local de votacao, detalhe de secao, agregados censitarios, RAIS/CAGED) -
arquivos leves (dezenas de MB no total), sempre disponiveis via GitHub
Release (`src/cloud_data_bootstrap.py`); e **por UF, sob demanda**
(votacao_secao - o maior arquivo do sistema, >1GB em estados grandes - e a
malha de setores/bairros) - baixadas e convertidas automaticamente (TSE cdn
+ IBGE geoftp) na primeira busca de um candidato daquele estado (ver
`src/uf_data_bootstrap.py`), e ficam em cache local para as buscas
seguintes. Nenhum desses arquivos e carregado inteiro em memoria: todas as
consultas usam DuckDB com projecao de colunas e filtros aplicados durante a
leitura. Resultados de consultas repetidas sao cacheados em `data/cache/`
(parquet).

### Limitacoes conhecidas

- **Malha geografica por UF**: a malha de setor censitario/bairro (IBGE
  CD2022) e baixada sob demanda para qualquer UF - mas o IBGE nao publica
  o produto "bairros" para todas as UFs (ex.: Tocantins). Quando ausente,
  o sistema usa "distrito" (setor censitario) como nivel alternativo e
  informa a limitacao, nunca simula um poligono.
- **Bairro na capital de SP**: a malha oficial de "bairro" do IBGE nao cobre
  o municipio de Sao Paulo (usa "distrito" oficial como nivel alternativo).
- **Primeira busca em uma UF nova**: baixa e converte a votacao oficial
  daquele estado (pode levar alguns minutos em estados grandes); buscas
  seguintes na mesma UF (mesma sessao/container) sao rapidas.
- **Perfil demografico por local de votacao**: aproximado pelo setor
  censitario onde o local fica fisicamente localizado - nao captura
  eleitores que se deslocam de outros setores.
- **Regressao/correlacao por territorio**: dados agregados (ecological
  regression) - nao permitem inferencia sobre o comportamento de eleitores
  individuais.
- **Indice de performance (0-100)**: mede forca *relativa* entre os
  territorios do proprio candidato (normalizacao min-max), nao dominio
  eleitoral absoluto. Pesos ajustaveis em `config/indicators.yaml`.
- Variaveis genericas de caracteristicas do domicilio ("dom1/dom2/dom3")
  foram deliberadamente excluidas por falta de identificacao clara
  (ver `variaveis_excluidas_automaticamente` em `config/data_sources.yaml`).

## Arquitetura

```
config/            YAML: fontes de dados, configuracoes gerais, pesos do indice
src/
  candidate_finder.py     Busca/desambiguacao de candidaturas em qualquer UF (DuckDB)
  uf_data_bootstrap.py    Download/conversao sob demanda por UF (votacao_secao + malha)
  cloud_data_bootstrap.py Download do pacote nacional (sempre disponivel) via GitHub Release
  tse_downloader.py       Download local-first dos arquivos do TSE
  ibge_downloader.py      Download local-first dos arquivos do IBGE
  data_cleaning.py        Correcao de coordenadas/numeros corrompidos
  data_validation.py      Validacoes de qualidade (nao interrompem o pipeline)
  electoral_metrics.py    Resultado geral e desempenho territorial
  competitor_analysis.py  Ranking de concorrentes, zonas de disputa
  geographic_analysis.py  Join espacial local de votacao -> setor/bairro
  voronoi_analysis.py     Diagrama de Voronoi (area de influencia)
  demographic_analysis.py Cruzamento com o Censo 2022 (IBGE)
  correlation_analysis.py Correlacao votos x demografia
  regression_models.py    Regressao linear (OLS)
  clustering.py           Segmentacao de territorios (K-Means)
  potential_index.py      Indice de Performance Eleitoral (0-100)
  charts.py               Graficos Plotly (paleta fixa e acessivel)
  maps.py                 Mapas Folium (pontos, coropletico, Voronoi)
  report_generator.py     Relatorio executivo HTML + PDF
  excel_exporter.py       Exportacao Excel multi-abas
app.py              Interface Streamlit (abas: Resumo, Concorrentes,
                    Territorio, Geografia, Demografia, Estatistica, Relatorio)
tests/              Testes automatizados (pytest)
```

## Testes

```powershell
.venv\Scripts\python -m pytest tests -v
```

## Modulo Candidato (expansao em andamento)

Primeira fatia de uma expansao maior do sistema (candidato + territorio +
pautas + analise integrada, com 4 modos de uso e relatorios longos). O
territorio (este README, acima) ja existia e continua identico. O que foi
adicionado nesta etapa e o **Modo 1 - Candidato**: um questionario de
autoavaliacao (nao dado eleitoral) que gera 20 indices de perfil e um
arquetipo politico-eleitoral.

```
src/questionnaire/candidate_questionnaire.py   Schema do questionario + escala categoria->nota
src/indicators/candidate_indices.py            Os 20 indices (0-100, pesos configuraveis)
src/profiles/candidate_archetype.py            Classificacao de arquetipo
config/weights.yaml                            Pesos e regras normativas (editavel sem mexer em codigo)
scripts/demo_modulo_candidato.py               Demonstracao end-to-end com dado ficticio
```

**Aviso metodologico importante**: diferente dos indices de territorio
acima (calculados a partir de dado real do TSE/IBGE), os 20 indices do
Modulo Candidato nascem de **autoavaliacao categorica** (nenhuma/baixa/
moderada/alta/muito alta) preenchida pelo proprio candidato ou por quem
responde em seu nome. Sao escores normativos, nunca medicao objetiva -
rotulados como tal em todo lugar que aparecem. Detalhe completo da decisao
metodologica e do roteiro das proximas etapas (pautas, rivais, matriz
integrada, relatorios de ~50 paginas) em `ETAPA1_ARQUITETURA.md`.

Rodar a demonstracao:

```powershell
.venv\Scripts\python scripts\demo_modulo_candidato.py
```

Rodar so os testes novos:

```powershell
.venv\Scripts\python -m pytest tests/test_candidate_questionnaire.py tests/test_candidate_indices.py tests/test_candidate_archetype.py -v
```

## Host dedicado: Questionario Completo de Novos Candidatos

Segundo ponto de entrada do MESMO repositorio (nao e um projeto separado -
reaproveita `src/` inteiro, mesmo `requirements.txt`, mesmo `config/`).
Pagina unica, formulario completo (8 secoes: as 7 do Modulo Candidato acima
+ Objetivos), com ponte opcional para o questionario completo de pauta por
cada pauta prioritaria marcada, comparativo de patrimonio pessoal contra os
rivais projetados (dado real do TSE) e aviso explicito sobre a assimetria
entre o IDP real dos rivais e a autoavaliacao do candidato hipotetico.

```powershell
.venv\Scripts\python -m streamlit run app_candidatos.py --server.port 8541
```

**Persistencia**: cada envio grava um JSON em
`data/candidatos/respostas/{id_analise}.json` (`src/questionnaire/persistence.py`)
- ao contrario do resto de `data/`, esta pasta NAO esta no `.gitignore` de
proposito. Quando rodando local, isso ja e suficiente pro app grande
(`app.py`, opcao de menu "Candidatos analisados") enxergar na hora. Quando
publicado no Streamlit Community Cloud (disco efemero, nao sobrevive a
redeploy), a mesma resposta tambem e commitada direto no GitHub via API
REST (secret `GITHUB_TOKEN` em Settings -> Secrets do app na nuvem) - o
SIET local so precisa de um `git pull` pra ver os candidatos preenchidos na
versao publica.

**Deploy no Streamlit Community Cloud**: criar um 2o app apontando pro
MESMO repositorio (`talesalonso1996-ops/sistema-inteligencia-eleitoral-v2`),
branch `master`, "Main file path" = `app_candidatos.py` - nao duplica
`requirements.txt` nem dado de cache, e o token do GitHub so precisa de
permissao `contents:write` neste repositorio especifico.

## Modulo de Pautas/Plataforma (expansao em andamento)

Segunda fatia da expansao (Modo 3 do briefing): questionario de pauta de
politica publica -> 20 indices -> matriz de priorizacao -> plataforma de
governo, com verificacao de competencia federativa do cargo antes de
qualquer proposta.

```
config/policy_areas.yaml                  35 pautas, competencia federativa real (base legal citavel - CF/88)
config/policy_weights.yaml                Pesos dos 20 indices + matriz de priorizacao (secao 14.4)
src/questionnaire/policy_questionnaire.py Schema da proposta de pauta (secao 10)
src/indicators/policy_indices.py          Os 20 indices (secao 14.3)
src/profiles/policy_classification.py     Matriz de priorizacao (secao 14.4)
src/platforms/platform_builder.py         Montagem da plataforma + gate de competencia do cargo (secao 14.5)
scripts/demo_modulo_pautas.py             Demonstracao end-to-end com dado ficticio
```

Mesmo aviso metodologico do Modulo Candidato: os 20 indices sao
autoavaliacao categorica do formulario, nao dado oficial de politica
publica (isso exigiria os conectores DATASUS/INEP/SICONFI/SNIS da secao
6.3 do briefing, ainda nao integrados). A UNICA parte deste modulo que e
dado real e verificavel e a competencia federativa/base legal de cada
pauta (`config/policy_areas.yaml`), usada pelo gate de
`platform_builder.py` para nunca gerar um "orgao responsavel" incompativel
com o cargo analisado - e para nunca inventar causas/consequencias sobre
um problema real que o sistema nao conhece (esses campos ficam
explicitamente marcados como pendentes de elaboracao). Detalhe completo em
`ETAPA1_ARQUITETURA.md`.

```powershell
.venv\Scripts\python scripts\demo_modulo_pautas.py
.venv\Scripts\python -m pytest tests/test_policy_questionnaire.py tests/test_policy_indices.py tests/test_policy_classification.py tests/test_platform_builder.py -v
```
