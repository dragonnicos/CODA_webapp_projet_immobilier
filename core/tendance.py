"""Évolution du marché dans le temps : séries de médianes, variations. Aucune dépendance à Dash."""
import pandas as pd

from .config import SEUIL_FIABLE
from .data import get_df
from .stats import _filtrer


def evolution_marche(type_="Tous", par_type=True, annee_min=None, annee_max=None, code_communes=None) -> pd.DataFrame:
    """Prix médian €/m² et nombre de ventes par trimestre (tout le Loiret, ou les communes données).

    Une ligne par trimestre et par type si par_type, sinon une seule série (types confondus).
    """
    df = _filtrer(get_df(), type_, annee_min, annee_max)
    if code_communes:
        df = df[df["code_commune"].isin(code_communes)]
    df = df.assign(
        trimestre=df["date_mutation"].dt.to_period("Q").dt.start_time,
        type=df["type"].astype(str) if par_type else "Tous",
    )
    g = (
        df.groupby(["trimestre", "type"])
        .agg(n_ventes=("prix_m2", "size"), prix_m2_median=("prix_m2", "median"))
        .reset_index()
    )
    g["fiable"] = g["n_ventes"] >= SEUIL_FIABLE
    g["prix_m2_median"] = g["prix_m2_median"].round(0)
    return g


def evolution_communes(code_communes, type_="Tous", annee_min=None, annee_max=None) -> pd.DataFrame:
    """Prix médian €/m² par année et par commune (annuel : un trimestre de commune compte trop peu de ventes)."""
    df = _filtrer(get_df(), type_, annee_min, annee_max)
    df = df[df["code_commune"].isin(code_communes)]
    g = (
        df.groupby(["code_commune", "nom_commune", "annee"], observed=True)
        .agg(n_ventes=("prix_m2", "size"), prix_m2_median=("prix_m2", "median"))
        .reset_index()
    )
    g["fiable"] = g["n_ventes"] >= SEUIL_FIABLE
    g["prix_m2_median"] = g["prix_m2_median"].round(0)
    return g


def fenetres(annee_min, annee_max):
    """Fenêtres de début et de fin comparées : 2 ans de chaque côté si la période le permet, sinon 1 an."""
    w = 2 if annee_max - annee_min >= 3 else 1
    return (annee_min, annee_min + w - 1), (annee_max - w + 1, annee_max)


def variation_communes(type_="Tous", annee_min=2021, annee_max=2025, fiables_seulement=True) -> pd.DataFrame:
    """Variation (%) du prix médian au m² entre le début et la fin de la période, par commune.

    Compare la médiane de la fenêtre de début à celle de la fenêtre de fin ; `fiable` exige au moins
    SEUIL_FIABLE ventes dans chacune des deux.
    """
    if annee_max <= annee_min:
        return pd.DataFrame(columns=["code_commune", "nom_commune", "prix_debut", "prix_fin", "n_debut", "n_fin", "variation_pct", "fiable"])
    (d0, d1), (f0, f1) = fenetres(annee_min, annee_max)
    df = _filtrer(get_df(), type_)

    def med(a, b, suffixe):
        x = df[(df["annee"] >= a) & (df["annee"] <= b)]
        g = x.groupby(["code_commune", "nom_commune"], observed=True).agg(
            **{f"n_{suffixe}": ("prix_m2", "size"), f"prix_{suffixe}": ("prix_m2", "median")}
        )
        return g

    g = med(d0, d1, "debut").join(med(f0, f1, "fin"), how="inner").reset_index()
    g["variation_pct"] = ((g["prix_fin"] / g["prix_debut"] - 1) * 100).round(1)
    g["fiable"] = (g["n_debut"] >= SEUIL_FIABLE) & (g["n_fin"] >= SEUIL_FIABLE)
    g["prix_debut"] = g["prix_debut"].round(0)
    g["prix_fin"] = g["prix_fin"].round(0)
    if fiables_seulement:
        g = g[g["fiable"]]
    g.attrs["fenetres"] = ((d0, d1), (f0, f1))
    return g.sort_values("variation_pct", ascending=False).reset_index(drop=True)
