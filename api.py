"""API JSON (FastAPI). Valide les paramètres puis délègue à core.services, jamais aux callbacks Dash."""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from core import services

TypeBien = Literal["Tous", "Maison", "Appartement"]
Annee = Query(None, ge=2021, le=2025, description="Année (2021-2025)")

router = APIRouter(tags=["immobilier"])


def _404(e: services.CommuneInconnue):
    return HTTPException(404, str(e))


@router.get("/resume", summary="Résumé du jeu de données")
def resume():
    return services.resume()


@router.get("/communes", summary="Liste des communes (code INSEE, nom, nombre de ventes)")
def communes():
    return services.communes()


@router.get("/prix-median", summary="Q1 : prix médian au m² par commune")
def prix_median(
    type: TypeBien = "Tous",
    annee_min: int | None = Annee,
    annee_max: int | None = Annee,
    fiables_seulement: bool = True,
    par_type: bool = True,
):
    return services.prix_median(type, annee_min, annee_max, fiables_seulement, par_type)


@router.get("/recherche-budget", summary="Q2 : communes où un bien tient dans un budget")
def recherche_budget(
    budget: int = Query(250_000, ge=10_000, le=2_000_000, description="Budget maximum en €"),
    surface_min: int = Query(100, ge=9, le=400, description="Surface bâtie minimale en m²"),
    type: Literal["Maison", "Appartement"] = "Maison",
    annee_min: int | None = Annee,
    annee_max: int | None = Annee,
    limite: int = Query(50, ge=1, le=400, description="Nombre maximal de communes renvoyées"),
):
    return services.recherche_budget(budget, surface_min, type, annee_min, annee_max, limite)


@router.get("/communes/{code_commune}/sections", summary="Drill-down : sections cadastrales d'une commune")
def sections(code_commune: str, type: TypeBien = "Tous", annee_min: int | None = Annee, annee_max: int | None = Annee):
    try:
        return services.sections(code_commune, type, annee_min, annee_max)
    except services.CommuneInconnue as e:
        raise _404(e)


@router.get("/communes/{code_commune}/ventes", summary="Drill-down : ventes d'une commune ou d'une section")
def ventes(
    code_commune: str,
    section: str | None = Query(None, max_length=2, description="Section cadastrale, ex. ZT"),
    type: TypeBien = "Tous",
    annee_min: int | None = Annee,
    annee_max: int | None = Annee,
    limite: int = Query(100, ge=1, le=500),
):
    try:
        return services.ventes(code_commune, section, type, annee_min, annee_max, limite)
    except services.CommuneInconnue as e:
        raise _404(e)
