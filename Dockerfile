# --- Stage 1: Docker CLI + Compose plugin binaries ---
FROM docker:cli AS docker-stage

# --- Stage 2: pass-cli binary ---
FROM debian:stable-slim AS pass-stage
ENV PROTON_PASS_CLI_INSTALL_DIR=/usr/local/bin
RUN apt-get update && apt-get install -y curl ca-certificates jq \
    && curl -fsSL https://proton.me/download/pass-cli/install.sh | bash

# --- Stage 3: Final image ---
FROM python:3-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI + Compose plugin (static binaries only)
COPY --from=docker-stage /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-stage /usr/local/libexec/docker/cli-plugins/ /usr/local/libexec/docker/cli-plugins/

# pass-cli (glibc binary)
COPY --from=pass-stage /usr/local/bin/pass-cli /usr/local/bin/pass-cli

# Allow git operations on mounted volumes with different ownership
RUN git config --global --add safe.directory '*'

# Git credential helper: uses GIT_TOKEN env var for HTTPS auth on private repos
COPY app/git-credential-env /usr/local/bin/git-credential-env
RUN chmod +x /usr/local/bin/git-credential-env \
    && git config --global credential.helper '/usr/local/bin/git-credential-env'

ARG GIT_COMMIT=dev
ENV GIT_COMMIT=${GIT_COMMIT}

# Sensible defaults for headless pass-cli operation
ENV PROTON_PASS_KEY_PROVIDER=fs

# Pre-create pass-cli directories (will be overridden by volume mounts if present)
RUN mkdir -p /root/.local/share/proton-pass-cli \
             /root/.config/proton-pass-cli

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
