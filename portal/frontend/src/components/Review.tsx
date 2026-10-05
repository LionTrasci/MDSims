import type { Job, Profile, Simulation } from '../types';
export function Review({job, spec, profile, busy, onSubmit}: {job: Job | null; spec: Simulation; profile: Profile; busy: boolean; onSubmit: () => void}) {
  function download() {
    if (!job) return;
    const url = URL.createObjectURL(new Blob([job.script], {type: 'text/plain'}));
    const a = document.createElement('a'); a.href = url; a.download = `${job.name}.sbatch`; a.click(); URL.revokeObjectURL(url);
  }
  return <aside className="review-panel"><div className="eyebrow">SUBMISSION SUMMARY</div><h2>{spec.name || 'New simulation'}</h2><dl><div><dt>Workflow</dt><dd>{spec.workflow === 'md' ? 'Amber MD' : 'MM-PB(GB)SA'}</dd></div><div><dt>Run as</dt><dd>{profile.bp1_user}</dd></div><div><dt>Production</dt><dd>{spec.duration_ns} ns / {spec.temperature} K</dd></div><div><dt>Resources</dt><dd>{spec.cpus} CPU · {spec.memory_gb} GB{spec.engine === 'gpu' ? ' · 1 GPU' : ''}</dd></div><div><dt>Time limit</dt><dd>{spec.walltime}</dd></div></dl>
    {job ? <><div className="review-status">✓ {profile.mode === 'preview' ? 'Script generated' : 'Input paths checked'}</div><p className="muted">A fresh run directory keeps this simulation separate.</p><code className="directory">{job.directory}</code><details open><summary>Slurm submission script</summary><pre>{job.script}</pre></details><button className="secondary" onClick={download}>Download .sbatch</button><button disabled={busy || profile.mode !== 'live' || job.state !== 'REVIEWED'} onClick={onSubmit}>{busy ? 'Submitting…' : 'Submit reviewed job to BP1'}</button><p className="muted">{profile.mode === 'preview' ? 'Preview only. BP1 files and connectivity have not been checked.' : 'This review expires after 30 minutes. Changing settings requires a new review.'}</p></> : <div className="empty-review"><span className="code-icon">⌘</span><h3>Review before you run</h3><p>Complete the inputs to see the exact script that will be sent to Slurm.</p></div>}
  </aside>;
}
