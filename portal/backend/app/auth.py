import hashlib
import time
from fastapi import HTTPException, Request
from . import config
from .database import connection
from .cluster import has_session


class Identity(str):
    def __new__(cls, name, token=""):
        value = super().__new__(cls, name)
        value.token = token
        return value


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request):
    if config.MODE == "preview":
        return Identity("preview")
    token = request.cookies.get("portal_session", "")
    with connection() as db:
        row = db.execute("SELECT owner FROM sessions WHERE token=? AND expires>?",
                         (token_hash(token), time.time())).fetchone()
    if not row or not has_session(token_hash(token)):
        raise HTTPException(401, "Sign in to continue")
    return Identity(row["owner"], token_hash(token))
