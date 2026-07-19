"""Mapas interativos (Folium) - secao 14 do briefing."""
from __future__ import annotations

import folium
import geopandas as gpd
import pandas as pd
from branca.colormap import LinearColormap

_AZUL_SEQUENCIAL = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95"]


def _centro(pontos: pd.DataFrame) -> tuple[float, float]:
    return float(pontos["latitude"].mean()), float(pontos["longitude"].mean())


def mapa_locais_votacao(pontos: pd.DataFrame, nome_candidato: str) -> folium.Map:
    """Mapa de pontos: cada local de votacao vira um circulo cujo raio e
    cor refletem os votos do candidato ali."""
    validos = pontos.dropna(subset=["latitude", "longitude"])
    if validos.empty:
        return folium.Map(location=[-14.2, -51.9], zoom_start=4)

    mapa = folium.Map(location=_centro(validos), zoom_start=12, tiles="cartodbdark_matter")
    maximo = max(validos["votos_candidato"].max(), 1)
    escala = LinearColormap(_AZUL_SEQUENCIAL, vmin=0, vmax=maximo, caption=f"Votos de {nome_candidato}")

    for _, row in validos.iterrows():
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=3 + 12 * (row["votos_candidato"] / maximo) ** 0.5,
            color=escala(row["votos_candidato"]),
            fill=True,
            fill_color=escala(row["votos_candidato"]),
            fill_opacity=0.75,
            weight=1,
            popup=folium.Popup(
                f"<b>{row.get('NM_LOCAL_VOTACAO', 'Local de votacao')}</b><br>"
                f"Votos: {int(row['votos_candidato'])}",
                max_width=250,
            ),
        ).add_to(mapa)

    escala.add_to(mapa)
    return mapa


def mapa_choropleth_territorio(
    malha: gpd.GeoDataFrame,
    agregado: pd.DataFrame,
    coluna_chave_malha: str,
    coluna_chave_agregado: str,
    coluna_valor: str,
    nome_candidato: str,
    zoom_start: int = 11,
    simplificar_tolerancia: float = 0.0,
) -> folium.Map:
    """Mapa coropletico: pinta cada poligono (bairro/distrito/setor/
    municipio) pela intensidade de votos do candidato (tom sequencial
    unico - azul). `zoom_start` menor (ex.: 6-7) para malhas que cobrem uma
    UF inteira (V2, cargos estaduais) em vez de 1 municipio.

    `simplificar_tolerancia` (graus, CRS EPSG:4674): reduz o numero de
    vertices dos poligonos SO para a renderizacao do mapa (nunca afeta os
    numeros/votos calculados, so a geometria desenhada) - necessario para
    malhas grandes (ex.: contorno dissolvido dos ~645 municipios de SP tem
    ~860 mil vertices / ~37MB de GeoJSON sem simplificar, o suficiente para
    travar o navegador ao renderizar via Folium/Leaflet). 0 (padrao) = sem
    simplificacao, mantem o comportamento identico ao anterior para os
    mapas municipais (bairro/distrito/setor de 1 municipio, ja pequenos)."""
    malha_wgs84 = malha.to_crs("EPSG:4674")
    if simplificar_tolerancia > 0:
        malha_wgs84 = malha_wgs84.copy()
        malha_wgs84["geometry"] = malha_wgs84.geometry.simplify(simplificar_tolerancia, preserve_topology=True)
    dados = malha_wgs84.merge(
        agregado, left_on=coluna_chave_malha, right_on=coluna_chave_agregado, how="left"
    )
    dados[coluna_valor] = dados[coluna_valor].fillna(0)

    centroides = dados.to_crs("EPSG:31983").geometry.centroid.to_crs("EPSG:4674")
    centro_lat, centro_lon = centroides.y.mean(), centroides.x.mean()
    mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=zoom_start, tiles="cartodbdark_matter")

    escala = LinearColormap(
        _AZUL_SEQUENCIAL, vmin=0, vmax=max(dados[coluna_valor].max(), 1),
        caption=f"{coluna_valor} - {nome_candidato}",
    )

    folium.GeoJson(
        dados,
        style_function=lambda feature: {
            "fillColor": escala(feature["properties"][coluna_valor] or 0),
            "color": "#6b7280",
            "weight": 0.5,
            "fillOpacity": 0.75,
        },
        tooltip=folium.GeoJsonTooltip(fields=[coluna_chave_malha, coluna_valor]),
    ).add_to(mapa)
    escala.add_to(mapa)
    return mapa


def mapa_voronoi(voronoi_gdf: gpd.GeoDataFrame, coluna_valor: str = "densidade_votos_km2") -> folium.Map:
    """Mapa dos poligonos de Voronoi (area de influencia de cada local de
    votacao), coloridos pela densidade eleitoral (votos/km2)."""
    dados = voronoi_gdf.to_crs("EPSG:4674")
    centroides = dados.to_crs("EPSG:31983").geometry.centroid.to_crs("EPSG:4674")
    centro_lat, centro_lon = centroides.y.mean(), centroides.x.mean()
    mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=12, tiles="cartodbdark_matter")

    maximo = max(dados[coluna_valor].quantile(0.95), 1)
    escala = LinearColormap(_AZUL_SEQUENCIAL, vmin=0, vmax=maximo, caption="Densidade de votos (votos/km²)")

    folium.GeoJson(
        dados,
        style_function=lambda feature: {
            "fillColor": escala(min(feature["properties"][coluna_valor] or 0, maximo)),
            "color": "#6b7280",
            "weight": 0.5,
            "fillOpacity": 0.7,
        },
        tooltip=folium.GeoJsonTooltip(fields=["local_votacao_id", "votos_candidato", coluna_valor]),
    ).add_to(mapa)
    escala.add_to(mapa)
    return mapa
