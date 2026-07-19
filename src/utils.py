"""Funcoes utilitarias compartilhadas: config, logging, cache e paths."""
from __future__ import annotations

import hashlib
import logging
import logging.handlers
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=None)
def load_yaml(relative_path: str) -> dict[str, Any]:
    """Carrega um arquivo YAML de configuracao relativo a raiz do projeto."""
    path = PROJECT_ROOT / relative_path
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def settings() -> dict[str, Any]:
    return load_yaml("config/settings.yaml")


def data_sources() -> dict[str, Any]:
    return load_yaml("config/data_sources.yaml")


def indicators_config() -> dict[str, Any]:
    return load_yaml("config/indicators.yaml")


def resolve_path(relative: str) -> Path:
    """Resolve um caminho relativo configurado em settings.yaml para absoluto."""
    return PROJECT_ROOT / relative


_LOGGER_CONFIGURED = False


def get_logger(name: str = "sie") -> logging.Logger:
    """Logger unico do sistema, gravando em outputs/logs/sistema.log (secao 12/17)."""
    global _LOGGER_CONFIGURED
    logger = logging.getLogger(name)
    if not _LOGGER_CONFIGURED:
        cfg = settings()
        log_path = resolve_path(cfg["logging"]["arquivo"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        level = getattr(logging, cfg["logging"].get("nivel", "INFO"))

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )

        file_handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        root = logging.getLogger("sie")
        root.setLevel(level)
        root.addHandler(file_handler)
        root.addHandler(stream_handler)
        root.propagate = False
        _LOGGER_CONFIGURED = True
    return logger


def cache_key(*parts: Any) -> str:
    """Gera uma chave de cache estavel a partir de parametros arbitrarios."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def cache_path(namespace: str, key: str) -> Path:
    cache_dir = resolve_path(settings()["paths"]["data_cache"]) / namespace
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{key}.parquet"


def read_cache(namespace: str, key: str) -> pd.DataFrame | None:
    if not settings()["cache"]["habilitado"]:
        return None
    path = cache_path(namespace, key)
    if path.exists():
        return pd.read_parquet(path)
    return None


def write_cache(namespace: str, key: str, df: pd.DataFrame) -> None:
    if not settings()["cache"]["habilitado"]:
        return
    path = cache_path(namespace, key)
    df.to_parquet(path, index=False)


def crs_metrico_utm(longitude_media: float) -> str:
    """EPSG SIRGAS 2000 / UTM (zona sul) mais adequado para a longitude
    media de um conjunto de pontos. O Brasil cobre varias zonas UTM (17S a
    25S); usar uma zona fixa (ex.: 23S, a de Sao Paulo) para pontos de
    outras regioes do pais introduz distorcao real de area/distancia - por
    isso a zona e calculada dinamicamente a partir da longitude, em vez de
    fixa. Usado em calculos de area (Voronoi) e distancia (fallback de
    poligono mais proximo no join espacial)."""
    zona = int((longitude_media + 180) // 6) + 1
    zona = min(max(zona, 17), 25)  # zonas UTM que cobrem o territorio brasileiro
    return f"EPSG:{31960 + zona}"


def parse_tse_broken_decimal(value: Any, integer_digits: int) -> float | None:
    """Corrige campos numericos do TSE exportados com virgula decimal
    convertida incorretamente em separador de milhar (ex.: latitude
    "-239.669.088" deveria ser -23.9669088). O parametro integer_digits
    informa quantos digitos (sem contar o sinal) pertencem a parte inteira.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text in ("", "nan", "None", "-1"):
        return None
    negative = text.startswith("-")
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    if "E+" in text.upper():
        try:
            return float(text.replace(",", "."))
        except ValueError:
            return None
    if len(digits) <= integer_digits:
        result = float(digits)
    else:
        result = float(f"{digits[:integer_digits]}.{digits[integer_digits:]}")
    return -result if negative else result


@dataclass
class DataIssue:
    """Representa uma limitacao/erro de validacao (secao 17): o sistema deve
    seguir processando as demais analises mesmo quando uma etapa falha."""

    etapa: str
    severidade: str  # "erro" | "aviso"
    mensagem: str
