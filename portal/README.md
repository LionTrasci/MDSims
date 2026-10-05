# BP1 molecular dynamics portal

React + TypeScript frontend, modular FastAPI backend, SQLite job records, and
individual SSH sessions to BP1. Designed for one Linux office server with Docker.
The portal does not run Amber on the office server. It submits the repository's
`amberMDrun` / `mmpbsa` commands to Slurm on BP1.

For the first live validation, follow [BP1_TESTING.md](BP1_TESTING.md). Begin with
read-only partition/account queries and executable discovery before a compute job.

## Access model

1. Users open an SSH tunnel to the **office server** (their office-server account).
2. They visit the portal at `http://127.0.0.1:8765` in their browser.
3. In live mode they sign in using their **own BP1 username and password**.
4. The portal opens SSH to the fixed, administrator-configured BP1 host. It retains
   the authenticated connection in memory, never writes the password to disk, and
   uses that connection for that browser session's submission and monitoring.
5. Jobs and logs are accessible only to the authenticated job owner. Logout closes
   that session's BP1 connection. Sessions expire after eight hours; restarting the
   portal requires users to sign in again. Queued/running Slurm jobs continue.

The office server handles BP1 passwords briefly during authentication and must be
trusted. No private keys or credentials belong in source control. Plain password
SSH is supported; interactive MFA/challenge flows need a different login adapter.
Run **one backend worker/instance**, because SSH sessions live in process memory.

## Quick local preview on the office server

From `portal/`:

```bash
docker compose up -d --build
```

From each user's computer:

```powershell
ssh -N -L 8765:127.0.0.1:8765 OFFICE_USER@OFFICE_SERVER
```

Then visit `http://127.0.0.1:8765`. Keep the SSH terminal open. Use a different
local port if needed (`-L 8766:127.0.0.1:8765`, then visit port 8766).

Preview mode needs no BP1 connection. It validates form structure and saves script
reviews, but cannot submit, cancel, read BP1 files, or claim a real job status.
Example form paths: `/user/work/preview/system.parm7` and
`/user/work/preview/system.rst7`. Preview records use a single preview identity.

## Enable real BP1 connections

1. Copy `deployment/config.example.json` to `deployment/config.json`.
2. Supply the BP1 SSH host key in `deployment/known_hosts`, verifying its fingerprint
   independently with your HPC administrator. Do not blindly trust `ssh-keyscan`
   output. Unknown or changed host keys are rejected.
3. Configure the work-root convention, actual partitions, suggested project accounts,
   and local resource limits. Leave `environment` empty to use the supplied BP1 Amber
   commands below, or set it to the **BP1 path** of an administrator-owned setup script.
   `partitions` and `accounts` are suggestions by default: users can enter their own,
   and Slurm authorizes them. Set `restrict_choices: true` to enforce these lists.
   Per-user entries in `profiles` override `defaults` and require all default fields
   plus `username`. Users may select any run parent inside their configured work root.
