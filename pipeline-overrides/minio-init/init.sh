#!/bin/sh
# Create the "debates" bucket in MinIO. Idempotent (--ignore-existing), so it is safe to run
# on every deploy. Uses `mc alias set` (credentials passed as separate args, so no URL-encoding
# concerns) against MinIO's internal ingress endpoint.
set -eu
mc alias set kdai "$MINIO_URL" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing kdai/debates
echo "MinIO buckets:"
mc ls kdai
