import os

import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, Input, Output, ctx, dash_table, dcc, html

import core
from core.indice import ZONES

app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY], title="Immobilier Loiret")
server = app.server  # Flask, pour gunicorn : gunicorn app:server

CARTE_CENTRE = {"lat": 47.92, "lon": 2.2}
SEUIL = core.SEUIL_FIABLE
R = core.resume_global()
COMMUNES = core.liste_communes()
ANNEES = list(range(2021, 2026))
VIDE = px.scatter(title="Aucune donnée pour cette sélection")
COULEURS_STATUT = {"assez de ventes": "#2c7fb8", f"< {SEUIL} ventes": "#bbbbbb"}
TYPES = ["Tous", "Maison", "Appartement"]


def euro(x):
    return f"{x:,.0f}".replace(",", " ") + " €"


def radio_type(id_):
    return dcc.RadioItems(TYPES, "Tous", id=id_, inline=True, inputClassName="me-1", labelClassName="me-3")


# ---------------------------------------------------------------- bandeau
bandeau = dbc.Alert(
    [
        html.Div([html.B("Source : "), core.SOURCE]),
        html.Div([html.B("Filtres déjà appliqués : "), core.FILTRES_SOURCE]),
        html.Details(
            [html.Summary("Limites des données"), html.Ul([html.Li(t) for t in core.LIMITES])],
            className="mt-1",
        ),
    ],
    color="light",
    className="small border",
)

periode = dbc.Row(
    [
        dbc.Col(html.Label("Période (années) :"), width="auto"),
        dbc.Col(
            dcc.RangeSlider(2021, 2025, 1, value=[2021, 2025], marks={a: str(a) for a in ANNEES}, id="periode"),
            md=5,
        ),
    ],
    className="mb-2 align-items-center",
)

# ---------------------------------------------------------------- Q1
tab_q1 = dbc.Container(
    [
        html.P("Prix médian au m² par commune. Taille du point = nombre de ventes, couleur = prix médian.", className="mt-3"),
        dbc.Row(
            [
                dbc.Col(radio_type("q1-type"), md="auto"),
                dbc.Col(
                    dbc.Checkbox(id="q1-peu-fiables", label=f"Afficher aussi les communes de moins de {SEUIL} ventes (peu fiables)"),
                    md="auto",
                ),
            ]
        ),
        html.Div(id="q1-resume", className="my-2 fw-bold"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="q1-carte", config={"scrollZoom": True}), md=7),
                dbc.Col(dcc.Graph(id="q1-barres"), md=5),
            ]
        ),
        html.Div(
            f"Maison contre appartement : seules les communes avec au moins {SEUIL} ventes de chaque type sont comparables.",
            className="text-muted small",
        ),
    ],
    fluid=True,
)

# ---------------------------------------------------------------- Q2
tab_q2 = dbc.Container(
    [
        html.P("Avec ce budget, dans quelles communes a-t-on vendu une maison d'au moins cette surface ?", className="mt-3"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label("Budget maximum (€)"),
                        dcc.Slider(
                            100_000, 600_000, 10_000, value=250_000, id="q2-budget",
                            marks={v: f"{v // 1000} k" for v in range(100_000, 600_001, 100_000)},
                            tooltip={"placement": "bottom"},
                        ),
                    ],
                    md=6,
                ),
                dbc.Col(
                    [
                        html.Label("Surface minimale (m²)"),
                        dcc.Slider(
                            40, 250, 10, value=100, id="q2-surface",
                            marks={v: str(v) for v in (40, 100, 150, 200, 250)},
                            tooltip={"placement": "bottom"},
                        ),
                    ],
                    md=6,
                ),
            ],
            className="mb-3",
        ),
        html.Div(id="q2-resume", className="my-2 fw-bold"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="q2-carte", config={"scrollZoom": True}), md=6),
                dbc.Col(dcc.Graph(id="q2-barres"), md=6),
            ]
        ),
        html.Div(
            f"Classement par nombre de ventes correspondant (sur la période). Moins de {SEUIL} ventes correspondantes : barre grisée.",
            className="text-muted small",
        ),
    ],
    fluid=True,
)

