import os
import re
import shutil
import subprocess

DOCKER_APPS_PATH = os.getenv("DOCKER_APPS_PATH", "/data/docker-apps")
SELF_STACK_NAME = "stack-manager"
GIT_COMMIT = os.getenv("GIT_COMMIT", "dev")[:7]

# Regex for validating stack/service/container names (no path traversal)
SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")

# Auto-detect docker compose command
if shutil.which("docker") and subprocess.run(
    ["docker", "compose", "version"], capture_output=True
).returncode == 0:
    COMPOSE_CMD = ["docker", "compose"]
else:
    COMPOSE_CMD = ["docker-compose"]
