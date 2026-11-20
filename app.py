import os

from dash import Dash, html

app = Dash(__name__)
server = app.server  # Flask, pour gunicorn : gunicorn app:server

app.layout = html.Div([html.H1("Immobilier Orléans / Loiret")])

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 8050)))
