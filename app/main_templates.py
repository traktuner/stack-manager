"""Shared Jinja2Templates instance used by main.py and routers."""
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import GIT_COMMIT

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.globals["git_commit"] = GIT_COMMIT
