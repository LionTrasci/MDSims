# BP1 validation handoff

The office-server hostname can be supplied later. First collect the cluster and
software details from a normal BP1 SSH session. These commands do not submit jobs
or start an Amber calculation.

## 1. Partitions, GPU resources and project access

```bash
sinfo -o '%P|%a|%l|%G|%f'
sacctmgr -nP show assoc where user="$USER" format=Cluster,Account,Partition,QOS
```

The first command reports partition name, availability, walltime limit, generic
resources (including GPU types/counts), and node features. The second reports your
Slurm associations. If either command is unavailable or access is denied, return
the error along with the remaining output. Associations do not by themselves
prove that every displayed GPU is usable by your account.

## 2. Check the supplied Amber setup

Run the entire block, including the parentheses. It uses a subshell so changes to
modules and environment variables do not persist in your interactive shell.

```bash
(
  module purge &&
  module add apps/amber/22 &&
  source /software/local/apps/amber24-tools24-MPI-CUDA-GCC/amber24/amber.sh || exit

  module list
  printf 'AMBERHOME=%s\n' "${AMBERHOME:-unset}"
  for tool in python amberMDrun mmpbsa cpptraj sander pmemd.cuda pmemd.cuda_DPFP acpype pdb4amber gmx gmx_MMPBSA mpirun; do
    command -v "$tool" || printf 'MISSING: %s\n' "$tool"
  done
)
```

The Amber 22 module and Amber 24 setup path are deliberately retained as supplied.
Their combined runtime compatibility remains to be checked on a compute node.
Missing `amberMDrun`/`mmpbsa` indicates the repository's Python package is not on
the active PATH; the Amber installation alone does not provide those wrappers.

For a personal Conda environment, also return the absolute BP1 paths of its
`etc/profile.d/conda.sh` activation script and environment directory. The optional
Conda activation goes after the Amber setup, so repeat the executable checks in
that combined environment if you already use it. No passwords or private keys
are needed in the feedback.

## 3. Next step after reviewing the output

Use the confirmed partition, GPU resource syntax, project account and any required
QoS to prepare a short, one-GPU Slurm smoke test. Check the allocated GPU and the
Amber/Python runtime on the compute node before running a small known molecular
system. Follow with an explicit-charge MM-PB(GB)SA test if that workflow is needed.
The existing wrapper runs preparation and equilibration in addition to production;
even a short production duration is not a five-minute benchmark.

Office-server password login and portal submission then need a separate end-to-end
test from the deployed portal. Success in a manually submitted job does not verify
the office server's network access or SSH session handling.

References: [sinfo](https://slurm.schedmd.com/sinfo.html),
[sacctmgr](https://slurm.schedmd.com/sacctmgr.html).
