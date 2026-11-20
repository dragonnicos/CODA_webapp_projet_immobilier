SEUIL_FIABLE = 10  # nombre minimal de ventes pour qu'une médiane soit jugée fiable

SOURCE = "DGFiP, DVF (Etalab), Licence Ouverte 2.0. Ventes du Loiret, 2021-2025."

FILTRES_SOURCE = (
    "Ventes d'un seul logement (maison ou appartement), prix de 10 k€ à 2 M€, "
    "surface de 9 à 400 m², prix de 300 à 8 000 €/m²."
)

LIMITES = [
    "Aucun filtre supplémentaire n'est appliqué par l'appli : les ventes atypiques restent comptées, d'où l'usage des médianes.",
    f"Une médiane est jugée fiable à partir de {SEUIL_FIABLE} ventes (sur 5 ans) ; en dessous, elle est signalée.",
    "DVF ne dit rien de l'état du bien, de l'étage ni du DPE : deux biens au même prix au m² ne se valent pas forcément.",
    "Pas d'adresse : la section cadastrale (quelques rues) est le niveau le plus fin.",
    "Les ventes sans coordonnées GPS (2 %) comptent dans les statistiques mais n'apparaissent pas sur les cartes.",
]
