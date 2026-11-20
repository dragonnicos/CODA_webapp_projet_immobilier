"""Prépare les contours (communes et sections cadastrales du Loiret) utilisés par les cartes en aplats.

Sources : geo.api.gouv.fr (communes) et cadastre.data.gouv.fr (sections, Etalab). Licence Ouverte 2.0.
Usage : python scripts/build_geo.py   (télécharge ~8 Mo, écrit data/communes.geojson et data/sections/<code_commune>.geojson)
"""
import gzip
import io
import json
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
URL_COMMUNES = "https://geo.api.gouv.fr/departements/45/communes?format=geojson&geometry=contour&fields=nom,code"
URL_SECTIONS = "https://cadastre.data.gouv.fr/data/etalab-cadastre/latest/geojson/departements/45/cadastre-45-sections.json.gz"
NDEC = 4  # ~10 m, largement suffisant pour une carte régionale


def get(url):
    with urllib.request.urlopen(url, timeout=180) as r:
        return r.read()


def arrondir(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], NDEC), round(coords[1], NDEC)]
    out = [arrondir(c) for c in coords]
    if isinstance(out[0][0], list) or not isinstance(out[0][0], (int, float)):
        return out
    dedup = [out[0]]  # supprime les points consécutifs identiques après arrondi
    for p in out[1:]:
        if p != dedup[-1]:
            dedup.append(p)
    return dedup if len(dedup) >= 4 else out


def polygones(geom):
    return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]


def main():
    communes = json.loads(get(URL_COMMUNES))
    feats = [
        {"type": "Feature", "id": f["properties"]["code"], "properties": {"nom": f["properties"]["nom"]},
         "geometry": {"type": f["geometry"]["type"], "coordinates": arrondir(f["geometry"]["coordinates"])}}
        for f in communes["features"]
    ]
    (DATA / "communes.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))

    sections = json.loads(gzip.GzipFile(fileobj=io.BytesIO(get(URL_SECTIONS))).read())
    # DVF ne garde que 2 caractères pour la section : deux sections d'une commune fusionnée peuvent donc se confondre ; on les réunit.
    par_id = {}
    for f in sections["features"]:
        cle = f"{f['properties']['commune']}-{f['id'][-2:]}"
        par_id.setdefault(cle, []).extend(polygones(f["geometry"]))
    feats = [
        {"type": "Feature", "id": cle, "properties": {},
         "geometry": {"type": "MultiPolygon", "coordinates": arrondir(polys)}}
        for cle, polys in par_id.items()
    ]
    # Un fichier par commune : le serveur n'en lit qu'un à la fois (le fichier unique de 12 Mo coûtait ~125 Mo de RAM une fois parsé).
    dossier = DATA / "sections"
    dossier.mkdir(exist_ok=True)
    par_commune = {}
    for f in feats:
        par_commune.setdefault(f["id"].split("-")[0], []).append(f)
    for code, fs in par_commune.items():
        (dossier / f"{code}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": fs}, separators=(",", ":")))
    print(len(communes["features"]), "communes,", len(feats), "sections")


if __name__ == "__main__":
    main()
