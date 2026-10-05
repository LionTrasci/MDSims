import { useEffect, useState } from 'react';
import { api } from './api';
import type { Job, Profile, Simulation } from './types';
import { Login } from './components/Login';
import { SimulationForm } from './components/SimulationForm';
import { Review } from './components/Review';
import { Jobs } from './components/Jobs';

function initial(profile: Profile): Simulation {
  return {workflow: 'md', name: 'amber-run', account: profile.accounts[0] || '', partition: profile.partitions[0] || 'short',
    walltime: '04:00:00', run_parent: profile.root, mail_user: '', dependency: '', qos: '', reservation: '', exclusive: false,
    use_conda: false, conda_sh: '', conda_prefix: '',
    cpus: 1, memory_gb: Math.min(8, profile.max_memory_gb), engine: 'gpu', temperature: 298.15,
    duration_ns: 100, topology: '', coordinates: '', protein: '', ligands: [{path: '', charge: 0, multiplicity: 1}], charge_mode: 'explicit', gamd: false};
}

export function App() {
  const [profile, setProfile] = useState<Profile | null>(null); const [loading, setLoading] = useState(true);
  const [spec, setSpec] = useState<Simulation | null>(null); const [jobs, setJobs] = useState<Job[]>([]);
  const [review, setReview] = useState<Job | null>(null); const [tab, setTab] = useState('new');
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  async function load() {
    try { const p = await api<Profile>('/me'); setProfile(p); setSpec(initial(p)); await reload(); }
    catch (e) { if ((e as Error).message !== 'Sign in to continue') setError((e as Error).message); }
    finally { setLoading(false); }
  }
  async function reload() { setJobs(await api<Job[]>('/jobs')); }
  useEffect(() => { void load(); }, []);
  async function check() {
    setBusy(true); setError(''); setNotice(''); setReview(null);
    try { setReview(await api<Job>('/reviews', spec)); await reload(); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function submit() {
    if (!review) return; setBusy(true); setError('');
    try { const job = await api<Job>(`/jobs/${review.id}/submit`, {}); setReview(null); setNotice(`Submitted to BP1 as Slurm job ${job.slurm_id}.`); setTab('jobs'); }
    catch (e) { setError((e as Error).message); setReview(null); }
    finally { setBusy(false); await reload().catch(e => setError(e.message)); }
  }
  async function logout() {
    try { await api('/logout', {}); setProfile(null); setSpec(null); setJobs([]); setReview(null); setError(''); setNotice(''); }
    catch (e) { setError((e as Error).message); }
  }
  if (loading) return <main className="loading">Opening your workspace…</main>;
  if (!profile || !spec) return <>{error && <p role="alert" className="error">{error}</p>}<Login onLogin={() => void load()}/></>;
  return <><header><div className="brand"><img src="/favicon.svg" width="36" height="36" alt=""/><strong>BP1<span> / Molecular dynamics</span></strong></div><div className="identity"><span className="connection-dot"/>{profile.bp1_user}{profile.mode === 'live' && <button className="header-button" onClick={() => void logout()}>Sign out</button>}</div></header>
    <main className="workspace"><div className="page-title"><div><div className="eyebrow">BLUEPEBBLE · MDSIMS</div><h1>Simulation workspace</h1><p>Prepare, review and submit your Amber simulations.</p></div><span className="cluster-badge">{profile.mode === 'preview' ? 'LOCAL PREVIEW' : 'BP1 · SLURM'}</span></div>
      {profile.mode === 'preview' && <div className="preview-banner"><strong>Preview mode</strong><span>Explore the workflow and generate scripts. Live submission requires your BP1 profile and environment configuration.</span></div>}
      <nav aria-label="Workspace"><button className={tab === 'new' ? 'active' : ''} onClick={() => setTab('new')}>New simulation</button><button className={tab === 'jobs' ? 'active' : ''} onClick={() => setTab('jobs')}>Job records <span className="count">{jobs.length}</span></button></nav>
      {error && <p role="alert" className="error">{error}</p>}{notice && <p role="status" className="success">{notice}</p>}
      {tab === 'new' ? <div className="submission-layout"><fieldset disabled={busy}><SimulationForm value={spec} profile={profile} onChange={s => {setSpec(s); setReview(null); setNotice('');}} onReview={() => void check()} busy={busy}/></fieldset><Review job={review} spec={spec} profile={profile} busy={busy} onSubmit={() => void submit()}/></div> : <Jobs jobs={jobs} live={profile.mode === 'live'} reload={reload}/>}
      <footer><span>AmberMDrun / BP1 submission portal</span><span>Compute runs on BP1 · Portal hosted in your office</span></footer>
    </main></>;
}
