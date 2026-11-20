import pandas as pd

from .config import SEUIL_FIABLE
from .data import get_df


def _filtrer(df, type_=None, annee_min=None, annee_max=None):
    if type_ and type_ != "Tous":
        df = df[df["type"] == type_]
    if annee_min is not None:
        df = df[df["annee"] >= annee_min]
    if annee_max is not None:
        df = df[df["annee"] <= annee_max]
    return df


def _centres(df):
    """Position médiane des ventes géolocalisées de chaque commune."""
    return df.groupby("code_commune")[["latitude", "longitude"]].median()


def liste_communes() -> pd.DataFrame:
    df = get_df()
    out = df.groupby(["code_commune", "nom_commune"], observed=True).size().rename("n_ventes").reset_index()
    return out.sort_values("nom_commune").reset_index(drop=True)


def resume_global() -> dict:
    df = get_df()
    return {
        "n_ventes": int(len(df)),
        "n_communes": int(df["code_commune"].nunique()),
        "n_maisons": int((df["type"] == "Maison").sum()),
        "n_appartements": int((df["type"] == "Appartement").sum()),
        "date_min": df["date_mutation"].min().date().isoformat(),
        "date_max": df["date_mutation"].max().date().isoformat(),
        "seuil_fiable": SEUIL_FIABLE,
    }


def prix_median_communes(type_="Tous", annee_min=None, annee_max=None, fiables_seulement=True, par_type=True) -> pd.DataFrame:
    """Q1 : médiane du prix/m² et nombre de ventes par commune.

    type_='Tous' : une ligne par commune et par type si par_type, sinon une ligne par commune (types confondus).
    """
    df = _filtrer(get_df(), type_, annee_min, annee_max)
    centres = _centres(get_df())
    if type_ == "Tous" and not par_type:
        df = df.assign(type="Tous")
    g = (
        df.groupby(["code_commune", "nom_commune", "type"], observed=True)
        .agg(n_ventes=("prix_m2", "size"), prix_m2_median=("prix_m2", "median"))
        .reset_index()
    )
    g = g[g["n_ventes"] > 0]
    g["fiable"] = g["n_ventes"] >= SEUIL_FIABLE
    g = g.join(centres, on="code_commune")
    if fiables_seulement:
        g = g[g["fiable"]]
    g["prix_m2_median"] = g["prix_m2_median"].round(0)
    return g.sort_values("prix_m2_median").reset_index(drop=True)


def recherche_budget(budget=250_000, surface_min=100, type_="Maison", annee_min=None, annee_max=None) -> pd.DataFrame:
    """Q2 : communes où l'on a vendu un bien du type voulu, d'au moins surface_min m², pour au plus `budget`."""
    df = _filtrer(get_df(), type_, annee_min, annee_max)
    df = df[df["surface_reelle_bati"] >= surface_min]
    total = df.groupby("code_commune", observed=True).size().rename("n_ventes_surface")
    ok = df[df["valeur_fonciere"] <= budget]
    g = (
        ok.groupby(["code_commune", "nom_commune"], observed=True)
        .agg(
            n_offres=("valeur_fonciere", "size"),
            prix_median=("valeur_fonciere", "median"),
            surface_mediane=("surface_reelle_bati", "median"),
            prix_m2_median=("prix_m2", "median"),
        )
        .reset_index()
        .join(total, on="code_commune")
        .join(_centres(get_df()), on="code_commune")
    )
    g["part_sous_budget"] = (g["n_offres"] / g["n_ventes_surface"]).round(2)
    g["fiable"] = g["n_offres"] >= SEUIL_FIABLE
    for c in ("prix_median", "surface_mediane", "prix_m2_median"):
        g[c] = g[c].round(0)
    return g.sort_values("n_offres", ascending=False).reset_index(drop=True)


def sections_commune(code_commune, type_="Tous", annee_min=None, annee_max=None) -> pd.DataFrame:
    df = _filtrer(get_df(), type_, annee_min, annee_max)
    df = df[df["code_commune"] == code_commune]
    g = (
        df.groupby("section", observed=True)
        .agg(
            n_ventes=("prix_m2", "size"),
            prix_m2_median=("prix_m2", "median"),
            prix_median=("valeur_fonciere", "median"),
            latitude=("latitude", "median"),
            longitude=("longitude", "median"),
        )
        .reset_index()
    )
    g["fiable"] = g["n_ventes"] >= SEUIL_FIABLE
    g["prix_m2_median"] = g["prix_m2_median"].round(0)
    g["prix_median"] = g["prix_median"].round(0)
    return g.sort_values("prix_m2_median", ascending=False).reset_index(drop=True)


def ventes_section(code_commune, section=None, type_="Tous", annee_min=None, annee_max=None) -> pd.DataFrame:
    df = _filtrer(get_df(), type_, annee_min, annee_max)
    df = df[df["code_commune"] == code_commune]
    if section:
        df = df[df["section"] == section]
    cols = ["date_mutation", "type", "valeur_fonciere", "surface_reelle_bati", "nombre_pieces_principales",
            "prix_m2", "surface_terrain", "section", "latitude", "longitude"]
    out = df[cols].sort_values("date_mutation", ascending=False).copy()
    out["type"] = out["type"].astype(str)
    out["prix_m2"] = out["prix_m2"].round(0)
    return out.reset_index(drop=True)
