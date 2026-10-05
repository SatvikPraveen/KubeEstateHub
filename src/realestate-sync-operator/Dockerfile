# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim-trixie AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
# pip is only needed to build the venv; drop it so the runtime image carries no installer
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt \
 && /opt/venv/bin/pip uninstall -y pip

FROM python:${PYTHON_VERSION}-slim-trixie
ARG CODE_VERSION=dev
LABEL org.opencontainers.image.title="kubeestatehub-realestate-sync-operator" \
      org.opencontainers.image.description="Kubernetes operator reconciling RealEstateSync resources into CronJobs" \
      org.opencontainers.image.source="https://github.com/SatvikPraveen/KubeEstateHub" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.revision="${CODE_VERSION}"
# PYTHONPATH: the kopf console script does not put the working directory on sys.path
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:${PATH}" PYTHONPATH=/app
# Pick up Debian security fixes published after the upstream image was built, and remove
# the base image's pip (unused at runtime).
# hadolint ignore=DL3005
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip uninstall -y pip
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY realestate_sync_operator ./realestate_sync_operator
USER 10001:10001
EXPOSE 8081
ENTRYPOINT ["kopf", "run", "-m", "realestate_sync_operator.handlers", "--liveness=http://0.0.0.0:8081/healthz"]
CMD ["--all-namespaces"]
