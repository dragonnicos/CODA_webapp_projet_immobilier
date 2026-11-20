"""Logique métier partagée (Dash aujourd'hui, FastAPI/MCP en phase 3). Aucune dépendance à Dash."""
from .config import SEUIL_FIABLE, FILTRES_SOURCE, LIMITES, SOURCE
from .data import get_df
from .geo import communes_geojson, sections_geojson
from .geo import communes_geojson, sections_geojson
from .stats import (
    resume_global,
    prix_median_communes,
    recherche_budget,
    sections_commune,
    ventes_section,
    liste_communes,
)

__all__ = [
    "SEUIL_FIABLE", "FILTRES_SOURCE", "LIMITES", "SOURCE", "get_df", "resume_global",
    "prix_median_communes", "recherche_budget", "sections_commune", "ventes_section",
    "liste_communes", "communes_geojson", "sections_geojson", "communes_geojson", "sections_geojson",
]
