# One-shot MinIO initialiser: creates the "debates" bucket the backend + ATTS services use.
# (The full docker-compose minio-init also provisions per-service users/policies; for this
# inno-d environment every service authenticates with the MinIO root creds, so we only need
# the bucket.) Built from minio/mc so `mc` is available; init.sh runs as the entrypoint.
FROM minio/mc
COPY init.sh /init.sh
ENTRYPOINT ["sh", "/init.sh"]
