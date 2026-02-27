import os

DOCKER_APPS_PATH = os.getenv("DOCKER_APPS_PATH", "/data/docker-apps")
MGMT_SCRIPT = os.getenv("MGMT_SCRIPT", f"{DOCKER_APPS_PATH}/mgmt.sh")
PASS_VAULT = os.getenv("PASS_VAULT", "docker-secrets")
SELF_STACK_NAME = "stack-manager"
