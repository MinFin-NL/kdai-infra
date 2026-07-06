FROM python:3.12-slim

# Azure Speech SDK runtime deps on Debian: OpenSSL 3, ALSA stubs, CA certs.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates libssl3 libasound2 wget && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 9090

CMD ["python", "server.py"]