# ---------------------------------------------------------------- Drill-down
tab_drill = dbc.Container(
    [
        html.P("Commune, puis section cadastrale (cliquez sur une barre), puis ventes.", className="mt-3"),
        dbc.Row(
            [
                dbc.Col(
                    dcc.Dropdown(
                        options=[
                            {"label": f"{r.nom_commune} ({r.n_ventes} ventes)", "value": r.code_commune}
                            for r in COMMUNES.itertuples()
                        ],
                        value="45234", clearable=False, id="dd-commune",
                    ),
                    md=5,
                ),
                dbc.Col(radio_type("dd-type"), md="auto"),
                dbc.Col(dbc.Button("Toutes les sections", id="dd-reset", size="sm", outline=True), md="auto"),
            ],
            className="mb-2",
        ),
        dcc.Store(id="dd-section"),
        html.Div(id="dd-resume", className="my-2 fw-bold"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="dd-barres"), md=5),
                dbc.Col(dcc.Graph(id="dd-carte", config={"scrollZoom": True}), md=7),
            ]
        ),
        html.H6("Ventes", className="mt-2"),
        dash_table.DataTable(
            id="dd-table", page_size=15, sort_action="native",
            style_table={"overflowX": "auto"}, style_cell={"fontSize": 13, "padding": "4px"},
            style_header={"fontWeight": "bold"},
        ),
    ],
    fluid=True,
)

# ---------------------------------------------------------------- Tendance
tab_tend = dbc.Container(
    [
        html.P("Comment les prix évoluent-ils dans le temps ? Médianes par trimestre (Loiret), puis variation par commune.", className="mt-3"),
        dbc.Row([dbc.Col(radio_type("tend-type"), md="auto")]),
        dbc.Row([dbc.Col(dcc.Graph(id="tend-marche"), md=12)]),
        html.Div(id="tend-resume", className="my-2 fw-bold"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="tend-carte", config={"scrollZoom": True}), md=7),
                dbc.Col(dcc.Graph(id="tend-barres"), md=5),
            ]
        ),
        html.Div(
            f"Variation = médiane de la fin de période contre celle du début (2 ans de chaque côté si la période dépasse 3 ans, sinon 1 an). "
            f"Seules les communes avec au moins {SEUIL} ventes dans chacune des deux fenêtres sont colorées.",
            className="text-muted small",
        ),
        html.H6("Comparer des communes", className="mt-3"),
        dcc.Dropdown(
            options=[{"label": r.nom_commune, "value": r.code_commune} for r in COMMUNES.itertuples()],
            value=["45234"], multi=True, id="tend-communes", placeholder="Choisir une ou plusieurs communes",
        ),
        dcc.Graph(id="tend-compare"),
        html.Div(
            f"Médiane annuelle par commune. Points creux : moins de {SEUIL} ventes cette année-là, à lire avec prudence.",
            className="text-muted small",
        ),
    ],
    fluid=True,
)

# ---------------------------------------------------------------- Mon projet (modèle ML)
STATUTS = {"sûr": "#2ca25f", "possible": "#fdae61", "hors budget": "#bdbdbd"}


def _champ(label, composant, md):
    return dbc.Col([html.Label(label, className="small mb-0"), composant], md=md)


