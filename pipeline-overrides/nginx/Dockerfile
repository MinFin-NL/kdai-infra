# KDAI front door for Azure Container Apps.
# Mirrors kdai3/backend/Dockerfile.nginx, but the upstream hosts are env vars
# (envsubst template, processed by the stock nginx entrypoint at startup):
#   BACKEND_FASTCGI   e.g. ca-kdai-backend-inno-d:9000   (TCP ingress, short name)
#   REVERB_UPSTREAM   e.g. https://ca-kdai-reverb-inno-d.internal.<domain>
#   FRONTEND_UPSTREAM e.g. https://ca-kdai-frontend-inno-d.internal.<domain>
#
# Pinned to the last known-good version. The 2026-09-16 rebuild pulled nginx:alpine
# 1.31.6 (and php 8.4.25), after which every /api/ call 502'd with "Connection reset
# by peer" on the fastcgi hop, while php-fpm logged each request as completed (200).
# Rolling PHP back to 8.4.24 alone did not help, so nginx is the next suspect.
FROM nginx:1.31.3-alpine

COPY nginx-main.conf /etc/nginx/nginx.conf
COPY default.conf.template /etc/nginx/templates/default.conf.template

RUN mkdir -p /var/cache/nginx && \
    chown -R nginx:nginx /var/cache/nginx

EXPOSE 80
