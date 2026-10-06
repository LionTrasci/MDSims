import { useState, type FormEvent } from 'react';
import { api } from '../api';
export function Login({onLogin}: {onLogin: () => void}) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try { await api('/login', Object.fromEntries(form)); onLogin(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <main className="login card"><div className="eyebrow">BLUEPEBBLE / MDSIMS</div><h1>Your simulations,<br/>one workspace.</h1><p>Connect using your BP1 account. Jobs run under your own identity.</p><form onSubmit={submit}><label>BP1 username<input name="username" autoComplete="username" required /></label><label>BP1 password<input name="password" type="password" autoComplete="current-password" required /></label><p className="muted">Your password is used to open an SSH session and is not saved. Use this portal through your office-server SSH tunnel or HTTPS.</p>{error && <p role="alert" className="error">{error}</p>}<button disabled={busy}>{busy ? 'Connecting to BP1…' : 'Connect to BP1 →'}</button></form></main>;
}
