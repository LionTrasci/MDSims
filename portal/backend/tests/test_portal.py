from concurrent.futures import ThreadPoolExecutor
import json
import time
import pytest
from fastapi.testclient import TestClient
from app import config, routes
from app.auth import Identity, current_user
from app.database import connection
from app.main import app
from app.models import Simulation
from app.scripts import render

HEADERS = {"X-Portal-Request": "1"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "MODE", "preview")
    settings = config.configuration()
    monkeypatch.setattr(config, "configuration", lambda: settings)
    app.dependency_overrides.clear()
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client
    app.dependency_overrides.clear()


def payload(**kwargs):
    return dict(account="PROJECT", partition="gpu", topology="/user/work/preview/system.parm7",
                coordinates="/user/work/preview/system.rst7", **kwargs)


def test_script_and_preview_cannot_submit(client):
    response = client.post("/api/reviews", json=payload(ligands=[{"path": "", "charge": 0, "multiplicity": 1}]), headers=HEADERS)
    assert response.status_code == 200
    job = response.json()
    assert "--gres=gpu:1" in job["script"]
    assert "--gamd" not in job["script"]
    assert "--parm7 input.parm7 --rst7 input.rst7" in job["script"]
    assert client.post(f"/api/jobs/{job['id']}/submit", json={}, headers=HEADERS).status_code == 409
    assert len(client.get("/api/jobs").json()) == 1


@pytest.mark.parametrize("change", [
    {"topology": "/user/work/preview/foo;touch_bad"},
    {"coordinates": "/user/work/preview/../other/file"},
    {"topology": "/user/work/elsewhere/file"},
    {"run_parent": "/user/work/preview/../../etc"},
    {"partition": "gpu\n#SBATCH --account=other"},
    {"dependency": "afterok:1;id"},
    {"walltime": "0-00:00:00"},
    {"walltime": "3-00:00:00"},
    {"cpus": 99},
])
def test_reject_unsafe_or_invalid_inputs(client, change):
    data = payload(); data.update(change)
    response = client.post("/api/reviews", json=data, headers=HEADERS)
    assert response.status_code in {400, 422}
    assert client.get("/api/jobs").json() == []


def test_mmpbsa_and_scheduler_options(client):
    data = payload(workflow="mmpbsa", protein="/user/work/preview/pro.pdb",
                   ligands=[{"path": "/user/work/preview/lig.mol2", "charge": -1, "multiplicity": 2}],
                   engine="cpu", cpus=4, walltime="1-00:00:00", mail_user="user@example.ac.uk",
                   dependency="afterok:123:456", qos="normal", reservation="lab", exclusive=True)
    script = client.post("/api/reviews", json=data, headers=HEADERS).json()["script"]
    assert "--gres" not in script
    assert "--charge -1 --multiplicity 2" in script
    assert "--mail-type=END,FAIL" in script
    assert "--dependency=afterok:123:456" in script
    assert "--exclusive" in script
    assert 'MDSIMS_MPI_RANKS="$SLURM_NTASKS"' in script
    assert "--ntasks=4" in script
    assert "--cpus-per-task=1" in script


def test_mutations_require_csrf_header(client):
    assert client.post("/api/reviews", json=payload()).status_code == 403
    assert client.post("/api/logout", json={}).status_code == 403


def live_mock(monkeypatch):
    p = config.profile("preview")
    monkeypatch.setattr(config, "profile", lambda _: p)
    monkeypatch.setattr(config, "MODE", "live")
    app.dependency_overrides[current_user] = lambda: Identity("preview", "test")
    class FakeCluster:
        submissions = 0
        def __init__(self, *_): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def validate(self, spec): pass
        def submit(self, job):
            type(self).submissions += 1
            return "4321"
        def status(self, slurm_id): return "RUNNING"
        def cancel(self, slurm_id): pass
        def log(self, job): return "Simulation output"
    monkeypatch.setattr(routes, "Cluster", FakeCluster)
    return FakeCluster


def test_concurrent_duplicate_submission_only_runs_once(client, monkeypatch):
    cluster = live_mock(monkeypatch)
    job = client.post("/api/reviews", json=payload(), headers=HEADERS).json()
    def submit(_):
        return client.post(f"/api/jobs/{job['id']}/submit", json={}, headers=HEADERS).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(submit, range(2)))
    assert sorted(statuses) == [200, 409]
    assert cluster.submissions == 1


def test_owners_are_isolated(client, monkeypatch):
    live_mock(monkeypatch)
    job = client.post("/api/reviews", json=payload(), headers=HEADERS).json()
    app.dependency_overrides[current_user] = lambda: Identity("someone_else", "other")
    assert client.get("/api/jobs").json() == []
    for action in ("submit", "refresh", "cancel"):
        assert client.post(f"/api/jobs/{job['id']}/{action}", json={}, headers=HEADERS).status_code == 404
    assert client.get(f"/api/jobs/{job['id']}/log").status_code == 404


def test_lost_submission_response_requires_manual_check(client, monkeypatch):
    cluster = live_mock(monkeypatch)
    def lost(self, job): raise TimeoutError("connection lost")
    monkeypatch.setattr(cluster, "submit", lost)
    job = client.post("/api/reviews", json=payload(), headers=HEADERS).json()
    url = f"/api/jobs/{job['id']}/submit"
    assert client.post(url, json={}, headers=HEADERS).status_code == 502
    assert client.get("/api/jobs").json()[0]["state"] == "NEEDS_CHECK"
    assert client.post(url, json={}, headers=HEADERS).status_code == 409


