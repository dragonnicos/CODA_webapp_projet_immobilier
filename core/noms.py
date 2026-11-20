"""Noms lisibles des sections cadastrales : quartier (IRIS) et rues principales.

Table générée par scripts/build_noms_sections.py -> data/sections_noms.parquet.
Absente ou incomplète : les fonctions retombent sur le code brut de la section, sans erreur.
"""
from functools import lru_cache
from pathlib import Path

import pandas as pd

PARQUET = Path(__file__).resolve().parent.parent / "data" / "sections_noms.parquet"
COLONNES = ["quartier", "rues_principales", "libelle"]


@lru_cache(maxsize=1)
def noms_sections() -> pd.DataFrame:
    """Une ligne par (code_commune, section) ; vide si le fichier n'a pas été généré."""
    if not PARQUET.exists():
        return pd.DataFrame(columns=["code_commune", "section", *COLONNES])
    return pd.read_parquet(PARQUET)


def ajouter_noms(df: pd.DataFrame, code_commune: str) -> pd.DataFrame:
    """Ajoute quartier, rues_principales et libelle à un tableau ayant une colonne `section`."""
    n = noms_sections()
    n = n[n["code_commune"] == code_commune].set_index("section")[COLONNES]
    out = df.join(n, on="section")
    for c in COLONNES:
        out[c] = out[c].fillna("")
    out["libelle"] = out["libelle"].where(out["libelle"] != "", "Section " + out["section"])
    return out
