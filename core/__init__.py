"""Logique métier partagée (Dash aujourd'hui, FastAPI/MCP en phase 3). Aucune dépendance à Dash."""
from .config import SEUIL_FIABLE, FILTRES_SOURCE, LIMITES, SOURCE
from .data import get_df
from .geo import communes_geojson, sections_geojson
from .noms import noms_sections
from .indice import zones_communes, indice_marche, niveau_communes
from .ml import estimer, estimer_communes, evaluation as evaluation_ml
from .prevision import prevision_indice, projet, comparer_annees, projet_par_zone, erreur_horizon
from .profil import taille_par_pieces, dispersion_communes
from .tendance import evolution_marche, evolution_communes, variation_communes, fenetres
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
    "liste_communes", "communes_geojson", "sections_geojson",
    "noms_sections", "estimer", "estimer_communes", "evaluation_ml", "prevision_indice", "projet", "comparer_annees", "projet_par_zone", "erreur_horizon", "zones_communes", "indice_marche", "niveau_communes", "taille_par_pieces", "dispersion_communes",
    "evolution_marche", "evolution_communes", "variation_communes", "fenetres",
]
