"""Entraîne le modèle de prix et l'enregistre dans data/modele_prix.joblib.

À lancer en LOCAL (quelques secondes à 1 minute), puis committer le fichier : le serveur (Render) ne fait que le charger.
À relancer si le parquet change ou si scikit-learn est mis à jour.

    python scripts/build_model.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import ml  # noqa: E402

t = time.time()
chemin = ml.sauver()
M = ml._modeles()
print(f"Modèle enregistré : {chemin} ({chemin.stat().st_size / 1e6:.1f} Mo) en {time.time() - t:.0f} s")
print(f"Entraîné sur {M['n']} ventes jusqu'au {M['donnees_jusqu_au']}, scikit-learn {M['sklearn']}")
print("Précision mesurée :", M["evaluation"])
