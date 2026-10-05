import { useState } from 'react';
import { api } from '../api';
import type { Job } from '../types';
export function Jobs({jobs, live, reload}: {jobs: Job[]; live: boolean; reload: () => Promise<void>}) {
  const [busy, setBusy] = useState(''); const [error, setError] = useState(''); const [log, setLog] = useState<{title: string; text: string} | null>(null);
  async function action(job: Job, name: string) {
    if (name === 'cancel' && !window.confirm(`Cancel BP1 job ${job.slurm_id} (${job.name})?`)) return;
    setBusy(job.id); setError('');
    try {
      if (name === 'log') { const data = await api<{text: string}>(`/jobs/${job.id}/log`); setLog({title: job.name, text: data.text}); }
      else { await api(`/jobs/${job.id}/${name}`, {}); await reload(); }
    } catch (e) { setError((e as Error).message); } finally { setBusy(''); }
  }
  return <section className="card"><div className="section-title"><div><h2>Your job records</h2><p>Reviews and submissions made through this portal. Status is updated when you press Refresh.</p></div><button className="secondary" onClick={() => void reload().catch(e => setError(e.message))}>Reload records</button></div>{error && <p role="alert" className="error">{error}</p>}
    {jobs.length === 0 ? <div className="empty-jobs"><h3>No submissions yet</h3><p>Start a new simulation and review its Slurm script. Your records will appear here.</p></div> : <div className="job-list">{jobs.map(job => <article className="job" key={job.id}><div className="job-heading"><strong>{job.name}</strong><span className="badge">{job.state.replaceAll('_', ' ')}</span></div><p className="muted">{new Date(job.created * 1000).toLocaleString()} · {job.slurm_id ? `Slurm ${job.slurm_id}` : 'No Slurm job ID'}</p><code className="directory">{job.directory}</code>{job.message && <p className="error">{job.message}</p>}<details><summary>Saved script</summary><pre>{job.script}</pre></details>{live && job.slurm_id && <div className="job-actions"><button className="secondary" disabled={busy === job.id} onClick={() => void action(job, 'refresh')}>Refresh status</button><button className="secondary" disabled={busy === job.id} onClick={() => void action(job, 'log')}>View log</button><button className="danger" disabled={busy === job.id} onClick={() => void action(job, 'cancel')}>Cancel job</button></div>}</article>)}</div>}
    {log && <section className="log-panel"><div className="job-heading"><h3>Output · {log.title}</h3><button className="secondary" onClick={() => setLog(null)}>Close log</button></div><p className="muted">Last 64 KB of Slurm output.</p><pre>{log.text || 'Output file is empty.'}</pre></section>}
  </section>;
}
