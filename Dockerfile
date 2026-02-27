# --- Stage 1: Docker CLI + Compose plugin binaries ---
FROM docker:27-cli AS docker-stage

# --- Stage 2: pass-cli binary ---
FROM debian:bookworm AS pass-stage
RUN apt-get update && apt-get install -y curl ca-certificates jq \
    && curl -fsSL https://proton.me/download/pass-cli/install.sh | bash

# --- Stage 3: Final image ---
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI + Compose plugin (static binaries only, no apt deps)
COPY --from=docker-stage /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-stage /usr/local/libexec/docker/cli-plugins/ /usr/local/libexec/docker/cli-plugins/

# pass-cli (static binary)
COPY --from=pass-stage /usr/local/bin/pass-cli /usr/local/bin/pass-cli

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
