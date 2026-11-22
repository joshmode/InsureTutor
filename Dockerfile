FROM node:22-alpine@sha256:1314fb30ec37592d5845e5a160d522c0e680972aa534549940b8d73bde88481a AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
# Optional organizational/proxy trust, mounted only during package download.
# Omit the secret on networks using the image's ordinary trust roots.
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; \
    npm ci --strict-ssl=true
COPY frontend/ ./
RUN NEXT_TELEMETRY_DISABLED=1 npm run build

FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    KNOWLEDGE_BASE_DIR=/app/knowledge \
    DATA_DIR=/app/data \
    EMBEDDING_CACHE_DIR=/app/data/model-cache \
    EMBEDDING_LOCAL_MODEL_DIR=/app/models/pinned

WORKDIR /app

# Pin the published Debian security fixes without floating the entire OS package
# graph. HTTPS and Debian's package signatures remain required. The optional CA
# secret supports the same organizational trust route as pip/npm.
RUN --mount=type=secret,id=build_ca,mode=0444 \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && if [ -f /run/secrets/build_ca ]; then set -- -o Acquire::https::CaInfo=/run/secrets/build_ca; else set --; fi \
    && apt-get "$@" update \
    && apt-get "$@" install -y --no-install-recommends \
        zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
        libc6=2.41-12+deb13u5 libc-bin=2.41-12+deb13u5 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    pip install --no-cache-dir --require-hashes --only-binary=:all: -r /app/backend/requirements.txt \
    && python -m pip uninstall --yes pip \
    && rm -rf /usr/local/lib/python3.13/ensurepip

# Runtime has no package installer or its vendored dependencies. Native runtime
# imports must still work before preparing the pinned local model.
RUN python -c "import importlib.util; import fastapi, uvicorn, pymupdf, fastembed, numpy, sqlite3; assert importlib.util.find_spec('pip') is None; assert importlib.util.find_spec('ensurepip') is None"

COPY backend/ /app/backend/
ARG EMBEDDING_MODEL_REVISION=faf4aa4225822f3bc6376869cb1164e8e3feedd0
# Download once during build, reuse only a hash-verified cache, and copy the
# model outside the data volume so a fresh volume cannot hide it at startup.
RUN --mount=type=cache,id=insuretutor-embedding-v2-${EMBEDDING_MODEL_REVISION},target=/opt/embedding-build-cache,sharing=locked \
    --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca REQUESTS_CA_BUNDLE=/run/secrets/build_ca; fi; \
    EMBEDDING_CACHE_DIR=/opt/embedding-build-cache EMBEDDING_LOCAL_MODEL_DIR=/opt/embedding-build-cache/pinned \
    python -m backend.app.scripts.download_embedding_model --revision "$EMBEDDING_MODEL_REVISION" \
    && mkdir -p /app/models \
    && cp -a /opt/embedding-build-cache/pinned /app/models/pinned
COPY knowledge/ /app/knowledge/
COPY --from=frontend-builder /build/frontend/out /app/frontend/out

# Private checkouts can have owner-only modes. COPY preserves those modes,
# but the runtime runs as a different, unprivileged user.
RUN chmod -R a+rX /app/backend /app/knowledge /app/frontend /app/models \
    && mkdir -p /app/data \
    && chown -R app:app /app/data

USER app
EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]

