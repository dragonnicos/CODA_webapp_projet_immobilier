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


def reponse(resume: str, donnees, avertissement: str | None = None, **extra) -> dict:
    return {
        "resume": resume,
        "donnees": donnees,
        **extra,
        "source": SOURCE,
        "filtres_source": FILTRES_SOURCE,
        "avertissement": avertissement
        or (
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


# ---------------------------------------------------------------- tendance, prévision, estimation
def _trimestre(d) -> str:
    d = pd.Timestamp(d)
    return f"{d.year} T{(d.month - 1) // 3 + 1}"


def resume_tendance(df: pd.DataFrame, type_, annee_min, annee_max) -> str:
    if df.empty:
        return "Aucune vente pour cette sélection."
    parts = []
    for t, g in df.sort_values("trimestre").groupby("type"):
        k = min(4, len(g) // 2)
        if k == 0:
            continue
        a, b = g["prix_m2_median"].head(k).mean(), g["prix_m2_median"].tail(k).mean()
        parts.append(
            f"{t} : {_euro(a)}/m² ({_trimestre(g['trimestre'].iloc[0])}) → {_euro(b)}/m² ({_trimestre(g['trimestre'].iloc[-1])}), {(b / a - 1) * 100:+.1f} %"
        )
    return (
        f"Prix médian au m² par trimestre, {_periode(annee_min, annee_max)} (Loiret). "
        + " ; ".join(parts)
        + " (moyenne des médianes trimestrielles en début et en fin de période)."
    )


def resume_variation(df: pd.DataFrame, type_, annee_min, annee_max, fenetres) -> str:
    if df.empty:
        return "Aucune commune avec assez de ventes au début et à la fin de la période."
    (d0, d1), (f0, f1) = fenetres
    fen = lambda a, b: str(a) if a == b else f"{a}-{b}"
    h, b = df.iloc[0], df.iloc[-1]
    return (
        f"{len(df)} communes comparables ({type_}), prix médian {fen(d0, d1)} → {fen(f0, f1)} : variation médiane "
        f"{df['variation_pct'].median():+.1f} %, {int((df['variation_pct'] > 0).sum())} en hausse. "
        f"Plus forte hausse : {h['nom_commune']} ({h['variation_pct']:+.1f} %) ; plus forte baisse : {b['nom_commune']} ({b['variation_pct']:+.1f} %)."
    )


def resume_evolution(df: pd.DataFrame, code_commune) -> str:
    if df.empty:
        return f"Aucune vente pour la commune {code_commune}."
    g = df.sort_values("annee")
    nom = g["nom_commune"].iloc[0]
    a, b = g.iloc[0], g.iloc[-1]
    return (
        f"{nom} : {_euro(a['prix_m2_median'])}/m² en {a['annee']} ({a['n_ventes']} ventes) → "
        f"{_euro(b['prix_m2_median'])}/m² en {b['annee']} ({b['n_ventes']} ventes)."
    )


def resume_marche(prev: pd.DataFrame, type_) -> str:
    p = prev[prev["annee"] == prev["annee"].min()]
    niv = ", ".join(f"{r.zone} {r.indice:.0f}" for r in p.itertuples())
    return (
        f"Indice de prix à qualité constante, {type_.lower()}s (base 100 = 1er semestre 2021). Niveau actuel par zone : {niv}. "
        "La prévision est le niveau actuel avec une fourchette qui s'élargit avec l'horizon : sur 2021-2025, extrapoler une "
        "tendance se trompe plus que supposer le marché stable, donc aucune hausse ni baisse n'est annoncée."
    )


def resume_estimation(r: dict, type_, budget) -> str:
    txt = (
        f"{type_} de {r['surface']:.0f} m² à {r['nom_commune']} ({r['annee']}) : estimation {_euro(r['prix_estime'])} "
        f"({_euro(r['prix_m2'])}/m²), fourchette à 80 % de {_euro(r['prix_bas'])} à {_euro(r['prix_haut'])}."
    )
    if budget is not None:
        txt += f" Budget {_euro(budget)} : {r['statut']} (marge {r['marge_pct']:+.0f} %)."
    if not r["fiable"]:
        txt += f" Attention : moins de {SEUIL_FIABLE} ventes de ce type dans la commune."
    return txt


def resume_projet(df: pd.DataFrame, budget, type_, surface, annee) -> str:
    n = df["statut"].value_counts()
    sures = df[df["statut"] == "sûr"].head(5)
    txt = (
        f"{type_} de {surface:.0f} m², achat en {annee}, budget {_euro(budget)} : {n.get('sûr', 0)} communes sûres, "
        f"{n.get('possible', 0)} possibles, {n.get('hors budget', 0)} hors budget."
    )
    if not sures.empty:
        txt += " Les plus proches d'Orléans parmi les sûres : " + ", ".join(
            f"{r.nom_commune} ({r.distance_km:.0f} km, {_euro(r.prix_estime)})" for r in sures.itertuples()
        ) + "."
    return txt
