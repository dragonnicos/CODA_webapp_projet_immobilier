import os

import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, ctx, dash_table, dcc, html

import core

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
    barres = px.bar(
        secs, x="prix_m2_median", y="section", orientation="h", color="statut",
        color_discrete_map=COULEURS_STATUT, text=secs["n_ventes"].map(lambda n: f"{n} ventes"),
        labels={"prix_m2_median": "Prix médian €/m²", "section": "Section"},
        title=f"{nom} : médiane par section (cliquez sur une barre ou une zone)",
    )
    barres.update_layout(
        height=max(420, 22 * len(secs)), margin=dict(l=0, r=0, t=40, b=0), legend_title_text="",
        yaxis=dict(type="category"),
    )
    gj = core.sections_geojson(code)
    dispo = {f["id"].split("-")[1] for f in gj["features"]}
    sa = secs[secs["section"].isin(dispo)]
    ids = [f"{code}-{x}" for x in sa["section"]]
    textes = [
        f"<b>Section {r.section}</b><br>{euro(r.prix_m2_median)}/m² (médiane)<br>{r.n_ventes} ventes"
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


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 8050)))
