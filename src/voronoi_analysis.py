"""Diagrama de Voronoi por local de votacao (secao 8.3 do briefing).

Cada local de votacao "controla" uma area de influencia (poligono de
Voronoi), permitindo visualizar cobertura territorial e calcular
densidade eleitoral (votos por km2) mesmo quando o local nao cai
claramente dentro de um bairro delimitado.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
import shapely

from .utils import crs_metrico_utm, get_logger

logger = get_logger(__name__)


def _fronteira_municipio(malha: gpd.GeoDataFrame) -> shapely.Geometry:
    """Uniao de todos os poligonos da malha (setores ou bairros) do
    municipio - usado para recortar o diagrama de Voronoi nos limites reais."""
    return malha.union_all()


def gerar_voronoi(
    pontos: pd.DataFrame, malha_municipio: gpd.GeoDataFrame
) -> gpd.GeoDataFrame | None:
    """Gera poligonos de Voronoi para os locais de votacao (pontos com
    lat/long validas), recortados pela fronteira do municipio. Retorna
    None se houver menos de 4 pontos (Voronoi nao e informativo)."""
    # Locais de votacao co-localizados (mesma lat/long exata - comum em
    # complexos com varios locais registrados no mesmo predio) precisam
    # virar UM ponto para o Voronoi (2 pontos identicos nao geram poligonos
    # distintos), mas os votos de cada local tem que ser somados no ponto
    # resultante - um drop_duplicates ingenuo manteria so o primeiro local e
    # descartaria silenciosamente os votos dos outros do mapa de densidade.
    com_coordenada = pontos.dropna(subset=["latitude", "longitude"])
    validos = com_coordenada.groupby(["latitude", "longitude"], as_index=False).agg(
        votos_candidato=("votos_candidato", "sum"),
        local_votacao_id=("local_votacao_id", lambda s: " / ".join(dict.fromkeys(s.astype(str)))),
    )
    if len(validos) < 4:
        logger.warning("Apenas %s locais com coordenada unica - Voronoi nao gerado.", len(validos))
        return None

    crs_metros = crs_metrico_utm(validos["longitude"].mean())
    gdf_pontos = gpd.GeoDataFrame(
        validos,
        geometry=gpd.points_from_xy(validos["longitude"], validos["latitude"]),
        crs="EPSG:4674",
    ).to_crs(crs_metros)

    fronteira = malha_municipio.to_crs(crs_metros).union_all()
    multiponto = shapely.MultiPoint(list(gdf_pontos.geometry))
    colecao = shapely.voronoi_polygons(multiponto, extend_to=fronteira)
    poligonos = gpd.GeoDataFrame(geometry=list(colecao.geoms), crs=crs_metros)
    poligonos["geometry"] = poligonos.geometry.intersection(fronteira)
    poligonos = poligonos[~poligonos.geometry.is_empty]

    # Reassocia cada poligono ao ponto (local de votacao) que ele contem.
    junto = gpd.sjoin(poligonos, gdf_pontos, how="left", predicate="contains")
    junto = junto.drop(columns=["index_right"], errors="ignore")
    junto["area_km2"] = junto.to_crs(crs_metros).geometry.area / 1_000_000
    junto["densidade_votos_km2"] = (junto["votos_candidato"] / junto["area_km2"]).round(2)
    return junto.to_crs("EPSG:4674")
