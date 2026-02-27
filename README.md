<div align="center">

# Stack Manager

[![Build](https://img.shields.io/github/actions/workflow/status/traktuner/stack-manager/build.yml?branch=master&style=flat-square&logo=github)](https://github.com/traktuner/stack-manager/actions)
[![License](https://img.shields.io/github/license/traktuner/stack-manager?style=flat-square)](LICENSE)
[![Docker](https://img.shields.io/badge/ghcr.io-traktuner%2Fstack--manager-blue?style=flat-square&logo=docker)](https://ghcr.io/traktuner/stack-manager)
[![Python](https://img.shields.io/badge/python-3.12-blue?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Proton Pass](https://img.shields.io/badge/Proton%20Pass-6D4AFF?style=flat-square&logo=proton&logoColor=white)](https://proton.me/pass)

**A lightweight web UI for managing Docker Compose stacks with built-in Proton Pass secret injection.**

<br>

*Dark-mode dashboard &bull; Real-time streaming output &bull; Mobile-friendly &bull; Self-contained container*

</div>

---

## Features

- **Start / Stop / Upgrade** Docker Compose stacks from a clean dark-mode web interface
- **Proton Pass integration** — secrets from `.env.template` files are resolved via `pass-cli` at container start
- **Live command output** — real-time streaming via Server-Sent Events in a modal overlay
- **Bulk operations** — upgrade all, pull all images, cleanup unused resources
- **Git-based config updates** — pull latest stack definitions with one click
- **Mobile-friendly** — responsive design that works on phones, tablets, and large monitors
- **Zero external scripts** — all management logic runs inside the container

## How It Works

Stack Manager scans a directory of Docker Compose projects (stacks). Each stack is a folder containing a `docker-compose.yml` file. Stacks are displayed with their container status and can be controlled through the web UI.

### Secret Management Modes

| File Present | Mode | Behavior |
|---|---|---|
| `.env.template` | **Proton Pass** | Secrets referenced as `pass://vault/item/field` are injected at start via `pass-cli` |
| `.env` | Standard | Docker Compose reads the `.env` file directly |
| Neither | No env | Stack starts without environment configuration |

### Stack Directory Structure

```
/data/docker-apps/
├── traefik/
│   ├── docker-compose.yml
│   └── .env.template          # → Proton Pass mode
├── gitea/
│   ├── docker-compose.yml
│   └── .env                   # → Standard mode
└── whoami/
    └── docker-compose.yml     # → No env mode
```

## Deployment

```yaml
services:
  stack-manager:
    image: ghcr.io/traktuner/stack-manager:latest
    container_name: stack-manager
    restart: unless-stopped
    ports:
      - "8099:8000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /data/docker-apps:/data/docker-apps
      - pass-cli-data:/root/.local/share
    environment:
      - DOCKER_APPS_PATH=/data/docker-apps
      - PASS_VAULT=docker-secrets
      - PROTON_PASS_KEY_PROVIDER=fs

volumes:
  pass-cli-data:
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DOCKER_APPS_PATH` | `/data/docker-apps` | Directory containing your Docker Compose stacks |
| `PASS_VAULT` | `docker-secrets` | Proton Pass vault name for secret lookups |
| `PROTON_PASS_KEY_PROVIDER` | — | Set to `fs` for headless pass-cli usage |

### Volumes

| Mount | Required | Description |
|---|---|---|
| `/var/run/docker.sock` | Yes | Docker socket for container management |
| `DOCKER_APPS_PATH` | Yes | Your stack definitions directory |
| `pass-cli-data` | No | Persistent Proton Pass session (survives container restarts) |

## Proton Pass Setup

1. Open the Stack Manager web UI
2. The header shows **Proton Pass: inactive** with a **Login** button
3. Click Login and enter your Proton email
4. Follow the authentication URL shown in the output
5. Once authenticated, stacks with `.env.template` can be started with secret injection

### `.env.template` Format

```env
# Plain values are passed through as-is
APP_NAME=my-app
APP_PORT=8080

# Secrets are resolved from Proton Pass at start time
DB_PASSWORD=pass://docker-secrets/my-app/database-password
API_KEY=pass://docker-secrets/my-app/api-key
```

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web UI |
| `GET` | `/health` | Health check |
| `GET` | `/api/stacks` | Stack list (HTML) |
| `GET` | `/api/status` | Status JSON (pass-cli, stack counts) |
| `POST` | `/api/stacks/{name}/start` | Start a stack |
| `POST` | `/api/stacks/{name}/stop` | Stop a stack |
| `POST` | `/api/stacks/upgrade` | Upgrade all active stacks |
| `POST` | `/api/stacks/pull` | Pull images for active stacks |
| `POST` | `/api/update` | Git pull stack definitions |
| `POST` | `/api/cleanup` | Docker system prune |
| `POST` | `/api/pass/login` | Proton Pass CLI login |
| `GET` | `/api/stream/{id}` | SSE command output stream |

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Uvicorn
- **Frontend:** Pico CSS, HTMX, vanilla JavaScript
- **Container:** Docker CLI, Docker Compose plugin, pass-cli, git

---

> **Disclaimer:** This project was vibe-coded with [Claude Code](https://claude.ai/claude-code) by Anthropic. The entire codebase — backend, frontend, CI/CD, and this README — was generated through conversational AI pair programming.
