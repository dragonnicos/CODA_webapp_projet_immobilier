"""Point d'entrée unique : FastAPI sur /api, MCP sur /mcp, Dash sur /. Lancer : uvicorn main:app"""
import os

from a2wsgi import WSGIMiddleware
from fastapi import FastAPI

from api import router
from auth import CleAcces
from app import server as dash_server  # Flask de Dash
from mcp_server import mcp

mcp_app = mcp.http_app(path="/mcp")  # Streamable HTTP ; son lifespan doit être celui de FastAPI

app = FastAPI(
    title="Immobilier Loiret : API",
    description="Ventes DVF du Loiret 2021-2025 (DGFiP, Etalab, Licence Ouverte 2.0). Médianes, nombre de ventes toujours fournis.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=mcp_app.lifespan,
)
app.include_router(router, prefix="/api")
app.router.routes.extend(mcp_app.routes)  # expose /mcp tel quel, avant le montage de Dash
app.mount("/", WSGIMiddleware(dash_server))  # en dernier : capte tout ce qui n'est ni /api ni /mcp
app.add_middleware(CleAcces, cle=os.environ.get("ACCESS_KEY"))  # une clé pour Dash, /api et /mcp (ouvert si absente)
