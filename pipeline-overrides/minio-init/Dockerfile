# Image for the MinIO init job. The build context is kdai3/_storage/minio_setup
# (init_minio.sh + policies/). Compose bind-mounts that directory; on Container
# Apps it is baked in and runs as a manual-trigger job after each MinIO deploy.
# The mc image is ubi-micro based and has no sed, so the pipeline strips CRLF
# from init_minio.sh on the build agent before `docker build`.
FROM docker.io/pgsty/mc:RELEASE.2026-09-16T00-00-00Z

COPY . /minio_setup

ENTRYPOINT ["bash", "/minio_setup/init_minio.sh"]
