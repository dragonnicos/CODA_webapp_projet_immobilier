"""Entraîne le modèle de prix et l'enregistre dans data/modele_prix.joblib.

À lancer en LOCAL (quelques secondes à 1 minute), puis committer le fichier : le serveur (Render) ne fait que le charger
(core/ml.py). Ce code d'entraînement n'est volontairement pas copié dans l'image Docker.
À relancer si le parquet change ou si scikit-learn est mis à jour.

    python scripts/build_model.py
"""
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor as HGB
from sklearn.model_selection import KFold

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import ml  # noqa: E402
from core.data import get_df  # noqa: E402
from core.indice import modele, zones_communes  # noqa: E402
from core.ml import ARTEFACT, FEATURES, K_TE, TYPES, _te_apply  # noqa: E402
from core.prevision import niveau_zone  # noqa: E402

PARAMS = dict(max_iter=300, learning_rate=0.06, random_state=0)


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


if __name__ == "__main__":
    t = time.time()
    chemin = sauver()
    M = ml._modeles()
    print(f"Modèle enregistré : {chemin} ({chemin.stat().st_size / 1e6:.1f} Mo) en {time.time() - t:.0f} s")
    print(f"Entraîné sur {M['n']} ventes jusqu'au {M['donnees_jusqu_au']}, scikit-learn {M['sklearn']}")
    print("Précision mesurée :", M["evaluation"])
