# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim-bookworm AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt

FROM python:${PYTHON_VERSION}-slim-bookworm
ARG CODE_VERSION=dev
LABEL org.opencontainers.image.title="kubeestatehub-listings-api" \
      org.opencontainers.image.description="Listings and market REST API" \
      org.opencontainers.image.source="https://github.com/SatvikPraveen/KubeEstateHub" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.revision="${CODE_VERSION}"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus \
    PORT=8080
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY gunicorn.conf.py ./
COPY listings_api ./listings_api
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/livez', timeout=2).status == 200 else 1)"]
# The multiprocess metrics directory must exist and be empty at start (it lives on the
# tmp emptyDir in Kubernetes, which is writable despite readOnlyRootFilesystem).
CMD ["sh", "-c", "rm -rf \"$PROMETHEUS_MULTIPROC_DIR\" && mkdir -p \"$PROMETHEUS_MULTIPROC_DIR\" && exec gunicorn listings_api.wsgi:app"]
