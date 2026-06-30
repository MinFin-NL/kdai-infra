#!/bin/sh
# Ensure the "debates" bucket exists in MinIO. Runs as a lightweight always-on Container App
# (not a Job — Microsoft.App/jobs may be restricted in this environment). Re-ensures hourly so
# the bucket is recreated if MinIO restarts (MinIO's /data is currently ephemeral — no volume).
# Idempotent via `mc mb --ignore-existing`. Credentials are passed to `mc alias set` as separate
# args (no URL-encoding concerns).
echo "[minio-init] starting; target=$MINIO_URL"
while true; do
  if mc alias set kdai "$MINIO_URL" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; then
    if mc mb --ignore-existing kdai/debates >/dev/null 2>&1; then
      echo "[minio-init] debates bucket ensured at $(date -u +%H:%M:%S)"
    else
      echo "[minio-init] WARN could not create/verify bucket"
    fi
  else
    echo "[minio-init] WARN could not reach MinIO yet; will retry"
  fi
  sleep 3600
done
