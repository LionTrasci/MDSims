"""SSH under a server-configured individual identity, with verified host keys."""
import re
import shlex
import stat
import threading
import time
from pathlib import PurePosixPath
import paramiko
from .config import configuration
from .environment import required_files

# Passwords are used only for SSH authentication. Sessions retain the SSH transport.
_sessions = {}
_guard = threading.RLock()


def connect(profile, password):
    cfg = configuration()
    client = paramiko.SSHClient()
    client.load_host_keys(cfg["known_hosts"])
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(cfg["host"], port=cfg.get("port", 22), username=profile["username"],
                       password=password, look_for_keys=False, allow_agent=False,
                       timeout=15, auth_timeout=30, banner_timeout=15)
        client.get_transport().set_keepalive(30)
        return client
    except Exception:
        client.close()
        raise


def close_session(token):
    with _guard:
        session = _sessions.pop(token, None)
    if session:
        with session[1]:
            session[0].close()


def prune_sessions():
    with _guard:
        expired = [token for token, (_, _, expires) in _sessions.items() if expires <= time.time()]
    for token in expired:
        close_session(token)


def close_all_sessions():
    with _guard:
        tokens = list(_sessions)
    for token in tokens:
        close_session(token)


def add_session(token, client):
    prune_sessions()
    with _guard:
        _sessions[token] = (client, threading.RLock(), time.time() + 28800)


def has_session(token):
    prune_sessions()
    with _guard:
        session = _sessions.get(token)
        return bool(session and session[0].get_transport() and session[0].get_transport().is_active())


class Cluster:
    def __init__(self, profile, identity):
        self.profile = profile
        self.identity = identity

    def __enter__(self):
        with _guard:
            session = _sessions.get(self.identity.token)
        if not session:
            raise RuntimeError("SSH session expired; sign in again")
        self.client, self.lock, _ = session
        self.lock.acquire()
        try:
            self.sftp = self.client.open_sftp()
            self.sftp.get_channel().settimeout(30)
        except Exception:
            self.lock.release()
            raise
        return self

    def __exit__(self, *args):
        self.sftp.close()
        self.lock.release()

    def run(self, command):
        _, stdout, stderr = self.client.exec_command(command, timeout=30)
        # Commands here return bounded output (one submission, one job, or cancellation).
        output = stdout.read(65536).decode("utf-8", "replace")
        error = stderr.read(65536).decode("utf-8", "replace")
        if stdout.channel.recv_exit_status() != 0:
            raise RuntimeError(error.strip() or output.strip() or "BP1 command failed")
        return output.strip()

    def validate(self, spec):
        root = PurePosixPath(self.sftp.normalize(self.profile["root"]))
        for source, _ in spec.inputs():
            canonical = self.sftp.normalize(source)
            if not PurePosixPath(canonical).is_relative_to(root):
                raise ValueError("An input resolves outside your configured BP1 work directory")
            if not stat.S_ISREG(self.sftp.stat(canonical).st_mode):
                raise ValueError(f"Input is not a regular file: {source}")
        # These are BP1 paths read as the authenticated user, never executed on the portal host.
        for path in required_files(spec, self.profile):
            if not stat.S_ISREG(self.sftp.stat(path).st_mode):
                raise ValueError(f"Environment file is not a regular file: {path}")
        if spec.use_conda and not stat.S_ISDIR(self.sftp.stat(spec.conda_prefix.rstrip("/") + "/conda-meta").st_mode):
            raise ValueError("Conda environment must contain a conda-meta directory")
        parent = spec.run_parent or self.profile["root"]
        if not PurePosixPath(self.sftp.normalize(parent)).is_relative_to(root):
            raise ValueError("Run parent resolves outside your work directory")
        if not stat.S_ISDIR(self.sftp.stat(parent).st_mode):
            raise ValueError("Run parent must be an existing directory")

    def submit(self, job):
        # mkdir is exclusive. An existing run is never overwritten or resubmitted.
        self.sftp.mkdir(job["directory"], mode=0o700)
        with self.sftp.open(job["directory"] + "/submit.sbatch", "w") as stream:
            stream.write(job["script"])
        self.sftp.chmod(job["directory"] + "/submit.sbatch", 0o600)
        result = self.run("sbatch --parsable " + shlex.quote(job["directory"] + "/submit.sbatch"))
        if not re.fullmatch(r"\d+(;[A-Za-z0-9_.-]+)?", result):
            raise RuntimeError("Unexpected sbatch response; check BP1 before retrying")
        return result.split(";")[0]

    def status(self, slurm_id):
        job_id = str(int(slurm_id))
        try:
            result = self.run(f"squeue --noheader --jobs={job_id} --format=%T")
        except RuntimeError as exc:
            if "Invalid job id" not in str(exc):
                raise
            result = ""
        if result:
            return result.splitlines()[0]
        result = self.run(f"sacct --noheader --parsable2 --jobs={job_id} --format=JobIDRaw,State,ExitCode")
        for line in result.splitlines():
            fields = line.split("|")
            if fields[0] == job_id:
                return fields[1]
        return "UNKNOWN"

    def cancel(self, slurm_id):
        self.run(f"scancel {int(slurm_id)}")

    def log(self, job):
        path = f"{job['directory']}/slurm-{int(job['slurm_id'])}.out"
        try:
            with self.sftp.open(path) as stream:
                stream.seek(max(0, stream.stat().st_size - 65536))
                return stream.read(65536).decode("utf-8", "replace")
        except FileNotFoundError:
            return "No Slurm output file yet. The job may still be pending."
