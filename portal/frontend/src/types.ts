export interface Profile {
  username: string; mode: 'preview' | 'live'; bp1_user: string; root: string;
  accounts: string[]; partitions: string[]; max_cpus: number; max_memory_gb: number; max_hours: number;
}
export interface Simulation {
  workflow: 'md' | 'mmpbsa'; name: string; account: string; partition: string;
  cpus: number; memory_gb: number; engine: 'gpu' | 'cpu';
  walltime: string; run_parent: string; mail_user: string; dependency: string;
  qos: string; reservation: string; exclusive: boolean;
  temperature: number; duration_ns: number; topology: string; coordinates: string; protein: string;
  ligands: {path: string; charge: number; multiplicity: number}[];
  charge_mode: 'explicit' | 'guess' | 'file'; gamd: boolean;
  use_conda: boolean; conda_sh: string; conda_prefix: string;
}
export interface Job {
  id: string; created: number; name: string; script: string; directory: string;
  state: string; slurm_id: string | null; message: string; settings: string;
}
