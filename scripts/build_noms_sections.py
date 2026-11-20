"""Associe à chaque section cadastrale un quartier (IRIS) et ses rues principales.

Sources (Licence Ouverte 2.0) :
  - contours IRIS : WFS IGN (data.geopf.fr), champ nom_iris ;
  - adresses : geo-dvf Etalab (files.data.gouv.fr), champ adresse_nom_voie.
Méthode : chaque vente du parquet est rattachée à l'IRIS qui la contient ; le quartier d'une section est
l'IRIS majoritaire de ses ventes. Les rues sont les plus fréquentes parmi les ventes de la section.
Python pur (pas de geopandas) : le script ne sert qu'à produire data/sections_noms.parquet.

Usage : python scripts/build_noms_sections.py   (télécharge ~6 Mo, écrit data/sections_noms.parquet)
"""
import csv
import gzip
import io
import json
import re
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
URL_IRIS = "https://data.geopf.fr/wfs/ows"
URL_DVF = "https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/45.csv.gz"
ANNEES = range(2021, 2026)
NB_RUES = 3
PETITS_MOTS = {"de", "du", "des", "la", "le", "les", "et", "au", "aux", "sur", "sous", "en", "a", "l", "d"}


def get(url, timeout=180):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def iris_departement():
    """[(code_commune, nom_commune, nom_iris, bbox, polygones)] pour le Loiret."""
    params = {
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
        "TYPENAMES": "STATISTICALUNITS.IRIS:contours_iris", "outputFormat": "application/json",
        "cql_filter": "code_insee LIKE '45%'", "count": "5000",
    }
    data = json.loads(get(URL_IRIS + "?" + urllib.parse.urlencode(params)))
    out = []
    for f in data["features"]:
        g, p = f["geometry"], f["properties"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        xs = [pt[0] for poly in polys for pt in poly[0]]
        ys = [pt[1] for poly in polys for pt in poly[0]]
        out.append((p["code_insee"], p["nom_commune"], p["nom_iris"], (min(xs), min(ys), max(xs), max(ys)), polys))
    return out


def dans_anneau(x, y, ring):
    dedans = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dedans = not dedans
        j = i
    return dedans


def dans_polygone(x, y, poly):
    return dans_anneau(x, y, poly[0]) and not any(dans_anneau(x, y, trou) for trou in poly[1:])


def trouver_iris(x, y, candidats):
    for _code, _nom_c, nom_iris, (x0, y0, x1, y1), polys in candidats:
        if x0 <= x <= x1 and y0 <= y <= y1 and any(dans_polygone(x, y, p) for p in polys):
            return nom_iris
    return None


ABREVIATIONS = {
    "fg": "Faubourg", "fbg": "Faubourg", "bd": "Boulevard", "av": "Avenue", "all": "Allée", "pl": "Place",
    "che": "Chemin", "chem": "Chemin", "rte": "Route", "imp": "Impasse", "sq": "Square", "pas": "Passage",
    "cdt": "Commandant", "mal": "Maréchal", "gen": "Général", "lt": "Lieutenant", "cne": "Capitaine",
    "st": "Saint", "ste": "Sainte", "pdt": "Président", "dr": "Docteur", "abbe": "Abbé", "cite": "Cité",
}


def joli(voie):
    """'RUE DE LA GARE' -> 'Rue de la Gare' ; abréviations DVF développées ; 'DE L AVIATION' -> 'de l'Aviation'."""
    voie = re.sub(r"\b([LD]) (?=[A-Z])", r"\1'", voie.strip().upper())
    mots = re.split(r"(\s+|')", voie.lower())
    out, debut = [], True
    for m in mots:
        if m.strip() and m != "'":
            if m in ABREVIATIONS:
                m = ABREVIATIONS[m]
            elif m in PETITS_MOTS and not debut:
                pass
            else:
                m = m.capitalize()
            debut = False
        out.append(m)
    return "".join(out)


def rues_par_mutation():
    """{id_mutation: voie} depuis le geo-dvf (première voie renseignée de la mutation)."""
    res = {}
    for annee in ANNEES:
        brut = gzip.GzipFile(fileobj=io.BytesIO(get(URL_DVF.format(annee=annee)))).read().decode("utf-8")
        for row in csv.DictReader(io.StringIO(brut)):
            voie = row["adresse_nom_voie"].strip()
            if voie and row["id_mutation"] not in res:
                res[row["id_mutation"]] = voie
        print(annee, "ok,", len(res), "mutations avec voie")
    return res


def main():
    df = pd.read_parquet(DATA / "immobilier.parquet", columns=["id_mutation", "code_commune", "nom_commune", "section", "longitude", "latitude"])

    print("Contours IRIS…")
    iris = iris_departement()
    par_commune = defaultdict(list)
    for it in iris:
        par_commune[it[0]].append(it)
    print(len(iris), "IRIS")

    print("Rattachement des ventes aux IRIS…")
    quartiers = defaultdict(Counter)
    for code, section, lon, lat in zip(df["code_commune"], df["section"], df["longitude"], df["latitude"]):
        if pd.isna(lon) or pd.isna(lat):
            continue
        nom = trouver_iris(lon, lat, par_commune.get(code, []))
        if nom:
            quartiers[(code, section)][nom] += 1

    print("Rues (geo-dvf)…")
    voie_de = rues_par_mutation()
    rues = defaultdict(Counter)
    for idm, code, section in zip(df["id_mutation"], df["code_commune"], df["section"]):
        voie = voie_de.get(idm)
        if voie:
            rues[(code, section)][joli(voie)] += 1

    noms_commune = df.drop_duplicates("code_commune").set_index("code_commune")["nom_commune"].to_dict()
    lignes = []
    for code, section in df[["code_commune", "section"]].drop_duplicates().itertuples(index=False):
        q = quartiers[(code, section)].most_common(1)
        quartier = q[0][0] if q else ""
        if quartier == noms_commune.get(code) or quartier.isdigit():
            # petite commune (l'IRIS porte le nom de la commune) ou IRIS non nommé (simple numéro) : inutile
            quartier = ""
        top = [v for v, _ in rues[(code, section)].most_common(NB_RUES)]
        libelle = " · ".join(p for p in (quartier, ", ".join(top)) if p)
        lignes.append({"code_commune": code, "section": section, "quartier": quartier,
                       "rues_principales": ", ".join(top), "libelle": libelle})
    out = pd.DataFrame(lignes).sort_values(["code_commune", "section"]).reset_index(drop=True)
    out.to_parquet(DATA / "sections_noms.parquet", index=False)
    print(len(out), "sections ;", (out["quartier"] != "").sum(), "avec quartier ;", (out["rues_principales"] != "").sum(), "avec rues")


if __name__ == "__main__":
    main()
