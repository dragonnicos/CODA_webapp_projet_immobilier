"""Estimation du prix d'un bien par apprentissage automatique (gradient boosting).

Entrées : type, surface, pièces, terrain, commune. Sortie : prix estimé et fourchette à 80 %.

Principe :
- Les prix passés sont d'abord ramenés au niveau de marché actuel avec l'indice de zone (core/indice.py), de sorte que
  le modèle apprend « combien vaut ce bien aujourd'hui » sans dériver avec la date. Il ne prédit donc pas de tendance
  (le test rétrospectif de core/prevision.py montre qu'elle n'est pas prévisible sur 2021-2025) ; l'année visée
  n'élargit que la fourchette.
- Trois modèles : médiane, quantile 10 % et quantile 90 %. La fourchette décrit la dispersion de ventes individuelles
  (état, étage, DPE… absents de DVF), élargie de l'incertitude de marché à l'horizon visé.
- La précision réelle est mesurée à l'entraînement : apprentissage sur 2021-2024, test sur les ventes de 2025.
- L'entraînement (code dans scripts/build_model.py, absent de l'image Docker) se fait en LOCAL ; ce module charge seulement
  data/modele_prix.joblib et prédit.
"""
import warnings
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .config import SEUIL_FIABLE
from .data import get_df
from .indice import zones_communes
from .prevision import _sigma_horizon, horizon_semestres

ARTEFACT = Path(__file__).resolve().parent.parent / "data" / "modele_prix.joblib"
K_TE = 8  # rétrécissement de l'encodage de commune vers la moyenne générale
FEATURES = ["t", "surface", "pieces", "terrain", "lat", "lon", "dist", "te"]
TYPES = ("Maison", "Appartement")


def _te_apply(df, stats, g):
    k = df[["code_commune", "t"]].join(stats, on=["code_commune", "t"])
    return ((k["sum"].fillna(0) + K_TE * g) / (k["count"].fillna(0) + K_TE)).to_numpy()


@lru_cache(maxsize=1)
def _modeles() -> dict:
    """Charge le modèle pré-entraîné (rapide). Aucun entraînement n'a lieu au démarrage du serveur."""
    if not ARTEFACT.exists():
        raise FileNotFoundError(f"{ARTEFACT.name} introuvable : lancer « python scripts/build_model.py » en local, puis déployer le fichier.")
    import sklearn

    M = joblib.load(ARTEFACT)
    if M["sklearn"] != sklearn.__version__:
        warnings.warn(f"Modèle entraîné avec scikit-learn {M['sklearn']}, version installée : {sklearn.__version__}.")
    return M


def evaluation() -> dict:
    """Précision mesurée hors échantillon (2021-2024 → 2025), enregistrée à l'entraînement."""
    return _modeles()["evaluation"]


def estimer_communes(type_="Maison", surface=100, pieces=None, terrain=None, annee_cible=2026, budget=None, codes=None) -> pd.DataFrame:
    """Prix estimé (médiane et fourchette à 80 %) du bien décrit, dans chaque commune.

    Valeurs non fournies (pièces, terrain) : laissées inconnues, le modèle gère l'absence. Pour une maison sans
    terrain connu, la fourchette est naturellement plus large. Avec `budget` : statut « sûr » (haut de la fourchette
    dans le budget), « possible » (estimation dans le budget) ou « hors budget ».
    """
    if type_ not in TYPES:
        raise ValueError("type_ doit être 'Maison' ou 'Appartement'.")
    M = _modeles()
    z = zones_communes()
    if codes is not None:
        z = z[z["code_commune"].isin(codes)]
    df = get_df()
    nv = df[df["type"] == type_].groupby("code_commune", observed=True).size().rename("n_ventes")
    X = pd.DataFrame({
        "code_commune": z["code_commune"].to_numpy(), "t": int(type_ == "Maison"),
        "surface": float(surface), "pieces": np.nan if pieces is None else float(pieces),
        "terrain": np.nan if terrain is None else float(terrain),
        "lat": z["latitude"].to_numpy(), "lon": z["longitude"].to_numpy(), "dist": z["distance_km"].to_numpy(),
    })
    X["te"] = _te_apply(X, M["stats"], M["g"])
    p, lo, hi = (M["m"][k].predict(X[FEATURES]) for k in ("median", "q10", "q90"))
    # incertitude de marché à l'horizon visé, ajoutée en quadrature aux demi-largeurs de la fourchette de ventes
    h = max(horizon_semestres(annee_cible, type_), 0)
    extra = 1.2816 * _sigma_horizon(type_, h)
    lo = p - np.sqrt((p - lo).clip(min=0) ** 2 + extra**2)
    hi = p + np.sqrt((hi - p).clip(min=0) ** 2 + extra**2)
    out = z[["code_commune", "nom_commune", "zone", "distance_km"]].reset_index(drop=True)
    out["n_ventes"] = out["code_commune"].map(nv).fillna(0).astype(int)
    out["annee"] = annee_cible
    out["surface"] = round(float(surface))
    out["prix_estime"] = np.exp(p).round(-2)
    out["prix_bas"] = np.exp(lo).round(-2)
    out["prix_haut"] = np.exp(hi).round(-2)
    out["prix_m2"] = (out["prix_estime"] / surface).round(0)
    out["fiable"] = out["n_ventes"] >= SEUIL_FIABLE
    if budget is not None:
        out["statut"] = np.where(out["prix_haut"] <= budget, "sûr", np.where(out["prix_estime"] <= budget, "possible", "hors budget"))
        out["marge_pct"] = ((budget - out["prix_estime"]) / budget * 100).round(0)
    return out.sort_values("distance_km").reset_index(drop=True)


def estimer(code_commune, type_="Maison", surface=100, pieces=None, terrain=None, annee_cible=2026, budget=None) -> dict:
    """Estimation du prix d'un bien dans une commune, avec fourchette à 80 %, précision mesurée et avertissements."""
    r = estimer_communes(type_, surface, pieces, terrain, annee_cible, budget, codes=[code_commune])
    if r.empty:
        raise ValueError(f"Commune inconnue : {code_commune}")
    r = r.iloc[0].to_dict()
    ev = evaluation()
    avert = [
        "La fourchette décrit la dispersion de ventes individuelles : l'état du bien, l'étage et le DPE ne sont pas dans DVF.",
        f"Précision mesurée sur les ventes de {ev['annee_test']} (jamais vues par le modèle) : erreur médiane {ev['erreur_mediane_pct']} %.",
        "Le modèle suppose un marché stable au niveau des deux dernières années ; il ne prédit pas de hausse ni de baisse.",
    ]
    if not r["fiable"]:
        avert.append(f"Moins de {SEUIL_FIABLE} ventes de ce type dans la commune : estimation peu fiable.")
    if type_ == "Maison" and terrain is None:
        avert.append("Surface de terrain non indiquée : c'est le 2e critère du prix d'une maison, l'estimation est moins précise.")
    r["avertissements"] = avert
    r["precision"] = ev
    return r
