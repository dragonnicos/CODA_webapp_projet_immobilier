"""API JSON (FastAPI). Valide les paramètres puis délègue à core.services, jamais aux callbacks Dash."""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from core import services

TypeBien = Literal["Tous", "Maison", "Appartement"]
Annee = Query(None, ge=2021, le=2025, description="Année (2021-2025)")

router = APIRouter(tags=["immobilier"])


def _404(e: services.CommuneInconnue):
    return HTTPException(404, str(e))


def _appel(fonction, *args, **kwargs):
    """Appelle un service et traduit ses erreurs métier en codes HTTP."""
    try:
        return fonction(*args, **kwargs)
    except services.CommuneInconnue as e:
        raise HTTPException(404, str(e))
    except services.ParametreInvalide as e:
        raise HTTPException(422, str(e))
    except services.ModeleIndisponible as e:
        raise HTTPException(503, str(e))


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


# ---------------------------------------------------------------- tendance, prévision, estimation
Surface = Query(100, ge=9, le=400, description="Surface habitable en m²")
Pieces = Query(None, ge=1, le=10, description="Nombre de pièces (optionnel)")
Terrain = Query(None, ge=0, le=100_000, description="Surface de terrain en m² (optionnel, utile pour une maison)")
AnneeAchat = Query(2026, ge=2026, le=2030, description="Année d'achat visée (2026-2030) ; au-delà de 2028 la confiance est faible")
BienType = Literal["Maison", "Appartement"]


@router.get("/tendance", summary="Évolution du prix médian au m² par trimestre (Loiret)")
def tendance(type: TypeBien = "Tous", annee_min: int | None = Annee, annee_max: int | None = Annee):
    return services.tendance(type, annee_min, annee_max)


@router.get("/variation-communes", summary="Variation du prix médian entre le début et la fin de la période, par commune")
def variation_communes(
    type: TypeBien = "Tous",
    annee_min: int = Query(2021, ge=2021, le=2025),
    annee_max: int = Query(2025, ge=2021, le=2025),
    fiables_seulement: bool = True,
    tri: Literal["hausse", "baisse"] = "hausse",
    limite: int = Query(50, ge=1, le=400),
):
    return _appel(services.variation, type, annee_min, annee_max, fiables_seulement, tri, limite)


@router.get("/communes/{code_commune}/evolution", summary="Prix médian au m² par année pour une commune")
def evolution(code_commune: str, type: TypeBien = "Tous", annee_min: int | None = Annee, annee_max: int | None = Annee):
    return _appel(services.evolution_commune, code_commune, type, annee_min, annee_max)


@router.get("/marche", summary="Indice de prix par zone (historique) et prévision avec fourchette")
def marche(type: BienType = "Maison"):
    return _appel(services.marche, type)


@router.get("/estimation", summary="Estimation du prix d'un bien dans une commune (modèle ML)")
def estimation(
    code_commune: str = Query(description="Code INSEE, ex. 45234"),
    type: BienType = "Maison",
    surface: float = Surface,
    pieces: int | None = Pieces,
    terrain: float | None = Terrain,
    annee: int = AnneeAchat,
    budget: int | None = Query(None, ge=10_000, le=2_000_000, description="Budget en € (optionnel) : ajoute le statut"),
):
    return _appel(services.estimation, code_commune, type, surface, pieces, terrain, annee, budget)


@router.get("/projet", summary="Projet d'achat : communes où le bien décrit tient dans le budget (modèle ML)")
def projet(
    budget: int = Query(250_000, ge=10_000, le=2_000_000, description="Budget maximum en €"),
    type: BienType = "Maison",
    surface: float = Surface,
    pieces: int | None = Pieces,
    terrain: float | None = Terrain,
    annee: int = AnneeAchat,
    fiables_seulement: bool = True,
    statuts: list[Literal["sûr", "possible", "hors budget"]] | None = Query(None),
    limite: int = Query(30, ge=1, le=400),
):
    return _appel(services.projet, budget, type, surface, pieces, terrain, annee, fiables_seulement, statuts, limite)
