"""Prévision de prix et simulateur de projet d'achat.

Choix de méthode (validé par un test rétrospectif, voir `erreur_horizon`) : sur 2021-2025, extrapoler une
tendance se trompe plus que supposer le niveau récent stable. Le prix attendu est donc le NIVEAU des deux
dernières années (4 semestres) de l'indice de la zone ; ce que l'horizon change, c'est la largeur de la fourchette.
Conséquence : l'année d'achat n'a pas d'effet sur le prix central, seulement sur l'incertitude.
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from .config import SEUIL_FIABLE
from .indice import ZONES, K_SHRINK, modele, zones_communes
from .profil import taille_par_pieces

FENETRE = 4  # semestres moyennés pour le niveau actuel
H_TESTE_MAX = 4  # horizon (semestres) validé par le test rétrospectif
Z95 = 1.96


@lru_cache(maxsize=2)
def erreur_horizon(type_: str) -> dict:
    """Erreur quadratique moyenne (en log) de la prévision « niveau des 4 derniers semestres », par horizon 1..4 semestres.

    Test rétrospectif à origine glissante sur l'indice de chaque zone : on prédit chaque semestre à venir
    avec les seuls semestres qui précèdent. Ce n'est pas un test hors échantillon strict (l'indice est estimé sur
    toute la période) et il repose sur peu de points : à lire comme un ordre de grandeur.
    """
    idx = modele(type_)["indice"]
    err = {h: [] for h in range(1, H_TESTE_MAX + 1)}
    for _, g in idx.groupby("zone"):
        y = g.sort_values("p")["log_indice"].to_numpy()
        for n0 in range(FENETRE, len(y)):
            niveau = y[n0 - FENETRE:n0].mean()
            for h in err:
                if n0 + h - 1 < len(y):
                    err[h].append(y[n0 + h - 1] - niveau)
    return {h: float(np.sqrt(np.mean(np.square(e)))) for h, e in err.items() if e}


def _sigma_horizon(type_, h):
    """Écart-type (log) de l'erreur de prévision à h semestres ; au-delà de l'horizon testé, croissance en racine de h (hypothèse)."""
    e = erreur_horizon(type_)
    if h <= H_TESTE_MAX:
        return float(np.interp(h, list(e), list(e.values())))
    return e[H_TESTE_MAX] * np.sqrt(h / H_TESTE_MAX)


def horizon_semestres(annee_cible, type_="Maison") -> float:
    """Nombre de semestres entre la dernière donnée et le milieu de l'année visée."""
    m = modele(type_)
    p_last = int(m["indice"]["p"].max())
    return 2 * (annee_cible - m["annee0"]) + 0.5 - p_last


def niveau_zone(type_="Maison") -> pd.DataFrame:
    """Niveau actuel de l'indice par zone (moyenne des 4 derniers semestres), en log, avec son incertitude."""
    idx = modele(type_)["indice"]
    out = []
    for zone in ZONES:
        g = idx[idx["zone"] == zone].sort_values("p").tail(FENETRE)
        out.append({
            "zone": zone, "log_niveau": float(g["log_indice"].mean()),
            "se_niveau": float(np.sqrt((g["se"] ** 2).sum()) / len(g)),
            "n_ventes": int(g["n_ventes"].sum()),
        })
    return pd.DataFrame(out)


def _confiance(h, sig_total):
    """faible / moyenne / élevée selon l'horizon et la largeur de la fourchette."""
    if h > H_TESTE_MAX or sig_total > 0.12:
        return "faible"
    return "élevée" if sig_total < 0.06 and h <= 2 else "moyenne"


def prevision_indice(type_="Maison", annee_cible=2026) -> pd.DataFrame:
    """Indice de prix attendu (base 100 = 1er semestre 2021) par zone pour l'année visée, avec fourchette à 95 %."""
    h = max(horizon_semestres(annee_cible, type_), 0)
    n = niveau_zone(type_)
    sig = np.sqrt(n["se_niveau"] ** 2 + _sigma_horizon(type_, h) ** 2)
    n["annee"] = annee_cible
    n["indice"] = (100 * np.exp(n["log_niveau"])).round(1)
    n["bas"] = (100 * np.exp(n["log_niveau"] - Z95 * sig)).round(1)
    n["haut"] = (100 * np.exp(n["log_niveau"] + Z95 * sig)).round(1)
    n["incertitude_pct"] = (100 * (np.exp(Z95 * sig) - 1)).round(0)
    n["confiance"] = [_confiance(h, s) for s in sig]
    return n.drop(columns=["log_niveau", "se_niveau"])


