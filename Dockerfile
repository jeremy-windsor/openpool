FROM python:3.13-slim@sha256:eb43ff125d8d58d7449dcba7d336c23bcac412f526d861db493b9994d8010280 AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.26@sha256:9a23023be68b2ed09750ae636228e903a54a05ea56ed03a934d00fe9fbeded4b \
    /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY openpool ./openpool

RUN uv sync --locked --no-dev --extra postgres --no-editable


FROM python:3.13-slim@sha256:eb43ff125d8d58d7449dcba7d336c23bcac412f526d861db493b9994d8010280

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENPOOL_DB=/data/openpool.sqlite \
    OPENPOOL_HOST=0.0.0.0 \
    OPENPOOL_PORT=5280 \
    PATH=/app/.venv/bin:$PATH

ARG OPENPOOL_BUILD_SHA=unknown
ARG OPENPOOL_BUILD_REF=unknown

ENV OPENPOOL_BUILD_SHA=${OPENPOOL_BUILD_SHA} \
    OPENPOOL_BUILD_REF=${OPENPOOL_BUILD_REF}

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

RUN adduser --disabled-password --gecos "" --home /nonexistent openpool \
    && mkdir -p /data \
    && chown -R openpool:openpool /data

USER openpool

EXPOSE 5280

CMD ["uvicorn", "openpool.main:app", "--host", "0.0.0.0", "--port", "5280"]
