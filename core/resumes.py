"""Mise en forme pour l'API et le MCP : lignes JSON + court résumé texte (une IA lit mal un graphique)."""
import pandas as pd

from .config import FILTRES_SOURCE, SEUIL_FIABLE, SOURCE


def enregistrements(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> liste de dicts JSON-compatibles (NaN -> None, dates -> ISO)."""
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
    out = out.astype(object).where(out.notna(), None)
    return out.to_dict("records")


def _euro(x) -> str:
    return f"{x:,.0f}".replace(",", " ") + " €"


def _periode(annee_min, annee_max) -> str:
    if annee_min is None and annee_max is None:
        return "sur 2021-2025"
    a, b = annee_min or 2021, annee_max or 2025
    return f"en {a}" if a == b else f"sur {a}-{b}"


def reponse(resume: str, donnees, **extra) -> dict:
    return {
        "resume": resume,
        "donnees": donnees,
        **extra,
        "source": SOURCE,
        "filtres_source": FILTRES_SOURCE,
        "avertissement": (
            f"Médianes sur les ventes DVF ; fiable à partir de {SEUIL_FIABLE} ventes (champ `fiable`). "
            "DVF ne dit rien de l'état, de l'étage ni du DPE."
        ),
    }


def resume_prix(df: pd.DataFrame, type_, annee_min, annee_max) -> str:
    if df.empty:
        return "Aucune commune pour cette sélection."
    base = f"{len(df)} lignes commune/type ({type_}), {_periode(annee_min, annee_max)}."
    bas, haut = df.iloc[0], df.iloc[-1]
    return (
        f"{base} Le moins cher : {bas['nom_commune']} ({bas['type']}), {_euro(bas['prix_m2_median'])}/m² "
        f"sur {bas['n_ventes']} ventes. Le plus cher : {haut['nom_commune']} ({haut['type']}), "
        f"{_euro(haut['prix_m2_median'])}/m² sur {haut['n_ventes']} ventes."
    )


def resume_budget(df: pd.DataFrame, budget, surface_min, type_, annee_min, annee_max) -> str:
    cible = f"{type_.lower()} d'au moins {surface_min:.0f} m² à {_euro(budget)} maximum"
    if df.empty:
        return f"Aucune commune avec un(e) {cible} {_periode(annee_min, annee_max)}."
    top = df.head(5)
    liste = ", ".join(f"{r.nom_commune} ({r.n_offres} ventes, médiane {_euro(r.prix_median)})" for r in top.itertuples())
    return (
        f"{len(df)} communes ont vendu un(e) {cible} {_periode(annee_min, annee_max)}. "
        f"Les plus fournies : {liste}."
    )


def resume_sections(df: pd.DataFrame, code_commune) -> str:
    if df.empty:
        return f"Aucune vente pour la commune {code_commune}."
    fiables = df[df["fiable"]]
    txt = f"{len(df)} sections cadastrales dans la commune {code_commune}, dont {len(fiables)} avec au moins {SEUIL_FIABLE} ventes."
    if not fiables.empty:
        h, b = fiables.iloc[0], fiables.iloc[-1]
        txt += (
            f" Section la plus chère : {h['section']} ({_euro(h['prix_m2_median'])}/m², {h['n_ventes']} ventes) ;"
            f" la moins chère : {b['section']} ({_euro(b['prix_m2_median'])}/m², {b['n_ventes']} ventes)."
        )
    return txt


def resume_ventes(total: int, renvoyees: int, code_commune, section) -> str:
    lieu = f"commune {code_commune}" + (f", section {section}" if section else "")
    txt = f"{total} ventes ({lieu})."
    if renvoyees < total:
        txt += f" Les {renvoyees} plus récentes sont renvoyées."
    return txt
