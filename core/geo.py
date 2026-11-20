"""Contours des communes et des sections (générés par scripts/build_geo.py)."""
import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def communes_geojson() -> dict:
    return json.loads((DATA / "communes.geojson").read_text())


@lru_cache(maxsize=1)
def _sections_par_commune() -> dict:
    out = {}
    for f in json.loads((DATA / "sections.geojson").read_text())["features"]:
        out.setdefault(f["id"].split("-")[0], []).append(f)
    return out


def sections_geojson(code_commune: str) -> dict:
    """Sections d'une commune ; id = '<code_commune>-<section>'."""
    return {"type": "FeatureCollection", "features": _sections_par_commune().get(code_commune, [])}
