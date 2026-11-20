"""Contours des communes et des sections (générés par scripts/build_geo.py)."""
import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def communes_geojson() -> dict:
    return json.loads((DATA / "communes.geojson").read_text())


@lru_cache(maxsize=8)  # un fichier par commune : on ne garde jamais les 12 Mo de tout le département en mémoire
def sections_geojson(code_commune: str) -> dict:
    """Sections d'une commune ; id = '<code_commune>-<section>'."""
    f = DATA / "sections" / f"{code_commune}.geojson"
    if not code_commune.isalnum() or not f.exists():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(f.read_text())
