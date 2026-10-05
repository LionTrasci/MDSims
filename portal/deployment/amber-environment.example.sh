#!/bin/bash
# Optional administrator override: install on BP1 and set environment in config.json.
# Leaving environment empty uses these same commands directly in each job script.
# User-provided BP1 setup; runtime compatibility still needs a compute-node test.
module purge
module add apps/amber/22
source /software/local/apps/amber24-tools24-MPI-CUDA-GCC/amber24/amber.sh

# Users can optionally activate their own Conda environment through the portal form.

# The chosen commands must resolve on COMPUTE nodes:
# command -v amberMDrun cpptraj pmemd.cuda pmemd.cuda_DPFP
# For MM-PB(GB)SA also: mmpbsa acpype pdb4amber gmx gmx_MMPBSA mpirun
