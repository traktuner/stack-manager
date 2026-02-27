import os
import shutil

DOCKER_APPS_PATH = os.getenv("DOCKER_APPS_PATH", "/data/docker-apps")
PASS_VAULT = os.getenv("PASS_VAULT", "docker-secrets")
SELF_STACK_NAME = "stack-manager"
GIT_COMMIT = os.getenv("GIT_COMMIT", "dev")[:7]

# Auto-detect docker compose command
if shutil.which("docker") and os.system("docker compose version >/dev/null 2>&1") == 0:
    COMPOSE_CMD = ["docker", "compose"]
else:
    COMPOSE_CMD = ["docker-compose"]