tab_projet = dbc.Container(
    [
        html.P(
            "Décrivez votre projet : le modèle estime le prix du bien dans chaque commune et indique où il entre dans votre budget.",
            className="mt-3",
        ),
        dbc.Row(
            [
                _champ("Type de bien", dcc.RadioItems(["Maison", "Appartement"], "Maison", id="pj-type", inline=True,
                                                      inputClassName="me-1", labelClassName="me-3"), 3),
                _champ("Surface habitable (m²)", dbc.Input(id="pj-surface", type="number", min=9, max=400, step=1, value=100, debounce=True), 2),
                _champ("Pièces", dcc.Dropdown(
                    options=[{"label": "Non précisé", "value": 0}] + [{"label": str(i) if i < 5 else "5 et +", "value": i} for i in range(1, 6)],
                    value=0, clearable=False, id="pj-pieces"), 2),
                _champ("Terrain (m²), maison", dbc.Input(id="pj-terrain", type="number", min=0, step=10, placeholder="non précisé", debounce=True), 2),
                _champ("Année d'achat", dcc.RadioItems([2026, 2027, 2028], 2026, id="pj-annee", inline=True,
                                                       inputClassName="me-1", labelClassName="me-3"), 3),
            ],
            className="mb-3 align-items-end",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label("Budget maximum (€)"),
                        dcc.Slider(100_000, 600_000, 10_000, value=250_000, id="pj-budget",
                                   marks={v: f"{v // 1000} k" for v in range(100_000, 600_001, 100_000)},
                                   tooltip={"placement": "bottom"}),
                    ],
                    md=8,
                ),
                dbc.Col(dbc.Checkbox(id="pj-peu-fiables", label=f"Inclure les communes de moins de {SEUIL} ventes (peu fiables)"), md=4),
            ],
            className="mb-3",
        ),
        html.Div(id="pj-resume", className="my-2 fw-bold"),
        html.Div(id="pj-notice"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="pj-carte", config={"scrollZoom": True}), md=7),
                dbc.Col(dcc.Graph(id="pj-zones"), md=5),
            ]
        ),
        html.Div(
            [
                html.B("Lecture : "),
                "« sûr » = même le haut de la fourchette (80 % des ventes) tient dans le budget ; « possible » = l'estimation tient, "
                "pas forcément le haut de la fourchette ; « hors budget » = l'estimation dépasse le budget. "
                "La fourchette décrit des ventes individuelles : DVF ne connaît ni l'état, ni l'étage, ni le DPE.",
            ],
            className="text-muted small",
        ),
        html.H6("Détail d'une commune", className="mt-3"),
        dcc.Dropdown(
            options=[{"label": r.nom_commune, "value": r.code_commune} for r in COMMUNES.itertuples()],
            value="45234", clearable=False, id="pj-commune",
        ),
        html.Div(id="pj-detail", className="my-2"),
        html.H6("Toutes les communes", className="mt-3"),
        dash_table.DataTable(
            id="pj-table", page_size=15, sort_action="native",
            style_table={"overflowX": "auto"}, style_cell={"fontSize": 13, "padding": "4px"},
            style_header={"fontWeight": "bold"},
            style_data_conditional=[
                {"if": {"filter_query": '{Statut} = "sûr"', "column_id": "Statut"}, "color": "#1a7f45", "fontWeight": "bold"},
                {"if": {"filter_query": '{Statut} = "possible"', "column_id": "Statut"}, "color": "#c26b00", "fontWeight": "bold"},
            ],
        ),
    ],
    fluid=True,
)

app.layout = dbc.Container(
    [
        html.H2("Immobilier Orléans / Loiret : où chercher, pour quel budget ?", className="mt-3"),
        html.Div(
            f"{R['n_ventes']:,} ventes, {R['n_communes']} communes, {R['date_min']} → {R['date_max']}".replace(",", " "),
            className="text-muted",
        ),
        bandeau,
        periode,
        dbc.Tabs(
            [
                dbc.Tab(tab_q1, label="Prix au m² par commune", tab_id="q1"),
                dbc.Tab(tab_q2, label="Mon budget", tab_id="q2"),
                dbc.Tab(tab_projet, label="Mon projet (estimation)", tab_id="pj"),
                dbc.Tab(tab_tend, label="Tendance du marché", tab_id="tend"),
                dbc.Tab(tab_drill, label="Explorer commune → section → vente", tab_id="dd"),
            ],
            active_tab="q1",
        ),
        html.Footer(f"Source : {core.SOURCE}", className="text-muted small my-3"),
    ],
    fluid=True,
)


def _map(fig, centre=None, zoom=8.3):
    fig.update_layout(
        map_style="open-street-map", map_center=centre or CARTE_CENTRE, map_zoom=zoom,
        margin=dict(l=0, r=0, t=30, b=0), height=520,
    )
    return fig


def aplats(geojson, ids, z, textes, titre_barre, fig=None, zmin=None, zmax=None, colorscale="YlOrRd"):
    """Carte en aplats : une zone colorée par commune (ou par section)."""
    fig = fig or go.Figure()
    fig.add_trace(go.Choroplethmap(
        geojson=geojson, locations=list(ids), z=list(z), text=list(textes), hoverinfo="text",
        colorscale=colorscale, zmin=zmin, zmax=zmax, marker_opacity=0.75, marker_line_width=0.6,
        marker_line_color="white", colorbar=dict(title=titre_barre, thickness=12, len=0.7),
    ))
    return fig


def bornes(serie):
    """Échelle de couleurs bornée aux percentiles 5-95 : quelques valeurs extrêmes n'écrasent pas la carte."""
    return float(serie.quantile(0.05)), float(serie.quantile(0.95))


