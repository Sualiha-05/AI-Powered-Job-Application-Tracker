'use client';

import { FormEvent, useState } from 'react';
import { ApiError, login, register, setToken } from '../lib/api';

export default function AuthForm({ onAuthed }: { onAuthed: () => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { accessToken } = await (mode === 'login' ? login : register)({ email, password });
      setToken(accessToken);
      onAuthed();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-hero">
        <h2>Know where every application stands.</h2>
        <p>Track roles on a board, then check your resume against each job description with quoted evidence.</p>
        <div className="auth-demo" aria-hidden="true">
          <div data-status="applied">Frontend Engineer <em>Applied</em></div>
          <div data-status="interview">Full-Stack Developer <em>Interview</em></div>
          <div data-status="offer">ML Engineer <em>Offer</em></div>
        </div>
      </div>
    <form className="panel auth" onSubmit={submit}>
      <h1>{mode === 'login' ? 'Sign in' : 'Create your account'}</h1>

      <label>
        Email
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
      </label>

      <label>
        Password
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
        />
      </label>

      {error && <p className="error" role="alert">{error}</p>}

      <button className="primary" type="submit" disabled={busy}>
        {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Register'}
      </button>

      <button
        type="button"
        className="link"
        onClick={() => {
          setMode(mode === 'login' ? 'register' : 'login');
          setError(null);
        }}
      >
        {mode === 'login' ? 'No account yet? Register' : 'Already registered? Sign in'}
      </button>
    </form>
    </div>
  );
}
