# Plan de développement : webapp immobilier Orléans / Loiret

> Fichier de référence pour les sessions Claude Code. À lire en début de session, à mettre à jour (section « Avancement ») en fin de session.

## 1. Contexte

- Sujet : [05-immobilier.md](05-immobilier.md) (cas 5, ventes DVF du Loiret 2021-2025).
- Données : `immobilier.parquet` (46 022 ventes, 325 communes, 32 820 maisons / 13 202 appartements, 02/01/2021 → 31/12/2025). Licence Ouverte 2.0, citer « DGFiP, DVF ».
- Colonnes : `id_mutation, date_mutation, annee, valeur_fonciere, type, surface_reelle_bati, nombre_pieces_principales, prix_m2, surface_terrain, code_commune, nom_commune, code_postal, section, longitude, latitude`.
- Utilisateur cible : un couple qui cherche à acheter. Décision à éclairer : dans quelle commune / quel quartier chercher, pour quel budget.
- Drill-down attendu : commune → section cadastrale → vente.
- Objectif final : un humain explore le dashboard ET une IA (ChatGPT, Claude…) se connecte via MCP.

## 2. Décisions techniques (validées avec l'utilisateur)

| Sujet | Choix |
|---|---|
| Front / analyse | Dash (Python) avec callbacks |
| Graphiques | Plotly (cartes incluses) |
| Environnement | `venv` dans `.venv/` (pas uv), dépendances dans `requirements.txt` |
| Questions métier priorisées | Q1 : prix médian/m² par commune, maison vs appartement. Q2 : budget 250 k€, communes avec maison ≥ 100 m² |
| Drill-down | Commune → section → vente, avec carte (latitude/longitude) |
| Extras (ML, LLM, Q3, Q6) | Aucun pour l'instant |
| Déploiement | Render (Docker), HTTPS, un seul service |
| API | FastAPI, **phase 3 seulement** |
| MCP | Python FastMCP, HTTP distant (Streamable HTTP), monté sur `/mcp` |

### Architecture cible (un seul service, un seul conteneur)

```
core/   logique partagée (filtres, médianes, recherche par budget), aucune dépendance à Dash ni FastAPI
  ├── Dash      /       dashboard pour l'humain (appelle core)
  ├── FastAPI   /api    endpoints JSON (appelle core)     ← phase 3
  └── FastMCP   /mcp    outils pour les IA (appelle core) ← phase 3
```

Règles :
- Les callbacks Dash **ne sont pas** appelés par l'API ou le MCP : tout passe par `core/`.
- L'API/MCP renvoie des chiffres en JSON + un court résumé texte (une IA lit mal un graphique). La figure Plotly en JSON ou PNG reste optionnelle.
- Dash est monté dans FastAPI (via WSGIMiddleware) en phase 3. Les phases 1-2 doivent donc garder une app Dash exposant `server` (Flask) pour gunicorn.

## 3. Règles de qualité des données (à afficher dans l'appli)

- Filtres déjà appliqués dans le fichier : ventes d'un seul logement, prix 10 k–2 M€, 9–400 m², 300–8000 €/m². Les filtres supplémentaires choisis doivent être annoncés dans l'appli.
- Utiliser les **médianes**, jamais les moyennes.
- Toujours afficher le **nombre de ventes** à côté du prix ; avertir sous **10 ventes** (seuil décidé, `SEUIL_FIABLE` dans `core/config.py`).
- DVF ne dit rien de l'état, de l'étage ni du DPE : le mentionner.
- Pas d'adresse : la section cadastrale est le niveau le plus fin.
- Citer la source : « DGFiP, DVF » (Etalab).

## 4. Phases

### Phase 0 : mise en place
- [x] `.venv` créé (Python 3.12.0)
- [x] Dépendances installées : dash 4.5.1, plotly 7.1.0, pandas 3.1.1, pyarrow 26.0.1, dash-bootstrap-components 2.0.4, gunicorn 27.0.1
- [x] `requirements.txt` figé (pip freeze, 36 lignes)
- [x] `.gitignore` (`.venv/`, `__pycache__/`)
- [x] `.dockerignore`
- [x] Structure : `app.py`, `core/`, `assets/`, `data/immobilier.parquet`

### Phase 1 : analyse et dashboard
1. [x] Explorer les données (valeurs manquantes, distributions, communes à faible volume) : voir « 8. Constats de l'exploration ».
2. [x] `core/` : chargement parquet (une seule fois), médiane/m² par commune et type, recherche par budget, agrégats par section et par vente.
3. [x] Graphique Q1 : prix médian/m² par commune, maison vs appartement, nombre de ventes affiché, carte.
4. [x] Graphique Q2 : curseur de budget (250 k€ par défaut) + surface minimale (100 m²) → communes qui proposent une maison.
5. [x] Drill-down commune → section → vente, avec carte des ventes.
6. [x] Bandeau d'infos : filtres appliqués, limites des données, source.

### Phase 2 : déploiement (Dash seul)
1. `Dockerfile` : python slim, `pip install -r requirements.txt`, `gunicorn app:server`, port lu dans `$PORT`.
2. Dépôt GitHub, service Web Render (Docker), HTTPS.
3. Vérifier : démarrage, taille mémoire, temps de chargement du parquet.
4. Note : l'offre gratuite de Render s'endort après 15 min d'inactivité (premier appel ~30 s).

### Phase 3 : API + MCP
1. FastAPI : endpoints JSON appelant `core/` (prix médian par commune, recherche par budget, détail section/vente).
2. Monter Dash dans FastAPI (`/` Dash, `/api` API).
3. FastMCP en HTTP distant sur `/mcp` ; outils dérivés des endpoints.
4. Connexion à Claude.ai et ChatGPT (connecteurs distants), tests.
5. Mise à jour du déploiement Render (même service).

