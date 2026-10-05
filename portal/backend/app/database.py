"""Small shared-server store. Transactions guard against duplicate submissions."""
import sqlite3
from contextlib import contextmanager
from . import config


@contextmanager
def connection():
    config.DATA.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.DATA / "portal.db", timeout=15) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        yield db


def initialize():
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, owner TEXT NOT NULL, created REAL NOT NULL,
            name TEXT NOT NULL, settings TEXT NOT NULL, script TEXT NOT NULL,
            directory TEXT NOT NULL, state TEXT NOT NULL, slurm_id TEXT, message TEXT NOT NULL DEFAULT ''
        );
        """)


def owned_job(job_id, owner):
    with connection() as db:
        row = db.execute("SELECT * FROM jobs WHERE id=? AND owner=?", (job_id, owner)).fetchone()
    return dict(row) if row else None


def update_job(job_id, state, message="", slurm_id=None):
    with connection() as db:
        db.execute("UPDATE jobs SET state=?, message=?, slurm_id=COALESCE(?,slurm_id) WHERE id=?",
                   (state, message, slurm_id, job_id))
