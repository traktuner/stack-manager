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

*Dark-mode dashboard &bull; Real-time streaming output &bull; Container logs &bull; Per-service upgrades &bull; Private repo support &bull; Mobile-friendly*

</div>

---

## Features

- **Start / Stop / Upgrade** Docker Compose stacks from a clean dark-mode web interface
- **Per-service upgrades** — update individual containers within a stack (pull + recreate)
- **Container logs** — view live logs for any container directly in the UI
- **Proton Pass integration** — secrets from `.env.template` files are resolved via `pass-cli` at container start
- **Live command output** — real-time streaming via Server-Sent Events in a modal overlay
- **Bulk operations** — upgrade all, pull all images, cleanup unused resources
- **Git-based config updates** — pull latest stack definitions with one click (supports private repos)
- **Private GitHub repos** — authenticate with a GitHub Personal Access Token via `GIT_TOKEN`
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

### Docker Images

Images are published to GitHub Container Registry and built for **linux/amd64** and **linux/arm64**.

```
ghcr.io/traktuner/stack-manager
```

| Tag | Example | Description |
|---|---|---|
| `latest` | `:latest` | Built monthly from `master` — a recent snapshot, but not tied to a specific release |
| `vX.Y.Z` | `:v1.0.0` | Pinned release — recommended for production, won't change after publish |
| `vX.Y` | `:v1.0` | Tracks the latest patch within a minor version (e.g. `v1.0` → `v1.0.2`) |
| `vX` | `:v1` | Tracks the latest minor+patch within a major version |
| `sha-<hash>` | `:sha-269ffd2` | Built on every commit — pinned to a specific revision, useful for debugging or rollback |

> **Recommendation:** Use a versioned tag (`:v1.0.0` or `:v1`) for stable deployments. Use `:latest` if you always want the newest build and are comfortable with potential breaking changes.

### Compose Example

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
      - /path/to/your/stacks:/data/docker-apps
      - pass-cli-data:/root/.local/share        # for Proton Pass session persistence
    environment:
      - DOCKER_APPS_PATH=/data/docker-apps
      - PROTON_PASS_KEY_PROVIDER=fs              # required for Docker
      - XDG_CONFIG_HOME=/root/.local/share/config
      - GIT_TOKEN=ghp_your_github_token          # for private repos (optional)

volumes:
  pass-cli-data:
```

> **Without Proton Pass?** If you don't use Proton Pass, you can omit `PROTON_PASS_KEY_PROVIDER`, `XDG_CONFIG_HOME`, and the `pass-cli-data` volume. Stacks will use `.env` files or run without environment configuration.

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DOCKER_APPS_PATH` | Yes | `/data/docker-apps` | Directory containing your Docker Compose stacks (must be mounted) |
| `PROTON_PASS_KEY_PROVIDER` | No | `keyring` | How pass-cli stores encryption keys (see below). Only needed for Proton Pass integration |
| `XDG_CONFIG_HOME` | No | — | Set to `/root/.local/share/config` when using pass-cli with a volume. Only needed for Proton Pass integration |
| `GIT_TOKEN` | No | — | GitHub Personal Access Token for pulling private repos (see below) |

> **Minimal setup:** Only `DOCKER_APPS_PATH` (mounted volume) and the Docker socket are required. All other variables are optional and only needed for Proton Pass or private repo support.

#### `PROTON_PASS_KEY_PROVIDER`

Controls how `pass-cli` stores its encryption keys. Available options:

| Value | Description | Use case |
|---|---|---|
| `keyring` | Uses the system keyring / Secret Service API (D-Bus) | Desktop Linux with a keyring daemon |
| `fs` | Stores keys on the filesystem | **Docker containers** and headless servers |
| *(env var)* | Derives key from the `PROTON_PASS_ENCRYPTION_KEY` environment variable | CI/CD pipelines, ephemeral environments |

For Docker deployments, use `fs` — containers don't have a system keyring.

When using the environment variable approach, set `PROTON_PASS_KEY_PROVIDER` to the name of another environment variable (e.g. `PROTON_PASS_ENCRYPTION_KEY`) that contains the encryption key.

#### `XDG_CONFIG_HOME`

When running in a container with `pass-cli`, the CLI writes both session data and config/encryption keys to separate directories (`~/.local/share` and `~/.config`). Setting `XDG_CONFIG_HOME=/root/.local/share/config` redirects config writes under the same volume mount, so a single named volume keeps everything persistent.

#### `GIT_TOKEN`

A GitHub Personal Access Token (classic or fine-grained) for authenticating git operations on private repositories. When set, the built-in credential helper automatically provides this token for HTTPS git requests to github.com.

If your stack definitions repo is private, set this variable so the **Update** button can pull the latest changes. The token is used with the `x-access-token` username, which is GitHub's universal method for PAT-based HTTPS authentication.

> **Note:** The container transparently rewrites SSH remote URLs to HTTPS during git pull — it does **not** modify your `.git/config`. This means your server can continue using SSH locally while the container uses HTTPS with the token.

### Volumes

| Mount | Required | Description |
|---|---|---|
| `/var/run/docker.sock` | Yes | Docker socket for container management |
| `DOCKER_APPS_PATH` | Yes | Your stack definitions directory |
| `pass-cli-data` | For Proton Pass | Persistent Proton Pass session and encryption keys (survives container restarts) |

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
DB_PASSWORD=pass://your-vault-name/my-app/database-password
API_KEY=pass://your-vault-name/my-app/api-key
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
| `POST` | `/api/stacks/{name}/upgrade` | Upgrade a single stack (pull + recreate) |
| `POST` | `/api/stacks/{stack}/services/{service}/upgrade` | Upgrade a single service |
| `POST` | `/api/stacks/upgrade` | Upgrade all active stacks |
| `POST` | `/api/stacks/pull` | Pull images for active stacks |
| `POST` | `/api/update` | Git pull stack definitions |
| `POST` | `/api/cleanup` | Docker system prune |
| `POST` | `/api/pass/login` | Proton Pass CLI login |
| `GET` | `/api/containers/{name}/logs` | Container logs (JSON, `?lines=N`) |
| `GET` | `/api/stream/{id}` | SSE command output stream |

## Security

Stack Manager is designed to run on **trusted internal networks** behind a reverse proxy with authentication (e.g., Traefik + Authelia, Nginx + OAuth2 Proxy).

### Important considerations

- **No built-in authentication** — the app does not implement its own auth layer. Protect it with your reverse proxy or VPN. Do not expose it directly to the internet.
- **Docker socket access** — required for container management. The app needs read/write access to `/var/run/docker.sock`. This grants full Docker API control, so treat the container as privileged.
- **Runs as root** — necessary to access the Docker socket and mounted volumes with varying ownership. Consider running behind a restricted network segment.
- **Input validation** — all stack/service/container names are validated against a strict allowlist (`^[a-zA-Z0-9][a-zA-Z0-9_.-]*$`). Path traversal and command injection are prevented by design.
- **No shell execution** — all subprocess calls use exec-style argument lists, never `shell=True`.
- **Template escaping** — Jinja2 autoescape is enabled globally. User-facing output is HTML-escaped.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Uvicorn
- **Frontend:** Pico CSS, HTMX + Idiomorph, vanilla JavaScript
- **Container:** Docker CLI, Docker Compose plugin, pass-cli, git

---

> **Disclaimer:** This project was vibe-coded with [Claude Code](https://claude.ai/claude-code) by Anthropic. The entire codebase — backend, frontend, CI/CD, and this README — was generated through conversational AI pair programming.
