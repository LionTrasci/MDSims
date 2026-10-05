from contextlib import asynccontextmanager
import asyncio
from pathlib import Path
import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .database import initialize
from .routes import router
from . import config
from .cluster import prune_sessions, close_all_sessions


@asynccontextmanager
async def lifespan(app):
    initialize()
    async def cleanup():
        while True:
            await asyncio.sleep(60)
            await asyncio.to_thread(prune_sessions)
    task = asyncio.create_task(cleanup())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await asyncio.to_thread(close_all_sessions)


app = FastAPI(title="BP1 · Molecular dynamics", lifespan=lifespan)


@app.middleware("http")
async def security(request: Request, call_next):
    allowed = config.configuration().get("allowed_hosts", ["127.0.0.1", "localhost", "::1"])
    if request.url.hostname not in allowed:
        return JSONResponse({"detail": "Host is not allowed"}, status_code=400)
    # Cross-origin forms cannot set this header; no CORS permissions are exposed.
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("X-Portal-Request") != "1":
        return JSONResponse({"detail": "Missing request header"}, status_code=403)
    try:
        response = await call_next(request)
    except Exception:
        logging.exception("Portal request failed")
        return JSONResponse({"detail": "BP1 connection or server error. Contact the portal administrator."}, status_code=502)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
    return response


app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


static = Path(os.environ.get("PORTAL_STATIC", "../frontend/dist"))
if static.is_dir():
    app.mount("/", StaticFiles(directory=static, html=True), name="frontend")
