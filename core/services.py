"""Opérations de haut niveau, communes à l'API (FastAPI) et au MCP : calcul + réponse {resume, donnees, ...}."""
import pandas as pd

from . import indice as _indice, ml as _ml, prevision as _prev, resumes, tendance as _tend
from .config import LIMITES, SEUIL_FIABLE
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


# ---------------------------------------------------------------- tendance, prévision, estimation
class ParametreInvalide(ValueError):
    pass


class ModeleIndisponible(RuntimeError):
    pass


AVERT_MODELE = (
    "Estimation statistique, pas une évaluation : DVF ne contient ni l'état du bien, ni l'étage, ni le DPE. La fourchette décrit la "
    "dispersion de ventes individuelles. Le modèle suppose un marché stable au niveau des deux dernières années : il ne prédit "
    "ni hausse ni baisse, et l'année visée n'élargit que la fourchette."
)
ORDRE_STATUT = {"sûr": 0, "possible": 1, "hors budget": 2}


def tendance(type="Tous", annee_min=None, annee_max=None):
    df = _tend.evolution_marche(type, True, annee_min, annee_max)
    return resumes.reponse(resumes.resume_tendance(df, type, annee_min, annee_max), resumes.enregistrements(df))


def variation(type="Tous", annee_min=2021, annee_max=2025, fiables_seulement=True, tri="hausse", limite=50):
    if annee_max <= annee_min:
        raise ParametreInvalide("annee_max doit être strictement supérieure à annee_min.")
    df = _tend.variation_communes(type, annee_min, annee_max, fiables_seulement)
    fen = _tend.fenetres(annee_min, annee_max)
    texte = resumes.resume_variation(df, type, annee_min, annee_max, fen)
    if tri == "baisse":
        df = df.iloc[::-1]
    df = df.head(limite)
    return resumes.reponse(
        texte, resumes.enregistrements(df),
        methode="Médiane du prix/m² de la fenêtre de fin contre celle de la fenêtre de début ; `fiable` exige au moins "
                f"{SEUIL_FIABLE} ventes dans chacune.",
        fenetres={"debut": list(fen[0]), "fin": list(fen[1])},
    )


def evolution_commune(code_commune, type="Tous", annee_min=None, annee_max=None):
    _verifier_commune(code_commune)
    df = _tend.evolution_communes([code_commune], type, annee_min, annee_max).drop(columns=["code_commune"])
    return resumes.reponse(resumes.resume_evolution(df, code_commune), resumes.enregistrements(df))


def marche(type="Maison", annees=(2026, 2027, 2028)):
    hist = _indice.indice_marche(type).drop(columns=["p"])
    prev = pd.concat([_prev.prevision_indice(type, a) for a in annees], ignore_index=True)
    return resumes.reponse(
        resumes.resume_marche(prev, type),
        {"historique": resumes.enregistrements(hist), "prevision": resumes.enregistrements(prev)},
        zones={z: "Orléans" if z == "Orléans" else "couronne autour d'Orléans (distance), commune par commune" for z in _indice.ZONES},
        erreur_prevision_par_horizon={f"{h} semestre(s)": round(e, 3) for h, e in _prev.erreur_horizon(type).items()},
        avertissement=AVERT_MODELE,
    )


def _modele(fonction, *args, **kwargs):
    try:
        return fonction(*args, **kwargs)
    except FileNotFoundError as e:
        raise ModeleIndisponible(str(e))


def estimation(code_commune, type="Maison", surface=100, pieces=None, terrain=None, annee=2026, budget=None):
    _verifier_commune(code_commune)
    r = _modele(_ml.estimer, code_commune, type, surface, pieces, terrain, annee, budget)
    avert, precision = r.pop("avertissements"), r.pop("precision")
    donnees = resumes.enregistrements(pd.DataFrame([r]))[0]
    return resumes.reponse(
        resumes.resume_estimation(donnees, type, budget), donnees,
        avertissement=" ".join(avert), precision_modele=precision,
    )


def projet(budget, type="Maison", surface=100, pieces=None, terrain=None, annee=2026, fiables_seulement=True,
           statuts=None, limite=30):
    d = _modele(_ml.estimer_communes, type, surface, pieces, terrain, annee, budget)
    if fiables_seulement:
        d = d[d["fiable"]]
    d = d.assign(_o=d["statut"].map(ORDRE_STATUT)).sort_values(["_o", "distance_km"]).drop(columns="_o")
    texte = resumes.resume_projet(d, budget, type, surface, annee)
    par_zone = (
        d.groupby("zone")
        .agg(
            n_communes=("code_commune", "size"),
            surs=("statut", lambda s: int((s == "sûr").sum())),
            possibles=("statut", lambda s: int((s == "possible").sum())),
            prix_estime_median=("prix_estime", "median"),
        )
        .reindex(_indice.ZONES).dropna().reset_index()
    )
    par_zone[["n_communes", "surs", "possibles"]] = par_zone[["n_communes", "surs", "possibles"]].astype(int)
    if statuts:
        d = d[d["statut"].isin(statuts)]
    cols = ["code_commune", "nom_commune", "zone", "distance_km", "prix_estime", "prix_bas", "prix_haut", "prix_m2",
            "statut", "marge_pct", "n_ventes", "fiable"]
    return resumes.reponse(
        texte, resumes.enregistrements(d[cols].head(limite)),
        par_zone=resumes.enregistrements(par_zone),
        precision_modele=_modele(_ml.evaluation),
        legende_statut={
            "sûr": "même le haut de la fourchette à 80 % tient dans le budget",
            "possible": "l'estimation tient dans le budget, pas forcément le haut de la fourchette",
            "hors budget": "l'estimation dépasse le budget",
        },
        avertissement=AVERT_MODELE,
    )