# ---------------------------------------------------------------- callbacks Q1
@app.callback(
    Output("q1-carte", "figure"), Output("q1-barres", "figure"), Output("q1-resume", "children"),
    Input("q1-type", "value"), Input("q1-peu-fiables", "value"), Input("periode", "value"),
)
def maj_q1(type_, peu_fiables, periode):
    fiables_seulement = not peu_fiables
    d = core.prix_median_communes(type_, periode[0], periode[1], fiables_seulement=fiables_seulement)
    if d.empty:
        return VIDE, VIDE, "Aucune commune avec assez de ventes."
    # carte : une valeur par commune (types confondus si « Tous »)
    m = core.prix_median_communes(type_, periode[0], periode[1], fiables_seulement=fiables_seulement, par_type=False)
    textes = [
        f"<b>{r.nom_commune}</b><br>{euro(r.prix_m2_median)}/m² (médiane)<br>{r.n_ventes} ventes"
        + ("" if r.fiable else f"<br><i>moins de {SEUIL} ventes : peu fiable</i>")
        for r in m.itertuples()
    ]
    zmin, zmax = bornes(m["prix_m2_median"])
    carte = aplats(core.communes_geojson(), m["code_commune"], m["prix_m2_median"], textes, "€/m²", zmin=zmin, zmax=zmax)
    _map(carte)
    d = d.copy()
    d["label"] = d["nom_commune"] + " (" + d["type"].astype(str) + ")" if type_ == "Tous" else d["nom_commune"]
    top = d.sort_values("prix_m2_median")
    sel = top if len(top) <= 30 else top.iloc[list(range(15)) + list(range(-15, 0))]
    barres = px.bar(
        sel, x="prix_m2_median", y="label", orientation="h", color="type" if type_ == "Tous" else None,
        text=sel["n_ventes"].map(lambda n: f"{n} ventes"), barmode="group",
        labels={"prix_m2_median": "Prix médian €/m²", "label": ""},
        title="Les 15 communes les moins chères et les 15 plus chères",
    )
    barres.update_layout(
        height=520, margin=dict(l=0, r=0, t=40, b=0),
        yaxis=dict(categoryorder="array", categoryarray=list(sel["label"])),
    )
    return carte, barres, f"{len(m)} communes colorées (zones sans couleur : pas assez de ventes), médiane des communes : {euro(m['prix_m2_median'].median())}/m²."


# ---------------------------------------------------------------- callbacks Q2
@app.callback(
    Output("q2-carte", "figure"), Output("q2-barres", "figure"), Output("q2-resume", "children"),
    Input("q2-budget", "value"), Input("q2-surface", "value"), Input("periode", "value"),
)
def maj_q2(budget, surface, periode):
    d = core.recherche_budget(budget, surface, "Maison", periode[0], periode[1])
    if d.empty:
        return VIDE, VIDE, f"Aucune maison d'au moins {surface} m² vendue à {euro(budget)} ou moins."
    d = d.assign(statut=d["fiable"].map({True: "assez de ventes", False: f"< {SEUIL} ventes"}))
    top = d.head(20).iloc[::-1]
    barres = px.bar(
        top, x="n_offres", y="nom_commune", orientation="h", color="statut",
        color_discrete_map=COULEURS_STATUT,
        text=top.apply(lambda r: f"médiane {euro(r.prix_median)}, {r.surface_mediane:.0f} m²", axis=1),
        labels={"n_offres": "Ventes correspondantes", "nom_commune": ""},
        title="20 communes avec le plus de ventes correspondantes",
    )
    barres.update_layout(height=520, margin=dict(l=0, r=0, t=40, b=0), legend_title_text="")
    textes = [
        f"<b>{r.nom_commune}</b><br>{r.n_offres} ventes correspondantes ({int(r.part_sous_budget * 100)} % des maisons de cette surface)"
        f"<br>prix médian {euro(r.prix_median)}, surface médiane {r.surface_mediane:.0f} m²"
        + ("" if r.fiable else f"<br><i>moins de {SEUIL} ventes : peu fiable</i>")
        for r in d.itertuples()
    ]
    carte = aplats(core.communes_geojson(), d["code_commune"], d["n_offres"], textes, "ventes",
                   zmin=0, zmax=max(float(d["n_offres"].quantile(0.95)), 1), colorscale="Blues")
    _map(carte)
    n_fiables = int(d["fiable"].sum())
    return carte, barres, (
        f"{len(d)} communes (plus la zone est foncée, plus il y a de ventes correspondantes) ont vu au moins une vente de maison de {surface} m² ou plus à {euro(budget)} ou moins "
        f"({n_fiables} avec au moins {SEUIL} ventes, {int(d['n_offres'].sum())} ventes au total)."
    )


