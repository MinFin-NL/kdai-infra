# nginx front door for Azure Container Apps. Same as kdai3/backend/Dockerfile.nginx,
# except the upstreams come from env vars via the stock envsubst entrypoint:
#   BACKEND_FASTCGI    ca-kdai-backend-inno-d:9000 (TCP ingress, short name)
#   REVERB_UPSTREAM    https://ca-kdai-reverb-inno-d.internal.<domain>
#   FRONTEND_UPSTREAM  https://ca-kdai-frontend-inno-d.internal.<domain>
#
# Pinned to the 2026-08-17 version while debugging the /api/ 502s. Pinning nginx
# and PHP didn't fix them; the TCP ingress did (see keep-conn in
# default.conf.template). Can go back to nginx:alpine once keep-conn is confirmed.
FROM nginx:1.31.3-alpine

COPY nginx-main.conf /etc/nginx/nginx.conf
COPY default.conf.template /etc/nginx/templates/default.conf.template

RUN mkdir -p /var/cache/nginx && \
    chown -R nginx:nginx /var/cache/nginx

EXPOSE 80
