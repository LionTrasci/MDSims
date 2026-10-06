"""Server-owned connection settings; never supplied by a browser."""
import json
import os
import re
from pathlib import Path

DATA = Path(os.environ.get("PORTAL_DATA", "data"))
CONFIG_PATH = Path(os.environ.get("PORTAL_CONFIG", "config.json"))
MODE = os.environ.get("PORTAL_MODE", "preview")
if MODE not in {"preview", "live"}:
    raise RuntimeError("PORTAL_MODE must be preview or live")


def configuration():
    if MODE == "preview":
        return {"host": "bp1-login03.acrc.bris.ac.uk", "profiles": {
            "preview": {"username": "preview", "root": "/user/work/preview",
                        "accounts": [], "partitions": ["short", "compute"],
                        "environment": "",
                        "max_cpus": 32, "max_memory_gb": 128, "max_hours": 48}}}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def profile(username):
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", username):
        raise ValueError("Invalid BP1 username")
    cfg = configuration()
    if username in cfg.get("profiles", {}):
        return cfg["profiles"][username]
    defaults = dict(cfg["defaults"])
    defaults["username"] = username
    defaults["root"] = defaults["root"].replace("{username}", username)
    return defaults
