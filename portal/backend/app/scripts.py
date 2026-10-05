"""Render reviewed Slurm scripts using the repository's installed entry points."""
import shlex
from .models import Simulation
from .environment import setup_lines


def render(spec: Simulation, profile, directory):
    spec.check_profile(profile)
    min_engine, md_engine = ("pmemd.cuda_DPFP", "pmemd.cuda") if spec.engine == "gpu" else ("sander", "sander")
    command = ["amberMDrun" if spec.workflow == "md" else "mmpbsa",
               "--temp", str(spec.temperature), "--ns", str(spec.duration_ns),
               "--MIN", min_engine, "--MD", md_engine]
    if spec.workflow == "md":
        command += ["--parm7", "input.parm7", "--rst7", "input.rst7"]
        if spec.gamd:
            command += ["--gamd", "True"]
    else:
        command += ["--protein", "protein.pdb", "--mol2"] + [dest for _, dest in spec.inputs()[1:]]
        if spec.charge_mode == "guess":
            command += ["--guess_charge"]
        elif spec.charge_mode == "file":
            command += ["--user_charge"]
        else:
            command += ["--charge"] + [str(lig.charge) for lig in spec.ligands]
            command += ["--multiplicity"] + [str(lig.multiplicity) for lig in spec.ligands]
    lines = ["#!/bin/bash -l", f"#SBATCH --job-name={spec.name}", f"#SBATCH --account={spec.account}",
             f"#SBATCH --partition={spec.partition}", "#SBATCH --nodes=1",
             f"#SBATCH --ntasks={spec.cpus if spec.workflow == 'mmpbsa' else 1}",
             f"#SBATCH --cpus-per-task={1 if spec.workflow == 'mmpbsa' else spec.cpus}", f"#SBATCH --mem={spec.memory_gb}G",
             f"#SBATCH --time={spec.walltime}",
             f"#SBATCH --chdir={directory}", "#SBATCH --output=slurm-%j.out"]
    if spec.engine == "gpu":
        lines.append("#SBATCH --gres=gpu:1")
    for option, value in [("mail-user", spec.mail_user), ("dependency", spec.dependency), ("qos", spec.qos), ("reservation", spec.reservation)]:
        if value:
            lines.append(f"#SBATCH --{option}={value}")
    if spec.mail_user:
        lines.append("#SBATCH --mail-type=END,FAIL")
    if spec.exclusive:
        lines.append("#SBATCH --exclusive")
    # Site/Conda activation scripts may reference unset variables; enable nounset afterwards.
    lines += ["", "set -eo pipefail", "umask 077"] + setup_lines(spec, profile)
    required = [command[0], "cpptraj", min_engine, md_engine]
    if spec.workflow == "mmpbsa":
        required += ["acpype", "pdb4amber", "gmx", "gmx_MMPBSA", "mpirun"]
    lines += ["set -u", "# Fail before copying inputs if a required command is missing.",
              "for executable in " + shlex.join(list(dict.fromkeys(required))) + "; do",
              '  command -v "$executable" >/dev/null || { echo "Missing executable: $executable" >&2; exit 1; }',
              "done", "export OMP_NUM_THREADS=1", "export OPENBLAS_NUM_THREADS=1", "export MKL_NUM_THREADS=1",
              'export MDSIMS_MPI_RANKS="$SLURM_NTASKS"',
              'echo "Started $(date -Is) on $(hostname); Slurm job $SLURM_JOB_ID"']
    lines += [f"cp -- {shlex.quote(src)} {shlex.quote(dest)}" for src, dest in spec.inputs()]
    lines += [shlex.join(command), 'echo "Finished $(date -Is)"', ""]
    return "\n".join(lines)