def test_expired_reviews_and_status_log_cancel(client, monkeypatch):
    live_mock(monkeypatch)
    job = client.post("/api/reviews", json=payload(), headers=HEADERS).json()
    with connection() as db:
        db.execute("UPDATE jobs SET created=? WHERE id=?", (time.time() - 1900, job["id"]))
    assert client.post(f"/api/jobs/{job['id']}/submit", json={}, headers=HEADERS).status_code == 409
    job = client.post("/api/reviews", json=payload(), headers=HEADERS).json()
    client.post(f"/api/jobs/{job['id']}/submit", json={}, headers=HEADERS)
    assert client.post(f"/api/jobs/{job['id']}/refresh", json={}, headers=HEADERS).json()["state"] == "RUNNING"
    assert client.get(f"/api/jobs/{job['id']}/log").json()["text"] == "Simulation output"
    assert client.post(f"/api/jobs/{job['id']}/cancel", json={}, headers=HEADERS).json()["state"] == "CANCEL_REQUESTED"


def test_bp1_login_keeps_no_password_in_database(client, monkeypatch):
    p = config.profile("preview")
    monkeypatch.setattr(config, "MODE", "live")
    monkeypatch.setattr(config, "configuration", lambda: {"defaults": p})
    calls = []
    monkeypatch.setattr(routes, "connect", lambda profile, password: calls.append((profile["username"], password)) or object())
    monkeypatch.setattr(routes, "add_session", lambda *_: None)
    response = client.post("/api/login", json={"username": "researcher", "password": "test-password-only"}, headers=HEADERS)
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert calls == [("researcher", "test-password-only")]
    with connection() as db:
        row = dict(db.execute("SELECT * FROM sessions").fetchone())
    assert row["owner"] == "researcher"
    assert "test-password-only" not in json.dumps(row)


def test_live_needs_authenticated_session(client, monkeypatch):
    monkeypatch.setattr(config, "MODE", "live")
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/jobs").status_code == 401


def test_default_environment_and_optional_conda_are_saved_in_review(client):
    data = payload(use_conda=True,
        conda_sh="/user/home/preview/miniconda3/etc/profile.d/conda.sh",
        conda_prefix="/user/home/preview/miniconda3/envs/ambertools")
    response = client.post("/api/reviews", json=data, headers=HEADERS)
    assert response.status_code == 200
    job = response.json()
    script = job["script"]
    commands = ["module purge", "module add apps/amber/22",
        "source /software/local/apps/amber24-tools24-MPI-CUDA-GCC/amber24/amber.sh",
        "source " + data["conda_sh"], "conda activate " + data["conda_prefix"], "set -u"]
    positions = [script.index(command) for command in commands]
    assert positions == sorted(positions)
    assert json.loads(job["settings"])["conda_prefix"] == data["conda_prefix"]
    assert script.startswith("#!/bin/bash -l\n")
    assert 'command -v "$executable"' in script


@pytest.mark.parametrize("change", [
    {"conda_sh": ""}, {"conda_prefix": ""},
    {"conda_sh": "/user/home/preview/foo.sh"},
    {"conda_prefix": "~/miniconda3/envs/ambertools"},
    {"conda_prefix": "/user/home/preview/env;id"},
    {"conda_sh": "/user/home/preview/$(id)/conda.sh"},
])
def test_conda_rejects_missing_relative_or_shell_paths(client, change):
    data = payload(use_conda=True, conda_sh="/user/home/preview/miniconda3/etc/profile.d/conda.sh",
                   conda_prefix="/user/home/preview/miniconda3/envs/ambertools")
    data.update(change)
    assert client.post("/api/reviews", json=data, headers=HEADERS).status_code == 422


def test_conda_off_ignores_old_form_values_and_admin_override_remains_supported(client):
    spec = Simulation(**payload(conda_sh="/old/conda.sh", conda_prefix="/old/env"))
    p = dict(config.profile("preview"), environment="/software/site-amber.sh")
    script = render(spec, p, "/user/work/preview/run")
    assert "source /software/site-amber.sh" in script
    assert "module purge" not in script
    assert "conda activate" not in script


def test_conda_preflight_checks_files_without_executing_activation(client):
    from app.cluster import Cluster
    from app.environment import AMBER_SCRIPT
    from types import SimpleNamespace
    import stat
    checked = []
    spec = Simulation(**payload(use_conda=True, conda_sh="/user/home/preview/base/etc/profile.d/conda.sh",
                               conda_prefix="/user/home/preview/envs/amber"))
    def remote_stat(path):
        checked.append(path)
        return SimpleNamespace(st_mode=stat.S_IFDIR if path.endswith("conda-meta") or path == "/user/work/preview" else stat.S_IFREG)
    cluster = Cluster(config.profile("preview"), Identity("preview"))
    cluster.sftp = SimpleNamespace(normalize=lambda path: path, stat=remote_stat)
    cluster.validate(spec)
    assert {AMBER_SCRIPT, spec.conda_sh, spec.conda_prefix + "/bin/python", spec.conda_prefix + "/conda-meta"} <= set(checked)