4. On BP1, install this checkout, including the portal integration fixes, into the
   Amber Python environment (`git submodule update --init --recursive`, then follow
   the root README's build requirements). The web image intentionally does not build
   Amber or the C++ extension. Install Amber/AmberTools and, for binding-energy runs,
   ACPYPE, GROMACS, gmx_MMPBSA, ParmEd and their compatible MPI environment separately.
5. Test the Amber setup on an allocated compute node. An optional administrator
   override is provided in `deployment/amber-environment.example.sh`.
6. Make configuration readable by container UID 10001. Keep the default loopback
   port binding and start live mode:

```bash
PORTAL_MODE=live docker compose up -d --build
```

For an HTTPS reverse proxy instead of SSH tunnels, keep the backend private and set
`https: true` so session cookies require HTTPS, and add the portal hostname to
`allowed_hosts`. Do not expose this password login on
unencrypted LAN HTTP. The default Compose mapping is loopback only. Restrict who can
forward to the office server's local port using the office server's SSH controls.

## Submission workflow

The default batch script starts a Bash login shell and uses the user-supplied setup:

```bash
module purge
module add apps/amber/22
source /software/local/apps/amber24-tools24-MPI-CUDA-GCC/amber24/amber.sh
```

The module name refers to Amber 22 while the sourced installation refers to Amber 24;
these are retained exactly as supplied, pending a BP1 compute-node compatibility test.

Under **Amber environment**, users can enable a personal Conda environment and enter
two absolute **BP1** paths: the base installation's `etc/profile.d/conda.sh` and the
environment directory (for example `/user/home/USER/miniconda3/envs/ambertools`). The
job sources `conda.sh` and runs `conda activate /absolute/environment/path` after the
BP1 Amber setup. The selected environment must provide the repository's installed
`amberMDrun` or `mmpbsa` command; AmberTools alone does not provide those entry points.
GPU runs also require the selected pmemd executables. Conda may change library and
executable search paths, so test the combined environment on BP1.

Live review checks that the activation script, environment Python and `conda-meta`
directory exist. It does not execute a user's activation script on the login node
or office server. The batch job checks required executables after activation and
fails clearly if one is missing. Paths are saved in each immutable review, and
editing them invalidates the review. There are no shared per-user environment edits.
See [Conda environment activation](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html).

- Choose Amber MD from topology/restart files, or MM-PB(GB)SA from a protein PDB and
  one or more pre-positioned ligand MOL2 files. The latter performs preparation, MD,
  then binding-energy analysis; it is not analysis of an existing trajectory.
- Enter production duration, temperature, and CPU or GPU engines. CPU MD currently
  uses serial sander; requesting more CPUs does not make that stage parallel.
- Select account, partition, walltime (`HH:MM:SS` or `D-HH:MM:SS`), memory, CPUs and
  parent directory. Optional dependency, email END/FAIL, QoS, reservation and exclusive
  allocation are supported. GPU mode requests one GPU via `--gres=gpu:1`; confirm
  the correct BP1 GPU partition and resource syntax before real use.
- Check inputs and review the exact script. Live review checks remote input paths;
  preview review does not. The form is locked while checking/submitting, and edits
  invalidate the current review. Reviews expire after 30 minutes.
- Submit once. A transactional state change prevents repeating the same review,
  including double-clicks or concurrent requests. Every run creates a unique directory
  under the selected parent; the script copies inputs into safe, fixed local names.
  Inputs are copied when the job starts: do not modify source files while queued.
- Job records provide explicit refresh, a 64 KB log tail and cancellation confirmation.
  Slurm status is read via `squeue` / `sacct`; records only cover this portal's jobs.

If SSH is lost around `sbatch`, the record is marked `NEEDS_CHECK`; never assume
the job failed to submit. Check `squeue -u USER` and the recorded run directory
before creating another review. A server crash during submission can leave
`SUBMITTING`, which needs the same check. There is no automatic submission retry.

## Structure

```text
frontend/src/components/  Workflow form, review, login, job records
frontend/src/api.ts      Typed API helper
backend/app/auth.py      Session identity
backend/app/cluster.py   Password SSH session lifecycle and Slurm adapter
backend/app/models.py    Input validation and profile limits
backend/app/scripts.py   Deterministic batch-script rendering
backend/app/environment.py BP1 setup and optional per-job Conda activation
backend/app/routes.py    HTTP endpoints and submission state transitions
backend/app/database.py  SQLite persistence and ownership
backend/app/config.py    Administrator-owned BP1 configuration
backend/tests/           Validation, access isolation and submission tests
deployment/              Configuration and BP1 environment examples
```

## Development and tests

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt
python -m pytest -q
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm dev
# Production static frontend:
pnpm build
```

Vite proxies `/api` to port 8000. After building, starting the backend from its
directory serves the frontend too. `PORTAL_DATA`, `PORTAL_CONFIG`, `PORTAL_STATIC`
and `PORTAL_MODE` override local paths/mode. Back up the persistent Docker volume
for job history; actual simulation outputs stay on BP1.

The wrapper fixes cover MM-PBSA argument ordering, charge validation, honoring
allocated analysis CPUs, and propagating production temperature. They do not
establish scientific validity. The native extension and full Amber/MPI workflow
must be smoke-tested on BP1 before production runs.

Reference: [Slurm sbatch options](https://slurm.schedmd.com/sbatch.html) and
[FastAPI Docker deployment](https://fastapi.tiangolo.com/deployment/docker/).
