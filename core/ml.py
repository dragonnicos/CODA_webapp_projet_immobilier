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
- L'entraînement se fait en LOCAL (scripts/build_model.py) ; le serveur charge data/modele_prix.joblib sans rien recalculer.
"""
import warnings
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor as HGB
from sklearn.model_selection import KFold

from .config import SEUIL_FIABLE
from .data import get_df
from .indice import modele, zones_communes
from .prevision import Z95, _sigma_horizon, horizon_semestres, niveau_zone

ARTEFACT = Path(__file__).resolve().parent.parent / "data" / "modele_prix.joblib"
K_TE = 8  # rétrécissement de l'encodage de commune vers la moyenne générale
FEATURES = ["t", "surface", "pieces", "terrain", "lat", "lon", "dist", "te"]
PARAMS = dict(max_iter=300, learning_rate=0.06, random_state=0)
TYPES = ("Maison", "Appartement")


def _base(df=None) -> pd.DataFrame:
    """Ventes avec variables du modèle et cible ramenée au niveau de marché actuel."""
    df = (get_df() if df is None else df).copy()
    z = zones_communes().set_index("code_commune")
    df["zone"] = df["code_commune"].map(z["zone"])
    df["dist"] = df["code_commune"].map(z["distance_km"])
    df["lat"] = df["latitude"].fillna(df["code_commune"].map(z["latitude"]))
    df["lon"] = df["longitude"].fillna(df["code_commune"].map(z["longitude"]))
    df["t"] = (df["type"] == "Maison").astype(int)
    df["surface"] = df["surface_reelle_bati"]
    df["pieces"] = df["nombre_pieces_principales"]
    df["terrain"] = df["surface_terrain"]
    df["p"] = (df["annee"] - df["annee"].min()) * 2 + (df["date_mutation"].dt.month > 6).astype(int)
    df["ajust"] = 0.0
    for ty in TYPES:
        idx = modele(ty)["indice"].set_index(["zone", "p"])["log_indice"].fillna(0)
        niv = niveau_zone(ty).set_index("zone")["log_niveau"]
        s = df["type"] == ty
        df.loc[s, "ajust"] = (
            df.loc[s, "zone"].map(niv).to_numpy()
            - pd.MultiIndex.from_frame(df.loc[s, ["zone", "p"]]).map(idx).to_numpy(dtype=float)
        )
    df["y"] = np.log(df["valeur_fonciere"]) + df["ajust"]
    df["ym2"] = df["y"] - np.log(df["surface"])
    return df


def _te_stats(df):
    return df.groupby(["code_commune", "t"])["ym2"].agg(["sum", "count"]), float(df["ym2"].mean())


def _te_apply(df, stats, g):
    k = df[["code_commune", "t"]].join(stats, on=["code_commune", "t"])
    return ((k["sum"].fillna(0) + K_TE * g) / (k["count"].fillna(0) + K_TE)).to_numpy()


def _preparer(df):
    """Ajoute l'encodage de commune : hors échantillon (5 plis) pour l'entraînement, pour éviter de recopier la cible."""
    df = df.copy()
    df["te"] = np.nan
    g = float(df["ym2"].mean())
    for a, b in KFold(5, shuffle=True, random_state=0).split(df):
        stats, _ = _te_stats(df.iloc[a])
        df.iloc[b, df.columns.get_loc("te")] = _te_apply(df.iloc[b], stats, g)
    return df


def _entrainer(df):
    return {
        "median": HGB(**PARAMS).fit(df[FEATURES], df["y"]),
        "q10": HGB(loss="quantile", quantile=0.1, **PARAMS).fit(df[FEATURES], df["y"]),
        "q90": HGB(loss="quantile", quantile=0.9, **PARAMS).fit(df[FEATURES], df["y"]),
    }


def _evaluer() -> dict:
    """Précision mesurée hors échantillon : entraînement sur les ventes jusqu'en 2024, test sur celles de 2025."""
    df = _base()
    an = int(df["annee"].max())
    tr, te = df[df["annee"] < an], df[df["annee"] == an].copy()
    tr = _preparer(tr)
    stats, g = _te_stats(tr)
    te["te"] = _te_apply(te, stats, g)
    m = _entrainer(tr)
    p, lo, hi = (m[k].predict(te[FEATURES]) for k in ("median", "q10", "q90"))
    ref = np.log(te["valeur_fonciere"]) + te["ajust"]
    err = np.abs(np.exp(p - ref) - 1)
    return {
        "annee_test": an, "n_test": int(len(te)),
        "erreur_mediane_pct": round(float(np.median(err)) * 100, 1),
        "couverture_80_pct": round(float(((ref >= lo) & (ref <= hi)).mean()) * 100, 1),
        "erreur_mediane_pct_maison": round(float(np.median(err[te["t"] == 1])) * 100, 1),
        "erreur_mediane_pct_appartement": round(float(np.median(err[te["t"] == 0])) * 100, 1),
    }


def construire() -> dict:
    """ENTRAÎNEMENT (lent, à lancer en local avec scripts/build_model.py) : modèles finaux + précision mesurée."""
    df = _preparer(_base())
    stats, g = _te_stats(df)
    return {
        "m": _entrainer(df), "stats": stats, "g": g, "n": len(df),
        "evaluation": _evaluer(), "sklearn": sklearn.__version__,
        "donnees_jusqu_au": get_df()["date_mutation"].max().date().isoformat(),
    }


def sauver(chemin=ARTEFACT) -> Path:
    joblib.dump(construire(), chemin, compress=3)
    return Path(chemin)


@lru_cache(maxsize=1)
def _modeles() -> dict:
    """Charge le modèle pré-entraîné (rapide). Aucun entraînement n'a lieu au démarrage du serveur."""
    if not ARTEFACT.exists():
        raise FileNotFoundError(f"{ARTEFACT.name} introuvable : lancer « python scripts/build_model.py » en local, puis déployer le fichier.")
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