# ---------------------------------------------------------------- callbacks drill-down
@app.callback(
    Output("dd-section", "data"),
    Input("dd-barres", "clickData"), Input("dd-carte", "clickData"), Input("dd-reset", "n_clicks"),
    Input("dd-commune", "value"), Input("dd-type", "value"),
    prevent_initial_call=True,
)
def choisir_section(click_barres, click_carte, _reset, _commune, _type):
    if ctx.triggered_id == "dd-barres" and click_barres:
        return click_barres["points"][0]["y"]
    if ctx.triggered_id == "dd-carte" and click_carte:
        loc = click_carte["points"][0].get("location")  # zone cliquée : "code_commune-section"
        return loc.split("-")[1] if loc else None
    return None


@app.callback(
    Output("dd-barres", "figure"), Output("dd-carte", "figure"), Output("dd-table", "data"),
    Output("dd-table", "columns"), Output("dd-resume", "children"),
    Input("dd-commune", "value"), Input("dd-type", "value"), Input("dd-section", "data"), Input("periode", "value"),
)
def maj_drill(code, type_, section, periode):
    nom = COMMUNES.loc[COMMUNES.code_commune == code, "nom_commune"].iloc[0]
    secs = core.sections_commune(code, type_, periode[0], periode[1])
    ventes = core.ventes_section(code, section, type_, periode[0], periode[1])
    if secs.empty:
        return VIDE, VIDE, [], [], f"{nom} : aucune vente pour cette sélection."
    secs = secs.assign(statut=secs["fiable"].map({True: "assez de ventes", False: f"< {SEUIL} ventes"}))
    secs = secs.sort_values("prix_m2_median")
    # Axe : quartier (ou première rue) + code ; la valeur de y reste le code, nécessaire au clic.
    court = [
        f"{q or (r.split(', ')[0] if r else 'Section')} ({s})"
        for q, r, s in zip(secs["quartier"], secs["rues_principales"], secs["section"])
    ]
    barres = px.bar(
        secs, x="prix_m2_median", y="section", orientation="h", color="statut",
        color_discrete_map=COULEURS_STATUT, text=secs["n_ventes"].map(lambda n: f"{n} ventes"),
        labels={"prix_m2_median": "Prix médian €/m²", "section": "Section"},
        title=f"{nom} : médiane par section (cliquez sur une barre ou une zone)",
        custom_data=["libelle"],
    )
    barres.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>%{x:,.0f} €/m²<extra></extra>")
    barres.update_layout(
        height=max(420, 22 * len(secs)), margin=dict(l=0, r=0, t=40, b=0), legend_title_text="",
        yaxis=dict(type="category", tickmode="array", tickvals=list(secs["section"]), ticktext=court, automargin=True),
    )
    gj = core.sections_geojson(code)
    dispo = {f["id"].split("-")[1] for f in gj["features"]}
    sa = secs[secs["section"].isin(dispo)]
    ids = [f"{code}-{x}" for x in sa["section"]]
    textes = [
        f"<b>{r.libelle}</b> <i>(section {r.section})</i><br>{euro(r.prix_m2_median)}/m² (médiane)<br>{r.n_ventes} ventes"
        + ("" if r.fiable else f"<br><i>moins de {SEUIL} ventes : peu fiable</i>")
        for r in sa.itertuples()
    ]
    geo = ventes.dropna(subset=["latitude"])
    if section and not geo.empty:  # section choisie : on retire les zones, on garde les ventes colorées
        zmin, zmax = bornes(geo["prix_m2"]) if len(geo) > 2 else (None, None)
        carte = go.Figure(go.Scattermap(
            lat=geo.latitude, lon=geo.longitude, mode="markers",
            marker=dict(size=13, color=geo["prix_m2"], colorscale="YlOrRd", cmin=zmin, cmax=zmax, opacity=0.9,
                        colorbar=dict(title="€/m²", thickness=12, len=0.7)),
            text=[
                f"<b>{r.type}</b> : {euro(r.valeur_fonciere)}<br>{r.surface_reelle_bati:.0f} m², {r.prix_m2:.0f} €/m²<br>{r.date_mutation:%d/%m/%Y}"
                for r in geo.itertuples()
            ],
            hoverinfo="text",
        ))
        _map(carte, {"lat": float(geo.latitude.median()), "lon": float(geo.longitude.median())}, 14)
        carte.update_layout(showlegend=False)
    elif sa.empty:
        carte = VIDE
    else:
        f_ok = sa["fiable"].to_numpy()
        carte = go.Figure()
        if (~f_ok).any():  # sections peu fiables : en gris
            carte.add_trace(go.Choroplethmap(
                geojson=gj, locations=[i for i, k in zip(ids, f_ok) if not k], z=[0] * int((~f_ok).sum()),
                text=[t for t, k in zip(textes, f_ok) if not k], hoverinfo="text",
                colorscale=[[0, "#cccccc"], [1, "#cccccc"]], showscale=False, marker_opacity=0.6,
                marker_line_width=0.6, marker_line_color="white",
            ))
        if f_ok.any():
            ok = sa[f_ok]
            zmin, zmax = bornes(ok["prix_m2_median"]) if len(ok) > 2 else (None, None)
            aplats(gj, [i for i, k in zip(ids, f_ok) if k], ok["prix_m2_median"],
                   [t for t, k in zip(textes, f_ok) if k], "€/m²", fig=carte, zmin=zmin, zmax=zmax)
        centre = {"lat": float(geo.latitude.median()), "lon": float(geo.longitude.median())} if not geo.empty else None
        _map(carte, centre, 11)
        carte.update_layout(showlegend=False)
    t = ventes.drop(columns=["latitude", "longitude"]).assign(date_mutation=ventes["date_mutation"].dt.strftime("%Y-%m-%d"))
    noms = {
        "date_mutation": "Date", "type": "Type", "valeur_fonciere": "Prix (€)", "surface_reelle_bati": "Surface (m²)",
        "nombre_pieces_principales": "Pièces", "prix_m2": "€/m²", "surface_terrain": "Terrain (m²)", "section": "Section",
    }
    cols = [{"name": n, "id": i} for i, n in noms.items()]
    lieu = f"{nom}, section {section}" if section else nom
    if ventes.empty:
        return barres, carte, [], cols, f"{lieu} : aucune vente."
    avert = f" Moins de {SEUIL} ventes : médiane peu fiable." if len(ventes) < SEUIL else ""
    return barres, carte, t.to_dict("records"), cols, f"{lieu} : {len(ventes)} ventes, médiane {euro(ventes['prix_m2'].median())}/m².{avert}"


