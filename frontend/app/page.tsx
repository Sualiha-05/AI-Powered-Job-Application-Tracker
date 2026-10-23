'use client';

import { useCallback, useEffect, useState } from 'react';
import AddApplicationForm from './components/AddApplicationForm';
import AuthForm from './components/AuthForm';
import Board from './components/Board';
import ResumePanel from './components/ResumePanel';
import {
  API,
  Application,
  ApiError,
  Resume,
  Status,
  clearToken,
  createApplication,
  deleteApplication,
  deleteResume,
  getToken,
  listApplications,
  listResumes,
  updateApplication,
  uploadResume,
} from './lib/api';

type ApiState = 'checking' | 'up' | 'down';

export default function Home() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [api, setApi] = useState<ApiState>('checking');

  const signOut = useCallback(() => {
    clearToken();
    setApps([]);
    setResumes([]);
    setAuthed(false);
  }, []);

  const handleError = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) return signOut();
      setError(err instanceof Error ? err.message : 'Something went wrong');
    },
    [signOut],
  );

  const load = useCallback(async () => {
    try {
      const [a, r] = await Promise.all([listApplications(), listResumes()]);
      setApps(a);
      setResumes(r);
      setAuthed(true);
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return signOut();
      setAuthed(true);
      handleError(err);
    }
  }, [handleError, signOut]);

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => setApi(r.ok ? 'up' : 'down'))
      .catch(() => setApi('down'));
    if (getToken()) load();
    else setAuthed(false);
  }, [load]);

  async function add(data: { company: string; title: string; jobDescription?: string }) {
    try {
      const created = await createApplication(data);
      setApps((prev) => [created, ...prev]);
      setError(null);
    } catch (err) {
      handleError(err);
    }
  }

  async function addResume(file: File) {
    try {
      const created = await uploadResume(file);
      setResumes((prev) => [created, ...prev]);
      setError(null);
    } catch (err) {
      handleError(err);
    }
  }

  async function removeResume(id: string) {
    const before = resumes;
    setResumes((prev) => prev.filter((r) => r.id !== id));
    try {
      await deleteResume(id);
    } catch (err) {
      setResumes(before);
      handleError(err);
    }
  }

  async function move(id: string, status: Status) {
    const before = apps;
    // Optimistic update, rolled back if the server rejects it.
    setApps((prev) => prev.map((a) => (a.id === id ? { ...a, status } : a)));
    try {
      await updateApplication(id, { status });
      setError(null);
    } catch (err) {
      setApps(before);
      handleError(err);
    }
  }

  async function remove(id: string) {
    const before = apps;
    setApps((prev) => prev.filter((a) => a.id !== id));
    try {
      await deleteApplication(id);
    } catch (err) {
      setApps(before);
      handleError(err);
    }
  }

  const statusLabel = { checking: 'Checking API…', up: 'API connected', down: 'API unreachable' }[api];

  if (authed === null) return <main className="shell" />;

  return (
    <main className="shell">
      <header className="top">
        <h1>{authed ? 'Your applications' : 'Job Tracker'}</h1>
        <div className="top-right">
          <p className="status" data-state={api}>{statusLabel}</p>
          {authed && (
            <button type="button" className="link" onClick={signOut}>
              Sign out
            </button>
          )}
        </div>
      </header>

      {error && <p className="error" role="alert">{error}</p>}

      {authed ? (
        <>
          <ResumePanel resumes={resumes} onUpload={addResume} onDelete={removeResume} />
          <AddApplicationForm onCreate={add} />
          <Board apps={apps} onMove={move} onDelete={remove} />
        </>
      ) : (
        <AuthForm onAuthed={load} />
      )}
    </main>
  );
}
