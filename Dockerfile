FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENPOOL_DB=/data/openpool.sqlite \
    OPENPOOL_HOST=0.0.0.0 \
    OPENPOOL_PORT=5280

ARG OPENPOOL_BUILD_SHA=unknown
ARG OPENPOOL_BUILD_REF=unknown

ENV OPENPOOL_BUILD_SHA=${OPENPOOL_BUILD_SHA} \
    OPENPOOL_BUILD_REF=${OPENPOOL_BUILD_REF}

WORKDIR /app

COPY pyproject.toml README.md ./
COPY openpool ./openpool

RUN pip install --no-cache-dir '.[postgres]' \
    && adduser --disabled-password --gecos "" --home /nonexistent openpool \
    && mkdir -p /data \
    && chown -R openpool:openpool /data

USER openpool

EXPOSE 5280

CMD ["uvicorn", "openpool.main:app", "--host", "0.0.0.0", "--port", "5280"]
