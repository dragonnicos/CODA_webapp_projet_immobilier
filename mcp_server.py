"""Serveur MCP (FastMCP) : les mêmes opérations que l'API, exposées comme outils pour une IA."""
from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from core import services

mcp = FastMCP(
    "Immobilier Loiret",
    instructions=(
        "Ventes immobilières DVF du Loiret (2021-2025, DGFiP/Etalab, Licence Ouverte 2.0), maisons et appartements. "
        "Les prix sont des MÉDIANES ; donne toujours le nombre de ventes avec le prix et signale les résultats "
        "où `fiable` est false (moins de 10 ventes). DVF ne dit rien de l'état, de l'étage ni du DPE, et n'a pas d'adresse "
        "(la section cadastrale est le niveau le plus fin). Pour une commune par son nom, appelle d'abord `lister_communes` "
        "afin d'obtenir son code INSEE (Orléans = 45234)."
    ),
)

LECTURE = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False}
Annee = Annotated[int | None, Field(ge=2021, le=2025, description="Année (2021-2025), optionnel")]
TypeBien = Literal["Tous", "Maison", "Appartement"]


def _appel(fonction, *args, **kwargs):
    try:
        return fonction(*args, **kwargs)
    except services.CommuneInconnue as e:
        raise ToolError(str(e))


@mcp.tool(annotations=LECTURE)
def resume_donnees() -> dict:
    """Présente le jeu de données : nombre de ventes, de communes, période, limites à connaître."""
    return services.resume()


@mcp.tool(annotations=LECTURE)
def lister_communes() -> dict:
    """Liste les 325 communes du Loiret avec leur code INSEE et leur nombre de ventes (pour retrouver un code à partir d'un nom)."""
    return services.communes()


@mcp.tool(annotations=LECTURE)
def prix_median_par_commune(
    type: Annotated[TypeBien, Field(description="Maison, Appartement ou Tous")] = "Tous",
    annee_min: Annee = None,
    annee_max: Annee = None,
    fiables_seulement: Annotated[bool, Field(description="Ne garder que les communes avec au moins 10 ventes")] = True,
    par_type: Annotated[bool, Field(description="Si type=Tous : une ligne par type (true) ou types confondus (false)")] = True,
) -> dict:
    """Prix médian au m² par commune (triées du moins cher au plus cher), avec le nombre de ventes. Sert à comparer les communes, maison vs appartement."""
    return services.prix_median(type, annee_min, annee_max, fiables_seulement, par_type)


@mcp.tool(annotations=LECTURE)
def rechercher_par_budget(
    budget: Annotated[int, Field(ge=10_000, le=2_000_000, description="Budget maximum en €")] = 250_000,
    surface_min: Annotated[int, Field(ge=9, le=400, description="Surface bâtie minimale en m²")] = 100,
    type: Annotated[Literal["Maison", "Appartement"], Field(description="Type de bien")] = "Maison",
    annee_min: Annee = None,
    annee_max: Annee = None,
    limite: Annotated[int, Field(ge=1, le=100, description="Nombre maximal de communes renvoyées")] = 20,
) -> dict:
    """Communes où des biens de la surface voulue se sont vendus pour au plus le budget, classées par nombre de ventes
    (n_offres), avec prix médian, surface médiane et part des ventes sous le budget. Répond à « où chercher avec X € ? »."""
    return services.recherche_budget(budget, surface_min, type, annee_min, annee_max, limite)


@mcp.tool(annotations=LECTURE)
def sections_d_une_commune(
    code_commune: Annotated[str, Field(description="Code INSEE de la commune, ex. 45234")],
    type: Annotated[TypeBien, Field(description="Maison, Appartement ou Tous")] = "Tous",
    annee_min: Annee = None,
    annee_max: Annee = None,
) -> dict:
    """Prix médian au m² par section cadastrale d'une commune (quartiers), du plus cher au moins cher, avec le nombre de ventes."""
    return _appel(services.sections, code_commune, type, annee_min, annee_max)


@mcp.tool(annotations=LECTURE)
def ventes_d_une_commune(
    code_commune: Annotated[str, Field(description="Code INSEE de la commune, ex. 45234")],
    section: Annotated[str | None, Field(max_length=2, description="Section cadastrale (2 caractères, ex. AB), optionnel")] = None,
    type: Annotated[TypeBien, Field(description="Maison, Appartement ou Tous")] = "Tous",
    annee_min: Annee = None,
    annee_max: Annee = None,
    limite: Annotated[int, Field(ge=1, le=100, description="Nombre maximal de ventes renvoyées (les plus récentes)")] = 20,
) -> dict:
    """Ventes individuelles (date, prix, surface, pièces, prix/m²) d'une commune ou d'une de ses sections, les plus récentes d'abord."""
    return _appel(services.ventes, code_commune, section, type, annee_min, annee_max, limite)
