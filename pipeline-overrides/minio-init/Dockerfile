# MinIO init job image. Build context = kdai3/_storage/minio_setup (from the
# kdai3 checkout), which holds init_minio.sh + policies/. The compose file
# bind-mounts that dir; on Container Apps we bake it into an image and run it
# as a manual-trigger Container Apps Job after each MinIO deploy.
FROM minio/mc:RELEASE.2025-08-13T08-35-41Z

COPY . /minio_setup

# Guard against CRLF line endings (the kdai3 README calls this out for Windows
# checkouts; the build agent should be LF, but normalizing is free).
RUN sed -i 's/\r$//' /minio_setup/init_minio.sh

ENTRYPOINT ["bash", "/minio_setup/init_minio.sh"]
