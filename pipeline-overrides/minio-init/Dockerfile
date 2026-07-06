# MinIO init job image. Build context = kdai3/_storage/minio_setup (from the
# kdai3 checkout), which holds init_minio.sh + policies/. The compose file
# bind-mounts that dir; on Container Apps we bake it into an image and run it
# as a manual-trigger Container Apps Job after each MinIO deploy.
# NOTE: the mc image is ubi-micro based — no sed/coreutils, so CRLF
# normalization of init_minio.sh happens on the build agent (pipeline step)
# before `docker build`, not in here.
FROM minio/mc:RELEASE.2025-08-13T08-35-41Z

COPY . /minio_setup

ENTRYPOINT ["bash", "/minio_setup/init_minio.sh"]