# ---------------------------------------------------------------- callbacks tendance
@app.callback(
    Output("tend-marche", "figure"), Output("tend-carte", "figure"), Output("tend-barres", "figure"),
    Output("tend-resume", "children"), Input("tend-type", "value"), Input("periode", "value"),
)
def maj_tendance(type_, periode):
    e = core.evolution_marche(type_, True, periode[0], periode[1])
    if e.empty:
        return VIDE, VIDE, VIDE, "Aucune donnée pour cette sélection."
    marche = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.04)
    for t, couleur in (("Maison", "#2c7fb8"), ("Appartement", "#e6550d")):
        x = e[e["type"] == t]
        if x.empty:
            continue
        marche.add_trace(go.Scatter(
            x=x["trimestre"], y=x["prix_m2_median"], mode="lines+markers", name=t, line=dict(color=couleur),
            customdata=x["n_ventes"], hovertemplate="%{x|%Y T%q}<br>%{y:,.0f} €/m² (médiane)<br>%{customdata} ventes<extra>" + t + "</extra>",
        ), row=1, col=1)
        marche.add_trace(go.Bar(x=x["trimestre"], y=x["n_ventes"], name=t, marker_color=couleur, showlegend=False, opacity=0.7), row=2, col=1)
    marche.update_layout(height=520, margin=dict(l=0, r=0, t=40, b=0), barmode="group",
                         title="Prix médian au m² et nombre de ventes par trimestre (Loiret)", legend_title_text="")
    marche.update_yaxes(title_text="€/m²", row=1, col=1)
    marche.update_yaxes(title_text="Ventes", row=2, col=1)

    if periode[1] <= periode[0]:
        return marche, VIDE, VIDE, "Choisissez une période d'au moins deux années pour voir les variations par commune."
    v = core.variation_communes(type_, periode[0], periode[1])
    if v.empty:
        return marche, VIDE, VIDE, "Aucune commune avec assez de ventes au début et à la fin de la période."
    (d0, d1), (f0, f1) = v.attrs["fenetres"]
    fen = lambda a, b: str(a) if a == b else f"{a}-{b}"
    textes = [
        f"<b>{r.nom_commune}</b><br>{r.variation_pct:+.1f} %<br>{euro(r.prix_debut)} ({r.n_debut} ventes, {fen(d0, d1)})"
        f" → {euro(r.prix_fin)} ({r.n_fin} ventes, {fen(f0, f1)})"
        for r in v.itertuples()
    ]
    lim = max(abs(float(v["variation_pct"].quantile(0.05))), abs(float(v["variation_pct"].quantile(0.95))), 1)
    carte = aplats(core.communes_geojson(), v["code_commune"], v["variation_pct"], textes, "%",
                   zmin=-lim, zmax=lim, colorscale="RdBu_r")
    _map(carte)
    sel = pd.concat([v.head(10), v.tail(10)]).drop_duplicates("code_commune").sort_values("variation_pct")
    barres = px.bar(
        sel, x="variation_pct", y="nom_commune", orientation="h", text=sel["variation_pct"].map(lambda x: f"{x:+.1f} %"),
        color=sel["variation_pct"] > 0, color_discrete_map={True: "#d6604d", False: "#4393c3"},
        labels={"variation_pct": f"Variation du prix médian (%) {fen(d0, d1)} → {fen(f0, f1)}", "nom_commune": ""},
        title="Les 10 plus fortes hausses et baisses",
    )
    barres.update_layout(height=520, margin=dict(l=0, r=0, t=40, b=0), showlegend=False,
                         yaxis=dict(categoryorder="array", categoryarray=list(sel["nom_commune"])))
    resume = (
        f"{len(v)} communes comparables : variation médiane {v['variation_pct'].median():+.1f} %, "
        f"{int((v['variation_pct'] > 0).sum())} en hausse et {int((v['variation_pct'] <= 0).sum())} en baisse."
    )
    return marche, carte, barres, resume


