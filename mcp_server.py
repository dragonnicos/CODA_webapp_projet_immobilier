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
        "afin d'obtenir son code INSEE (Orléans = 45234). "
        "Pour un projet d'achat (budget, surface, pièces, terrain, année), utilise `projet_d_achat` (où acheter) ou `estimer_un_bien` "
        "(prix dans une commune) : ce sont des ESTIMATIONS d'un modèle statistique, avec une fourchette à 80 %, une erreur médiane "
        "d'environ 17 % sur le prix d'une vente (précision_modele), et le modèle suppose un marché stable : il ne prédit ni hausse ni "
        "baisse (`marche_et_prevision` explique pourquoi). Ne présente jamais un prix estimé sans sa fourchette, et rappelle que "
        "l'état du bien, l'étage et le DPE ne sont pas connus. Le niveau « sûr / possible / hors budget » est défini dans `legende_statut`."
    ),
)

LECTURE = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False}
Annee = Annotated[int | None, Field(ge=2021, le=2025, description="Année (2021-2025), optionnel")]
TypeBien = Literal["Tous", "Maison", "Appartement"]


def _appel(fonction, *args, **kwargs):
    try:
        return fonction(*args, **kwargs)
    except (services.CommuneInconnue, services.ParametreInvalide, services.ModeleIndisponible) as e:
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


# ---------------------------------------------------------------- tendance, prévision, estimation
Surface = Annotated[float, Field(ge=9, le=400, description="Surface habitable en m²")]
Pieces = Annotated[int | None, Field(ge=1, le=10, description="Nombre de pièces (optionnel)")]
Terrain = Annotated[float | None, Field(ge=0, le=100_000, description="Surface de terrain en m² (optionnel ; 2e critère du prix d'une maison)")]
AnneeAchat = Annotated[int, Field(ge=2026, le=2030, description="Année d'achat visée (2026-2030) ; elle n'élargit que la fourchette")]
BienType = Literal["Maison", "Appartement"]


@mcp.tool(annotations=LECTURE)
def tendance_du_marche(
    type: Annotated[TypeBien, Field(description="Maison, Appartement ou Tous")] = "Tous",
    annee_min: Annee = None,
    annee_max: Annee = None,
) -> dict:
    """Évolution du prix médian au m² par trimestre dans le Loiret (maison et appartement), avec le nombre de ventes. Répond à « les prix montent-ils ? »."""
    return services.tendance(type, annee_min, annee_max)


@mcp.tool(annotations=LECTURE)
def variation_par_commune(
    type: Annotated[TypeBien, Field(description="Maison, Appartement ou Tous")] = "Tous",
    annee_min: Annotated[int, Field(ge=2021, le=2025, description="Début de la période")] = 2021,
    annee_max: Annotated[int, Field(ge=2021, le=2025, description="Fin de la période (> annee_min)")] = 2025,
    fiables_seulement: Annotated[bool, Field(description="Ne garder que les communes avec assez de ventes au début ET à la fin")] = True,
    tri: Annotated[Literal["hausse", "baisse"], Field(description="hausse : plus fortes hausses d'abord ; baisse : plus fortes baisses d'abord")] = "hausse",
    limite: Annotated[int, Field(ge=1, le=100)] = 20,
) -> dict:
    """Variation (%) du prix médian au m² entre le début et la fin de la période, par commune. Compare des fenêtres de 2 ans si la période dépasse 3 ans."""
    return _appel(services.variation, type, annee_min, annee_max, fiables_seulement, tri, limite)


@mcp.tool(annotations=LECTURE)
def evolution_d_une_commune(
    code_commune: Annotated[str, Field(description="Code INSEE de la commune, ex. 45234")],
    type: Annotated[TypeBien, Field(description="Maison, Appartement ou Tous")] = "Tous",
    annee_min: Annee = None,
    annee_max: Annee = None,
) -> dict:
    """Prix médian au m² par année pour une commune, avec le nombre de ventes (une année à moins de 10 ventes est peu fiable)."""
    return _appel(services.evolution_commune, code_commune, type, annee_min, annee_max)


@mcp.tool(annotations=LECTURE)
def marche_et_prevision(type: Annotated[BienType, Field(description="Maison ou Appartement")] = "Maison") -> dict:
    """Indice de prix à qualité constante par zone (Orléans, première couronne, périurbain, rural) depuis 2021, et prévision 2026-2028 avec fourchette à 95 %.
    La prévision est le niveau actuel : une tendance extrapolée se trompe plus qu'un marché supposé stable (test rétrospectif)."""
    return _appel(services.marche, type)


@mcp.tool(annotations=LECTURE)
def estimer_un_bien(
    code_commune: Annotated[str, Field(description="Code INSEE de la commune, ex. 45234")],
    type: Annotated[BienType, Field(description="Maison ou Appartement")] = "Maison",
    surface: Surface = 100,
    pieces: Pieces = None,
    terrain: Terrain = None,
    annee: AnneeAchat = 2026,
    budget: Annotated[int | None, Field(ge=10_000, le=2_000_000, description="Budget en € (optionnel) : ajoute le statut sûr/possible/hors budget")] = None,
) -> dict:
    """Estime le prix d'un bien (type, surface, pièces, terrain) dans une commune : prix estimé et fourchette à 80 %, avec la précision mesurée du modèle."""
    return _appel(services.estimation, code_commune, type, surface, pieces, terrain, annee, budget)


@mcp.tool(annotations=LECTURE)
def projet_d_achat(
    budget: Annotated[int, Field(ge=10_000, le=2_000_000, description="Budget maximum en €")] = 250_000,
    type: Annotated[BienType, Field(description="Maison ou Appartement")] = "Maison",
    surface: Surface = 100,
    pieces: Pieces = None,
    terrain: Terrain = None,
    annee: AnneeAchat = 2026,
    fiables_seulement: Annotated[bool, Field(description="Ne garder que les communes avec au moins 10 ventes de ce type")] = True,
    statuts: Annotated[list[Literal["sûr", "possible", "hors budget"]] | None, Field(description="Filtrer sur ces statuts (optionnel)")] = None,
    limite: Annotated[int, Field(ge=1, le=100)] = 20,
) -> dict:
    """Où acheter ? Pour un projet (budget, type, surface, pièces, terrain, année), estime le prix du bien dans chaque commune et classe : sûr, possible, hors budget
    (les plus proches d'Orléans d'abord), avec une synthèse par zone (`par_zone`)."""
    return _appel(services.projet, budget, type, surface, pieces, terrain, annee, fiables_seulement, statuts, limite)