def projet(budget, type_="Maison", surface=None, pieces=None, annee_cible=2026, zones=None, fiables_seulement=True) -> pd.DataFrame:
    """Simulateur : pour chaque commune, le bien voulu entre-t-il dans le budget à l'année visée ?

    surface : m² voulus ; à défaut déduits du nombre de pièces (surface médiane des ventes à ce nombre de pièces).
    Tri : « sûr » d'abord, puis « possible », puis « hors budget », et dans chaque groupe les communes les plus proches d'Orléans.
    Colonnes : prix attendu et fourchette (incertitude de niveau, pas celle d'une vente isolée), surface achetable
    avec le budget, `statut` = « sûr » (même le haut de la fourchette passe), « possible » (le bas passe) ou « hors budget ».
    `ecart_ventes_pct` : dispersion des ventes individuelles autour du prix attendu (la moitié des ventes est à ± cette valeur).
    """
    if surface is None:
        if pieces is None:
            raise ValueError("Donner une surface ou un nombre de pièces.")
        t = taille_par_pieces(type_)
        t = t[t["pieces"] == min(int(pieces), 5)]
        if t.empty:
            raise ValueError("Pas de ventes pour ce nombre de pièces.")
        surface = float(t["surface_mediane"].iloc[0])
    m = modele(type_)
    h = max(horizon_semestres(annee_cible, type_), 0)
    sig_h = _sigma_horizon(type_, h)
    niv = niveau_zone(type_).set_index("zone")
    c = m["communes"].merge(zones_communes()[["code_commune", "distance_km"]], on="code_commune")
    if zones:
        c = c[c["zone"].isin(zones)]
    c = c.assign(log_niveau=c["zone"].map(niv["log_niveau"]), se_zone=c["zone"].map(niv["se_niveau"]))
    b = m["beta_surface"]
    a = c["effet_lisse"] + c["log_niveau"]  # log(prix/m²) d'un bien de 1 m², au niveau actuel
    se_com = m["sigma"] / np.sqrt(c["n_ventes"] + K_SHRINK)  # incertitude sur le niveau de la commune (rétrécie)
    sig = np.sqrt(sig_h**2 + c["se_zone"] ** 2 + se_com**2)
    c["surface"] = round(surface)
    c["prix_m2"] = np.exp(a + b * np.log(surface)).round(0)
    c["prix_attendu"] = (c["prix_m2"] * surface).round(-2)
    c["prix_bas"] = (c["prix_attendu"] * np.exp(-Z95 * sig)).round(-2)
    c["prix_haut"] = (c["prix_attendu"] * np.exp(Z95 * sig)).round(-2)
    c["surface_achetable"] = np.floor((budget / np.exp(a)) ** (1 / (1 + b)))
    c["marge_pct"] = ((budget - c["prix_attendu"]) / budget * 100).round(0)
    c["statut"] = np.where(c["prix_haut"] <= budget, "sûr", np.where(c["prix_bas"] <= budget, "possible", "hors budget"))
    c["ecart_ventes_pct"] = (100 * (np.exp(0.674 * m["sigma"]) - 1)).round(0)
    c["fiable"] = c["n_ventes"] >= SEUIL_FIABLE
    c["annee"] = annee_cible
    if fiables_seulement:
        c = c[c["fiable"]]
    ordre = {"sûr": 0, "possible": 1, "hors budget": 2}
    c = c.assign(_o=c["statut"].map(ordre)).sort_values(["_o", "distance_km"]).drop(columns="_o")
    cols = ["code_commune", "nom_commune", "zone", "distance_km", "n_ventes", "annee", "surface", "prix_m2", "prix_attendu",
            "prix_bas", "prix_haut", "surface_achetable", "marge_pct", "statut", "ecart_ventes_pct", "fiable"]
    return c[cols].reset_index(drop=True)


def comparer_annees(budget, type_="Maison", surface=None, pieces=None, annees=(2026, 2027, 2028), zones=None) -> pd.DataFrame:
    """Compare les années d'achat pour un même projet : nombre de communes sûres / possibles et prix médian attendu."""
    out = []
    for an in annees:
        p = projet(budget, type_, surface, pieces, an, zones)
        h = max(horizon_semestres(an, type_), 0)
        out.append({
            "annee": an, "n_communes": len(p),
            "n_sures": int((p["statut"] == "sûr").sum()), "n_possibles": int((p["statut"] == "possible").sum()),
            "prix_attendu_median": float(p["prix_attendu"].median()),
            "confiance": _confiance(h, _sigma_horizon(type_, h)),
        })
    return pd.DataFrame(out)


def projet_par_zone(budget, type_="Maison", surface=None, pieces=None, annee_cible=2026) -> pd.DataFrame:
    """Synthèse du projet par zone : combien de communes passent, prix et surface achetable médians."""
    p = projet(budget, type_, surface, pieces, annee_cible)
    g = p.groupby("zone").agg(
        n_communes=("code_commune", "size"),
        n_sures=("statut", lambda s: int((s == "sûr").sum())),
        n_possibles=("statut", lambda s: int((s == "possible").sum())),
        prix_attendu_median=("prix_attendu", "median"),
        surface_achetable_mediane=("surface_achetable", "median"),
        ventes=("n_ventes", "sum"),
    ).reset_index()
    g["zone"] = pd.Categorical(g["zone"], ZONES, ordered=True)
    return g.sort_values("zone").reset_index(drop=True)