@app.callback(Output("tend-compare", "figure"), Input("tend-communes", "value"), Input("tend-type", "value"), Input("periode", "value"))
def maj_comparaison(codes, type_, periode):
    if not codes:
        return VIDE
    d = core.evolution_communes(codes, type_, periode[0], periode[1])
    if d.empty:
        return VIDE
    fig = go.Figure()
    for nom, x in d.groupby("nom_commune", observed=True):
        fig.add_trace(go.Scatter(
            x=x["annee"], y=x["prix_m2_median"], mode="lines+markers", name=nom,
            marker=dict(symbol=["circle" if f else "circle-open" for f in x["fiable"]], size=9),
            customdata=x["n_ventes"], hovertemplate="%{x}<br>%{y:,.0f} €/m² (médiane)<br>%{customdata} ventes<extra>" + nom + "</extra>",
        ))
    fig.update_layout(height=420, margin=dict(l=0, r=0, t=30, b=0), title="Prix médian au m² par année", legend_title_text="",
                      xaxis=dict(dtick=1), yaxis_title="€/m²")
    return fig


# ---------------------------------------------------------------- callbacks Mon projet
def _critere(surface, pieces, terrain):
    """Valide la saisie ; renvoie (surface, pièces, terrain) ou None si la surface est inutilisable."""
    if surface is None or not 9 <= surface <= 400:
        return None
    return float(surface), (int(pieces) if pieces else None), (float(terrain) if terrain is not None else None)


@app.callback(Output("pj-terrain", "disabled"), Input("pj-type", "value"))
def terrain_actif(type_):
    return type_ == "Appartement"


