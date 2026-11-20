"""Opérations de haut niveau, communes à l'API (FastAPI) et au MCP : calcul + réponse {resume, donnees, ...}."""
from . import resumes
from .config import LIMITES
from .stats import (
    liste_communes,
    prix_median_communes,
    recherche_budget as _recherche_budget,
    resume_global,
    sections_commune,
    ventes_section,
)


class CommuneInconnue(ValueError):
    pass


def _verifier_commune(code: str):
    if code not in set(liste_communes()["code_commune"]):
        raise CommuneInconnue(f"Commune inconnue : {code} (code INSEE attendu, ex. 45234 pour Orléans ; voir la liste des communes).")


def resume():
    r = resume_global()
    return resumes.reponse(
        f"{r['n_ventes']} ventes DVF du Loiret ({r['n_maisons']} maisons, {r['n_appartements']} appartements) "
        f"dans {r['n_communes']} communes, du {r['date_min']} au {r['date_max']}.",
        r,
        limites=LIMITES,
    )


def communes():
    df = liste_communes()
    return resumes.reponse(f"{len(df)} communes.", resumes.enregistrements(df))


def prix_median(type="Tous", annee_min=None, annee_max=None, fiables_seulement=True, par_type=True):
    df = prix_median_communes(type, annee_min, annee_max, fiables_seulement, par_type)
    df = df.drop(columns=["latitude", "longitude"])
    return resumes.reponse(resumes.resume_prix(df, type, annee_min, annee_max), resumes.enregistrements(df))


def recherche_budget(budget=250_000, surface_min=100, type="Maison", annee_min=None, annee_max=None, limite=50):
    df = _recherche_budget(budget, surface_min, type, annee_min, annee_max)
    texte = resumes.resume_budget(df, budget, surface_min, type, annee_min, annee_max)
    df = df.drop(columns=["latitude", "longitude"]).head(limite)
    return resumes.reponse(texte, resumes.enregistrements(df))


def sections(code_commune, type="Tous", annee_min=None, annee_max=None):
    _verifier_commune(code_commune)
    df = sections_commune(code_commune, type, annee_min, annee_max).drop(columns=["latitude", "longitude"])
    return resumes.reponse(resumes.resume_sections(df, code_commune), resumes.enregistrements(df))


def ventes(code_commune, section=None, type="Tous", annee_min=None, annee_max=None, limite=100):
    _verifier_commune(code_commune)
    df = ventes_section(code_commune, section, type, annee_min, annee_max)
    texte = resumes.resume_ventes(len(df), min(len(df), limite), code_commune, section)
    df = df.drop(columns=["latitude", "longitude"]).head(limite)
    return resumes.reponse(texte, resumes.enregistrements(df))
