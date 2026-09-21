# KDAI front door for Azure Container Apps.
# Mirrors kdai3/backend/Dockerfile.nginx, but the upstream hosts are env vars
# (envsubst template, processed by the stock nginx entrypoint at startup):
#   BACKEND_FASTCGI   e.g. ca-kdai-backend-inno-d:9000   (TCP ingress, short name)
#   REVERB_UPSTREAM   e.g. https://ca-kdai-reverb-inno-d.internal.<domain>
#   FRONTEND_UPSTREAM e.g. https://ca-kdai-frontend-inno-d.internal.<domain>
#
# Temporarily pinned to the 2026-08-17 known-good version while the /api/ 502 was
# diagnosed. Pinning nginx (1.31.3) and PHP (8.4.24) did NOT fix it; the cause is
# the Container Apps TCP ingress (see the keep-conn note in default.conf.template).
# Once keep-conn is confirmed working, this can go back to the floating nginx:alpine.
FROM nginx:1.31.3-alpine

COPY nginx-main.conf /etc/nginx/nginx.conf
COPY default.conf.template /etc/nginx/templates/default.conf.template

RUN mkdir -p /var/cache/nginx && \
    chown -R nginx:nginx /var/cache/nginx

EXPOSE 80