@app.callback(
    Output("pj-carte", "figure"), Output("pj-zones", "figure"), Output("pj-table", "data"), Output("pj-table", "columns"),
    Output("pj-resume", "children"), Output("pj-notice", "children"),
    Input("pj-type", "value"), Input("pj-surface", "value"), Input("pj-pieces", "value"), Input("pj-terrain", "value"),
    Input("pj-annee", "value"), Input("pj-budget", "value"), Input("pj-peu-fiables", "value"),
)
def maj_projet(type_, surface, pieces, terrain, annee, budget, peu_fiables):
    vide = (VIDE, VIDE, [], [])
    crit = _critere(surface, pieces, terrain if type_ == "Maison" else None)
    if crit is None:
        return *vide, "Indiquez une surface entre 9 et 400 m².", None
    try:
        d = core.estimer_communes(type_, crit[0], crit[1], crit[2], annee, budget)
        ev = core.evaluation_ml()
    except FileNotFoundError as e:
        return *vide, "Modèle indisponible.", dbc.Alert(str(e), color="danger")
    if not peu_fiables:
        d = d[d["fiable"]]
    if d.empty:
        return *vide, "Aucune commune pour cette sélection.", None

    n = d["statut"].value_counts()
    resume = (
        f"{type_} de {crit[0]:.0f} m², achat en {annee}, budget {euro(budget)} : "
        f"{n.get('sûr', 0)} communes sûres, {n.get('possible', 0)} possibles, {n.get('hors budget', 0)} hors budget."
    )
    notes = [
        f"Précision mesurée sur les ventes de {ev['annee_test']} (jamais vues par le modèle) : erreur médiane {ev['erreur_mediane_pct']} % "
        f"sur le prix d'une vente. La fourchette contient {ev['couverture_80_pct']} % des ventes réelles (cible 80 %).",
        "Le modèle suppose un marché stable au niveau des deux dernières années : il ne prédit ni hausse ni baisse. "
        "L'année d'achat n'élargit que la fourchette.",
    ]
    if type_ == "Maison" and crit[2] is None:
        notes.append("Terrain non précisé : c'est le 2e critère du prix d'une maison, l'estimation est moins précise.")
    notice = dbc.Alert([html.Div(t) for t in notes], color="light", className="small border py-2")

    carte = go.Figure()
    gj = core.communes_geojson()
    for statut, couleur in STATUTS.items():
        x = d[d["statut"] == statut]
        if x.empty:
            continue
        carte.add_trace(go.Choroplethmap(
            geojson=gj, locations=list(x["code_commune"]), z=[1] * len(x), name=statut, showlegend=True,
            colorscale=[[0, couleur], [1, couleur]], showscale=False, marker_opacity=0.75, marker_line_width=0.6,
            marker_line_color="white", hoverinfo="text",
            text=[
                f"<b>{r.nom_commune}</b> ({r.zone}, {r.distance_km:.0f} km d'Orléans)<br>"
                f"estimation {euro(r.prix_estime)} ({euro(r.prix_m2)}/m²)<br>fourchette à 80 % : {euro(r.prix_bas)} à {euro(r.prix_haut)}<br>"
                f"{statut} ({r.marge_pct:+.0f} % de marge) · {r.n_ventes} ventes"
                + ("" if r.fiable else "<br><i>peu fiable</i>")
                for r in x.itertuples()
            ],
        ))
    _map(carte)
    carte.update_layout(legend=dict(orientation="h", y=1.02, x=0), margin=dict(l=0, r=0, t=30, b=0))

    z = d.groupby(["zone", "statut"]).size().rename("n").reset_index()
    zones = px.bar(
        z, x="n", y="zone", color="statut", orientation="h", color_discrete_map=STATUTS, text="n",
        category_orders={"zone": ZONES[::-1], "statut": list(STATUTS)},
        labels={"n": "Communes", "zone": ""}, title="Communes par zone et par statut",
    )
    zones.update_layout(height=520, margin=dict(l=0, r=0, t=40, b=0), legend_title_text="")

    t = d.assign(
        prix=d["prix_estime"], fourchette=d.apply(lambda r: f"{euro(r.prix_bas)} à {euro(r.prix_haut)}", axis=1)
    )
    noms = {"nom_commune": "Commune", "zone": "Zone", "distance_km": "Km d'Orléans", "statut": "Statut", "prix": "Estimation (€)",
            "fourchette": "Fourchette 80 %", "prix_m2": "€/m²", "marge_pct": "Marge (%)", "n_ventes": "Ventes"}
    t = t[list(noms)].rename(columns=noms)
    return carte, zones, t.to_dict("records"), [{"name": c, "id": c} for c in t.columns], resume, notice


@app.callback(
    Output("pj-detail", "children"),
    Input("pj-commune", "value"), Input("pj-type", "value"), Input("pj-surface", "value"), Input("pj-pieces", "value"),
    Input("pj-terrain", "value"), Input("pj-annee", "value"), Input("pj-budget", "value"),
)
def maj_detail(code, type_, surface, pieces, terrain, annee, budget):
    crit = _critere(surface, pieces, terrain if type_ == "Maison" else None)
    if crit is None or not code:
        return None
    try:
        r = core.estimer(code, type_, crit[0], crit[1], crit[2], annee, budget)
    except FileNotFoundError:
        return None
    couleur = {"sûr": "success", "possible": "warning", "hors budget": "secondary"}[r["statut"]]
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(f"{r['nom_commune']} : {euro(r['prix_estime'])}", className="mb-1"),
                html.Div(f"Fourchette à 80 % : {euro(r['prix_bas'])} à {euro(r['prix_haut'])} ({euro(r['prix_m2'])}/m²)"),
                html.Div(
                    [dbc.Badge(r["statut"], color=couleur, className="me-2"),
                     f"budget {euro(budget)} : marge {r['marge_pct']:+.0f} % sur l'estimation, {r['n_ventes']} ventes de ce type dans la commune."]
                ),
                html.Ul([html.Li(a) for a in r["avertissements"]], className="small text-muted mt-2 mb-0"),
            ]
        ),
        className="border-" + couleur,
    )


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 8050)))
