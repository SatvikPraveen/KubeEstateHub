# syntax=docker/dockerfile:1.7
FROM nginxinc/nginx-unprivileged:1.31.6-alpine
ARG CODE_VERSION=dev
LABEL org.opencontainers.image.title="kubeestatehub-frontend-dashboard" \
      org.opencontainers.image.description="Static market analytics dashboard" \
      org.opencontainers.image.source="https://github.com/SatvikPraveen/KubeEstateHub" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.revision="${CODE_VERSION}"
# Pick up Alpine security fixes published after the upstream image was built (the image
# workflow gates on fixable CRITICAL/HIGH CVEs).
USER root
# hadolint ignore=DL3017
RUN apk upgrade --no-cache
COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html app.js styles.css /usr/share/nginx/html/
USER 101
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
