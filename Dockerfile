FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MALLOC_ARENA_MAX=2

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py api.py auth.py main.py mcp_server.py ./
COPY core/ core/
COPY assets/ assets/
COPY data/ data/

# Render fournit $PORT ; 8050 par défaut en local.
# uvicorn sert FastAPI (/api), le MCP (/mcp) et Dash (/, monté en WSGI).
# 1 seul processus : les données (parquet + contours) sont chargées une fois, mémoire limitée sur l'offre gratuite.
EXPOSE 8050
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8050}
