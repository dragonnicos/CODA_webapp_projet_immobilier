FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .
COPY core/ core/
COPY assets/ assets/
COPY data/ data/

# Render fournit $PORT ; 8050 par défaut en local.
# 1 worker : les données (parquet + contours) sont chargées une fois, mémoire limitée sur l'offre gratuite.
EXPOSE 8050
CMD gunicorn app:server --bind 0.0.0.0:${PORT:-8050} --workers 1 --threads 4 --timeout 120