## 5. À décider plus tard

- Authentification éventuelle du MCP (public ou protégé par clé).
- Filtres supplémentaires sur les données (outliers).

## 6. Conventions

- Langue de l'interface et de la doc : français.
- Commandes Windows : activer le venv avec `.\.venv\Scripts\Activate.ps1` ; lancer l'app avec `.\.venv\Scripts\python app.py`.
- Ne pas committer sans demande explicite de l'utilisateur.

## 7. Avancement

- 2026-11-20 : lecture du sujet, choix techniques validés, `.venv` + dépendances installés, `plan.md` créé. Prochaine étape : explorer le parquet, puis créer la structure et `core/`.
- 2026-11-20 (suite) : phase 1 étape 1 faite (exploration, constats en section 8). Prochaine étape : `core/` (chargement parquet, médianes, recherche par budget).

## 8. Constats de l'exploration (phase 1, étape 1)

**Qualité**
- 46 022 lignes, 0 doublon (`id_mutation` unique), aucune valeur manquante sauf `longitude`/`latitude` : 1 011 NA (2,2 %), surtout à Saint-Ay (77 %), Baule (58 %), Chaingy (46 %). Aucune commune n'est 100 % sans GPS : exclure ces lignes de la carte seulement.
- `prix_m2` = `valeur_fonciere / surface_reelle_bati` (écart max 0), cohérent.
- La valeur de `type` est `Maison` / `Appartement` (majuscule).
- `section` : toujours 2 caractères (`ZT`, `AB`, `0E`…), 175 valeurs distinctes, 3 422 couples commune/section.
- `nom_commune` et `code_commune` : 325 uniques chacun. Deux communes ont plusieurs codes postaux (45191, 45234 Orléans) : utiliser `code_commune` comme clé, jamais le code postal.
- « Combleux » (code 45100, 49 ventes) apparaît comme commune distincte : à vérifier/afficher avec prudence.
- `surface_terrain` : 0 pour 96 % des appartements (normal) et 2 % des maisons ; 955 maisons > 1 ha (valeurs extrêmes, ne pas utiliser sans filtre).
- `nombre_pieces_principales` : 12 lignes à 0 pièce, 95 à ≥ 10 : peu fiable, ne pas filtrer dessus.

**Distributions**
- Maisons 32 820 (71 %), appartements 13 202. Volume en baisse : 11 403 ventes en 2021, 8 427 en 2025.
- `prix_m2` : médiane 1 930 €, P5 843, P95 3 476, P99 4 632. 428 ventes < 500 €/m² et 314 > 5 000 €/m² (queues, à surveiller, pas supprimées).
- Médiane/m² par an : appartements 2 088 (2021) → 2 245 (2022) → 2 351 (2023) → 2 174 (2024, 2025) ; maisons 1 780 → 1 892 → 1 888 → 1 851 → 1 837. L'appartement est plus cher au m² que la maison.
- Surface médiane : maison 92 m², appartement 57 m². Valeur médiane : maison 173 k€, appartement 113 k€.
- Écarts communaux : de ~1 000 €/m² (Aillant-sur-Milleron, Bonny-sur-Loire) à ~2 800-3 000 €/m² (Ardon, Combleux) parmi les communes ≥ 30 ventes.

**Communes à faible volume (sur 5 ans)**
- Ventes par commune : < 5 : 4 communes ; < 10 : 22 ; < 20 : 66 ; < 30 : 108 ; < 50 : 167 (soit plus de la moitié sous 50 ventes). Orléans 9 130 ventes, Olivet 1 757, Saint-Jean-de-Braye 1 493.
- Appartements : 217 communes sans aucun appartement, 271 avec < 5. La comparaison maison/appartement n'a de sens que dans une minorité de communes.
- Sections : 1 703 des 3 422 couples commune/section ont < 5 ventes. Le drill-down section doit afficher l'effectif et griser/avertir sous le seuil.

**Implications pour la suite**
- Seuil de fiabilité : 10 ventes retenu (5 jugé trop bas).
- Q2 (≤ 250 k€, maison ≥ 100 m²) : 8 159 ventes, 324 communes sur 325. Le simple filtre est quasi inutile : classer par nombre d'offres et par médiane du prix, avec effectif.
- Carte : filtrer les lignes sans GPS, ne pas les supprimer des statistiques.
- 2026-11-20 (fin de phase 1) : seuil de fiabilité fixé à 10 ventes. `core/` fait (`config.py`, `data.py`, `stats.py` : `prix_median_communes`, `recherche_budget`, `sections_commune`, `ventes_section`). `app.py` : bandeau (source, filtres, limites), 3 onglets (Q1 prix/m² par commune avec carte, Q2 budget/surface, drill-down commune → section → vente avec carte et tableau), filtre de période. Testé : fonctions des callbacks + serveur démarre (HTTP 200). Pas encore vérifié visuellement dans un navigateur. Prochaine étape : phase 2 (Dockerfile, Render).
- 2026-11-20 (cartes en aplats) : les cartes Q1, Q2 et drill-down sont des zones colorées (choroplèthes) au lieu de points. Contours générés par `scripts/build_geo.py` (geo.api.gouv.fr + cadastre.data.gouv.fr, Licence Ouverte) dans `data/communes.geojson` et `data/sections.geojson` (12 Mo, chargé côté serveur, une commune à la fois). 64 couples commune/section de DVF sans contour (non colorés). Poids d'une mise à jour de carte Q1 : ~1,6 Mo (geojson inclus), à optimiser si lent sur Render.
