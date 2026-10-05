import type { Simulation } from '../types';

export function EnvironmentFields({spec, username, onChange}: {
  spec: Simulation; username: string; onChange: (spec: Simulation) => void;
}) {
  return <details>
    <summary>Amber environment</summary>
    <p className="muted">Uses the configured BP1 Amber setup. You can activate your personal Conda environment afterwards for AmberTools and the MDSims Python commands. The full setup is shown in the reviewed script.</p>
    <label className="check"><input type="checkbox" checked={spec.use_conda}
      onChange={e => onChange({...spec, use_conda: e.target.checked})}/> Activate a personal Conda environment</label>
    {spec.use_conda && <>
      <label>Conda activation script · BP1 path<input value={spec.conda_sh} required
        placeholder={`/user/home/${username}/miniconda3/etc/profile.d/conda.sh`}
        onChange={e => onChange({...spec, conda_sh: e.target.value})}/></label>
      <label>Conda environment directory · BP1 path<input value={spec.conda_prefix} required
        placeholder={`/user/home/${username}/miniconda3/envs/ambertools`}
        onChange={e => onChange({...spec, conda_prefix: e.target.value})}/></label>
      <p className="muted">Use absolute paths on BP1. The environment must already exist and provide the MDSims command for your workflow. GPU runs also need the selected pmemd engines.</p>
    </>}
  </details>;
}
