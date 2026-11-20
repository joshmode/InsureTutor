FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    KNOWLEDGE_BASE_DIR=/app/knowledge \
    DATA_DIR=/app/data \
    EMBEDDING_CACHE_DIR=/app/data/model-cache

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY knowledge/ /app/knowledge/
COPY --from=frontend-builder /build/frontend/out /app/frontend/out

RUN mkdir -p /app/data && chown -R app:app /app/data /app/frontend

USER app
EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

