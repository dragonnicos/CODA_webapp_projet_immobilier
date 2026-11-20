"""Métriques de profil : taille typique selon le nombre de pièces, dispersion des prix par commune."""
import pandas as pd

from .config import SEUIL_FIABLE
from .data import get_df
from .indice import zones_communes


def _q(p):
    def f(s):
        return s.quantile(p)
    f.__name__ = f"q{int(p * 100)}"
    return f


def taille_par_pieces(type_="Maison", zone=None, annee_min=None, annee_max=None) -> pd.DataFrame:
    """Surface typique, prix et prix/m² selon le nombre de pièces (5 = 5 et plus).

    Sert à passer d'un critère « nombre de pièces » à une surface, donc à un budget.
    """
    df = get_df()
    df = df[df["type"] == type_]
    if annee_min is not None:
        df = df[df["annee"] >= annee_min]
    if annee_max is not None:
        df = df[df["annee"] <= annee_max]
    if zone:
        df = df.merge(zones_communes()[["code_commune", "zone"]], on="code_commune")
        df = df[df["zone"] == zone]
    df = df.assign(pieces=df["nombre_pieces_principales"].clip(upper=5).astype(int))
    g = df.groupby("pieces").agg(
        n_ventes=("prix_m2", "size"),
        surface_p25=("surface_reelle_bati", _q(0.25)), surface_mediane=("surface_reelle_bati", "median"),
        surface_p75=("surface_reelle_bati", _q(0.75)),
        prix_median=("valeur_fonciere", "median"), prix_m2_median=("prix_m2", "median"),
    ).reset_index()
    g["fiable"] = g["n_ventes"] >= SEUIL_FIABLE
    return g.round(0)


def dispersion_communes(type_="Maison") -> pd.DataFrame:
    """Dispersion du prix/m² par commune : quartiles et écart interquartile relatif (plus il est grand, moins la médiane est parlante)."""
    df = get_df()
    df = df[df["type"] == type_]
    g = df.groupby(["code_commune", "nom_commune"], observed=True)["prix_m2"].agg(
        n_ventes="size", p25=_q(0.25), mediane="median", p75=_q(0.75)
    ).reset_index()
    g["iqr_relatif"] = ((g["p75"] - g["p25"]) / g["mediane"]).round(2)
    g["fiable"] = g["n_ventes"] >= SEUIL_FIABLE
    return g.round({"p25": 0, "mediane": 0, "p75": 0})
