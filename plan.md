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
- Toujours afficher le **nombre de ventes** à côté du prix ; avertir sous 5 ventes (seuil de fiabilité à confirmer, voir « À décider »).
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
1. Explorer les données (valeurs manquantes, distributions, communes à faible volume).
2. `core/` : chargement parquet (une seule fois), médiane/m² par commune et type, recherche par budget, agrégats par section et par vente.
3. Graphique Q1 : prix médian/m² par commune, maison vs appartement, nombre de ventes affiché, carte.
4. Graphique Q2 : curseur de budget (250 k€ par défaut) + surface minimale (100 m²) → communes qui proposent une maison.
5. Drill-down commune → section → vente, avec carte des ventes.
6. Bandeau d'infos : filtres appliqués, limites des données, source.

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

- Seuil minimal de ventes pour considérer un prix fiable (5 ou plus).
- Authentification éventuelle du MCP (public ou protégé par clé).
- Filtres supplémentaires sur les données (outliers).

## 6. Conventions

- Langue de l'interface et de la doc : français.
- Commandes Windows : activer le venv avec `.\.venv\Scripts\Activate.ps1` ; lancer l'app avec `.\.venv\Scripts\python app.py`.
- Ne pas committer sans demande explicite de l'utilisateur.

## 7. Avancement

- 2026-11-20 : lecture du sujet, choix techniques validés, `.venv` + dépendances installés, `plan.md` créé. Prochaine étape : explorer le parquet, puis créer la structure et `core/`.
