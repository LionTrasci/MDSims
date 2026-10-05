# Verification — 2 October 2026

- Backend: `python -m pytest -q` — 32 passed. Includes validation/injection rejection,
  cross-user job isolation, concurrent duplicate submissions, expired reviews,
  uncertain submission outcomes, status/log/cancel routes, login storage, and Amber
  wrapper argument/temperature/CPU allocation regressions. Slurm and Amber are mocked.
- Environment update: exact supplied BP1 module/source commands, optional Conda
  activation order and saved settings, unsafe/missing path rejection, administrator
  override compatibility, and remote environment-file preflight covered by tests.
  Browser review confirmed user-entered Conda paths appear in the generated script.
- Frontend: `pnpm build` — TypeScript check and Vite production build passed.
- Browser against the real local API: MD review, MM-PB(GB)SA review with explicit
  ligand charge and four CPUs, invalidation after editing, persistent review records,
  disabled live-submit control in preview mode. Desktop and narrow layouts inspected;
  narrow viewport had no document-level horizontal overflow. No browser console errors.
- Docker image: not built here; Docker is not installed in this Windows workspace.
- Live BP1 password authentication, Slurm submission, Amber/native extension execution,
  MPI behavior and real cancellation/log retrieval: not tested. Requires office-server
  connectivity, verified host key, actual Amber environment and cluster resource settings.

The first real run should use a small known input system and short production duration.
Confirm the run's Slurm identity, allocation, Amber output and exit status before scaling.
