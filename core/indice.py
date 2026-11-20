"""Indice de prix à qualité constante et niveau de prix par commune.

Modèle hédonique par type de bien (maison / appartement), estimé sur toutes les ventes :

    log(prix_m2) = effet_commune + b * log(surface) + effet_zone_semestre + erreur

- effet_commune : niveau de prix propre à la commune (estimé par transformation « within »).
- b * log(surface) : les petites surfaces coûtent plus cher au m².
- effet_zone_semestre : évolution du marché de la zone (couronne autour d'Orléans), base = 1er semestre 2021.

L'indice est donc une évolution « toutes choses égales par ailleurs » : il ne bouge pas parce que la
composition des ventes (surface, commune) change d'un semestre à l'autre, contrairement à une médiane brute.
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from .config import SEUIL_FIABLE
from .data import get_df

ORLEANS = (47.9029, 1.9093)  # (latitude, longitude)
CODE_ORLEANS = "45234"
ZONES = ["Orléans", "Première couronne", "Périurbain", "Rural"]
LIMITES_KM = {"Première couronne": 12, "Périurbain": 30}  # au-delà : Rural
K_SHRINK = 8  # une commune à n ventes pèse n / (n + K) face à la moyenne de sa zone


def _km(lat, lon):
    """Distance à Orléans (haversine, km)."""
    p1, p2 = np.radians(lat), np.radians(ORLEANS[0])
    dphi, dl = p2 - p1, np.radians(ORLEANS[1] - lon)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def _zone(code, km):
    if code == CODE_ORLEANS:
        return "Orléans"
    if pd.isna(km) or km > LIMITES_KM["Périurbain"]:
        return "Rural"
    return "Première couronne" if km <= LIMITES_KM["Première couronne"] else "Périurbain"


@lru_cache(maxsize=1)
def zones_communes() -> pd.DataFrame:
    """Zone (couronne autour d'Orléans) de chaque commune, d'après la position médiane de ses ventes."""
    df = get_df()
    c = df.groupby(["code_commune", "nom_commune"], observed=True).agg(
        latitude=("latitude", "median"), longitude=("longitude", "median")
    ).reset_index()
    c["distance_km"] = _km(c["latitude"], c["longitude"]).round(1)
    c["zone"] = [_zone(a, b) for a, b in zip(c["code_commune"], c["distance_km"])]
    return c


def _semestre(df):
    return (df["annee"] - df["annee"].min()) * 2 + (df["date_mutation"].dt.month > 6).astype(int)


def _date_semestre(p, annee0):
    return pd.Timestamp(year=annee0 + p // 2, month=1 if p % 2 == 0 else 7, day=1)


@lru_cache(maxsize=2)
def modele(type_: str) -> dict:
    """Estime le modèle pour 'Maison' ou 'Appartement' (résultat mis en cache)."""
    df = get_df()
    df = df[df["type"] == type_].merge(zones_communes()[["code_commune", "zone"]], on="code_commune")
    df = df.assign(p=_semestre(df), y=np.log(df["prix_m2"]), ls=np.log(df["surface_reelle_bati"]))
    annee0 = int(get_df()["annee"].min())

    cle = df["zone"] + "|" + df["p"].astype(str)
    D = pd.get_dummies(cle.where(df["p"] > 0)).astype(float)
    D = D.loc[:, D.sum() > 0]
    X = pd.concat([df[["ls"]], D], axis=1)

    g = df["code_commune"]
    Xm, ym = X.groupby(g, observed=True).transform("mean"), df["y"].groupby(g, observed=True).transform("mean")
    Xw, yw = (X - Xm).to_numpy(), (df["y"] - ym).to_numpy()
    coef, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    rss = float(((yw - Xw @ coef) ** 2).sum())
    n_com = g.nunique()
    dof = len(df) - X.shape[1] - n_com
    sigma2 = rss / dof
    se = np.sqrt(np.diag(np.linalg.pinv(Xw.T @ Xw)) * sigma2)
    coef, se = pd.Series(coef, X.columns), pd.Series(se, X.columns)

    # effets commune : moyenne du résidu hors commune, puis rétrécissement vers la moyenne de la zone
    a = (df["y"].groupby(g, observed=True).mean() - (X.groupby(g, observed=True).mean() * coef).sum(axis=1)).rename("effet")
    n = g.value_counts().rename("n_ventes")
    com = zones_communes().set_index("code_commune")[["nom_commune", "zone"]].join(a, how="inner").join(n)
    moy_zone = com.groupby("zone").apply(lambda x: np.average(x["effet"], weights=x["n_ventes"]), include_groups=False)
    w = com["n_ventes"] / (com["n_ventes"] + K_SHRINK)
    com["effet_lisse"] = w * com["effet"] + (1 - w) * com["zone"].map(moy_zone)

    # indice par zone et semestre (base 100 au 1er semestre)
    lignes = []
    n_cell = df.groupby(["zone", "p"]).size()
    for zone in ZONES:
        for p in range(int(df["p"].max()) + 1):
            k = f"{zone}|{p}"
            c, s = (0.0, 0.0) if p == 0 else (coef.get(k, np.nan), se.get(k, np.nan))
            lignes.append({
                "zone": zone, "semestre": _date_semestre(p, annee0), "p": p,
                "log_indice": c, "se": s, "n_ventes": int(n_cell.get((zone, p), 0)),
            })
    idx = pd.DataFrame(lignes)
    idx["fiable"] = idx["n_ventes"] >= SEUIL_FIABLE
    return {
        "type": type_, "annee0": annee0, "beta_surface": float(coef["ls"]), "sigma": float(np.sqrt(sigma2)),
        "communes": com.reset_index(), "indice": idx, "n_ventes": int(len(df)),
    }


def indice_marche(type_="Maison") -> pd.DataFrame:
    """Indice de prix (base 100 = 1er semestre 2021) par zone et par semestre, avec intervalle à 95 %."""
    idx = modele(type_)["indice"].copy()
    for col, f in (("indice", 0.0), ("bas", -1.96), ("haut", 1.96)):
        idx[col] = (100 * np.exp(idx["log_indice"] + f * idx["se"])).round(1)
    return idx.drop(columns=["log_indice"])


def niveau_communes(type_="Maison", surface=100) -> pd.DataFrame:
    """Prix/m² attendu pour un bien de `surface` m², par commune, au niveau du 1er semestre 2021 (base de l'indice).

    Pour obtenir un niveau actuel, multiplier par l'indice courant de la zone / 100.
    """
    m = modele(type_)
    c = m["communes"].copy()
    c["prix_m2_base"] = np.exp(c["effet_lisse"] + m["beta_surface"] * np.log(surface)).round(0)
    c["fiable"] = c["n_ventes"] >= SEUIL_FIABLE
    return c.drop(columns=["effet", "effet_lisse"])
