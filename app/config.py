import os
import re
import shutil

DOCKER_APPS_PATH = os.getenv("DOCKER_APPS_PATH", "/data/docker-apps")
if not os.path.isdir(DOCKER_APPS_PATH):
    raise SystemExit(
        f"DOCKER_APPS_PATH={DOCKER_APPS_PATH!r} does not exist or is not a directory. "
        "Mount your stacks directory and set DOCKER_APPS_PATH accordingly."
    )
SELF_STACK_NAME = "stack-manager"
GIT_COMMIT = os.getenv("GIT_COMMIT", "dev")[:7]

# Regex for validating stack/service/container names (no path traversal)
SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")

# Auto-detect docker compose command
if shutil.which("docker") and os.system("docker compose version >/dev/null 2>&1") == 0:
    COMPOSE_CMD = ["docker", "compose"]
else:
    COMPOSE_CMD = ["docker-compose"]
