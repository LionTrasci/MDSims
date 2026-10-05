import json
import secrets
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from . import config
from .auth import current_user, token_hash
from .database import connection, owned_job, update_job
from .models import Login, Simulation
from .scripts import render
from .cluster import Cluster, connect, add_session, close_session

router = APIRouter(prefix="/api")
_attempts = {}


@router.post("/login")
def login(body: Login, request: Request, response: Response):
    if config.MODE != "live":
        raise HTTPException(409, "Preview mode does not require a BP1 login")
    key = request.client.host
    now = time.time()
    attempts = [t for t in _attempts.get(key, []) if t > now - 300]
    if len(attempts) >= 10:
        raise HTTPException(429, "Too many sign-in attempts; try again in five minutes")
    _attempts[key] = attempts + [now]
    try:
        client = connect(config.profile(body.username), body.password)
    except Exception as exc:
        raise HTTPException(401, "BP1 sign-in failed. Check your credentials, server connectivity and configured host keys. Interactive MFA is not supported by this login yet.") from exc
    token = secrets.token_urlsafe(32)
    close_session(token_hash(request.cookies.get("portal_session", "")))
    add_session(token_hash(token), client)
    _attempts.pop(key, None)
    with connection() as db:
        db.execute("DELETE FROM sessions WHERE expires<?", (now,))
        db.execute("INSERT INTO sessions VALUES (?,?,?)", (token_hash(token), body.username, now + 28800))
    response.set_cookie("portal_session", token, httponly=True, secure=config.configuration().get("https", False), samesite="strict", max_age=28800)
    return {"username": body.username}


@router.post("/logout")
def logout(request: Request, response: Response):
    close_session(token_hash(request.cookies.get("portal_session", "")))
    with connection() as db:
        db.execute("DELETE FROM sessions WHERE token=?", (token_hash(request.cookies.get("portal_session", "")),))
    response.delete_cookie("portal_session")
    return {"ok": True}


@router.get("/me")
def me(user=Depends(current_user)):
    p = config.profile(user)
    return {"username": user, "mode": config.MODE, "bp1_user": p["username"],
            "root": p["root"], "accounts": p["accounts"], "partitions": p["partitions"],
            "max_cpus": p["max_cpus"], "max_memory_gb": p["max_memory_gb"], "max_hours": p["max_hours"]}


@router.get("/jobs")
def jobs(user=Depends(current_user)):
    with connection() as db:
        rows = db.execute("SELECT * FROM jobs WHERE owner=? ORDER BY created DESC LIMIT 100", (user,)).fetchall()
    return [dict(row) for row in rows]


@router.post("/reviews")
def review(body: Simulation, user=Depends(current_user)):
    p = config.profile(user)
    job_id = uuid.uuid4().hex
    directory = (body.run_parent or p["root"]).rstrip("/") + "/mdportal-" + job_id
    try:
        script = render(body, p, directory)
        if config.MODE == "live":
            with Cluster(p, user) as cluster:
                cluster.validate(body)
    except (ValueError, OSError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    with connection() as db:
        db.execute("INSERT INTO jobs (id,owner,created,name,settings,script,directory,state) VALUES (?,?,?,?,?,?,?,?)",
                   (job_id, user, time.time(), body.name, body.model_dump_json(), script, directory, "REVIEWED"))
    return owned_job(job_id, user)


def get_job(job_id, user):
    job = owned_job(job_id, user)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


def require_live():
    if config.MODE != "live":
        raise HTTPException(409, "Preview mode: no BP1 jobs can be submitted or cancelled")


@router.post("/jobs/{job_id}/submit")
def submit(job_id: str, user=Depends(current_user)):
    require_live()
    job = get_job(job_id, user)
    if time.time() - job["created"] > 1800:
        raise HTTPException(409, "Review expired. Review the settings again")
    p = config.profile(user)
    spec = Simulation.model_validate_json(job["settings"])
    # Reject changes to server-owned environment or limits after review.
    try:
        if render(spec, p, job["directory"]) != job["script"]:
            raise ValueError("Server configuration changed; review again")
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    with connection() as db:
        changed = db.execute("UPDATE jobs SET state='SUBMITTING' WHERE id=? AND owner=? AND state='REVIEWED'",
                             (job_id, user)).rowcount
    if not changed:
        raise HTTPException(409, "This review has already been used; check its job record")
    try:
        with Cluster(p, user) as cluster:
            cluster.validate(spec)
            slurm_id = cluster.submit(job)
        update_job(job_id, "SUBMITTED", slurm_id=slurm_id)
    except Exception as exc:
        # A lost SSH response may follow a successful sbatch. Never retry automatically.
        update_job(job_id, "NEEDS_CHECK", f"Submission could not be confirmed: {exc}. Check BP1 before creating another submission.")
        raise HTTPException(502, "Submission could not be confirmed. Check the saved job record and BP1 queue before retrying") from exc
    return get_job(job_id, user)


@router.post("/jobs/{job_id}/refresh")
def refresh(job_id: str, user=Depends(current_user)):
    require_live()
    job = get_job(job_id, user)
    if job["slurm_id"]:
        with Cluster(config.profile(user), user) as cluster:
            update_job(job_id, cluster.status(job["slurm_id"]))
    return get_job(job_id, user)


@router.post("/jobs/{job_id}/cancel")
def cancel(job_id: str, user=Depends(current_user)):
    require_live()
    job = get_job(job_id, user)
    if not job["slurm_id"]:
        raise HTTPException(409, "No confirmed Slurm job ID")
    with Cluster(config.profile(user), user) as cluster:
        cluster.cancel(job["slurm_id"])
    update_job(job_id, "CANCEL_REQUESTED")
    return get_job(job_id, user)


@router.get("/jobs/{job_id}/log")
def log(job_id: str, user=Depends(current_user)):
    require_live()
    job = get_job(job_id, user)
    if not job["slurm_id"]:
        raise HTTPException(409, "No confirmed Slurm job ID")
    with Cluster(config.profile(user), user) as cluster:
        return {"text": cluster.log(job)}
