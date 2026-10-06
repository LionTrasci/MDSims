"""BP1 environment setup shared by script rendering and remote preflight."""
import shlex

AMBER_SCRIPT = "/software/local/apps/amber24-tools24-MPI-CUDA-GCC/amber24/amber.sh"


def setup_lines(spec, profile):
    override = profile.get("environment")
    lines = ([f"source {shlex.quote(override)}"] if override else
             ["module purge", "module add apps/amber/22", f"source {AMBER_SCRIPT}"])
    if spec.use_conda:
        lines += [f"source {shlex.quote(spec.conda_sh)}", f"conda activate {shlex.quote(spec.conda_prefix)}"]
    return lines


def required_files(spec, profile):
    files = [profile.get("environment") or AMBER_SCRIPT]
    if spec.use_conda:
        files += [spec.conda_sh, spec.conda_prefix.rstrip("/") + "/bin/python"]
    return files
