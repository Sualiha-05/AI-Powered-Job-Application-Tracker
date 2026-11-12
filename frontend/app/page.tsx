'use client';

import { useCallback, useEffect, useState } from 'react';
import AddApplicationForm from './components/AddApplicationForm';
import AuthForm from './components/AuthForm';
import Board from './components/Board';
import MatchDialog from './components/MatchDialog';
import ResumePanel from './components/ResumePanel';
import {
  API,
  Application,
  ApiError,
  Resume,
  STATUS_LABEL,
  STATUSES,
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
  const [matchId, setMatchId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [api, setApi] = useState<ApiState>('checking');
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [toast, setToast] = useState<{ text: string; undo?: () => void } | null>(null);

  const notify = useCallback((text: string, undo?: () => void) => {
    setToast({ text, undo });
    window.setTimeout(() => setToast((t) => (t?.text === text ? null : t)), 5000);
  }, []);

  const signOut = useCallback(() => {
    clearToken();
    setApps([]);
    setResumes([]);
    setMatchId(null);
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
    } finally {
      setLoading(false);
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

  async function saveJobDescription(id: string, jobDescription: string) {
    const updated = await updateApplication(id, { jobDescription });
    setApps((prev) => prev.map((a) => (a.id === id ? updated : a)));
  }

  async function move(id: string, status: Status) {
    const before = apps;
    // Optimistic update, rolled back if the server rejects it.
    setApps((prev) => prev.map((a) => (a.id === id ? { ...a, status } : a)));
    try {
      await updateApplication(id, { status });
      setError(null);
      const prev = before.find((a) => a.id === id)?.status;
      notify(`Moved to ${STATUS_LABEL[status]}`, prev && prev !== status ? () => move(id, prev) : undefined);
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

  const q = query.trim().toLowerCase();
  const shown = q ? apps.filter((a) => `${a.title} ${a.company}`.toLowerCase().includes(q)) : apps;
  const matchApp = apps.find((a) => a.id === matchId) ?? null;

  if (authed === null) return <main className="shell" />;

  return (
    <>
      <header className="top">
        <div className="top-inner">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">J</span>
          <div>
            <h1>Job Tracker</h1>
            <p>{authed ? 'Your search, one pipeline.' : 'Applications, resumes and evidence in one place.'}</p>
          </div>
        </div>
        <div className="top-right">
          <p className="status" data-state={api}>{statusLabel}</p>
          {authed && (
            <button type="button" className="ghost" onClick={signOut}>
              Sign out
            </button>
          )}
        </div>
        </div>
      </header>
      <main className="shell">
      {error && <p className="error" role="alert">{error}</p>}

      {authed ? (
        <>
          <Pipeline apps={apps} />
          <ResumePanel resumes={resumes} onUpload={addResume} onDelete={removeResume} />
          <div className="toolbar">
            <label className="search">
              <span className="sr-only">Search applications</span>
              <input
                type="search"
                placeholder="Search by role or company"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
            <AddApplicationForm onCreate={add} />
          </div>
          <Board apps={shown} loading={loading} onMove={move} onDelete={remove} onMatch={(a) => setMatchId(a.id)} />
          {matchApp && (
            <MatchDialog
              key={matchApp.id}
              app={matchApp}
              resumes={resumes}
              onClose={() => setMatchId(null)}
              onSaveJobDescription={saveJobDescription}
              onUnauthorized={signOut}
            />
          )}
          {toast && (
            <div className="toast" role="status">
              {toast.text}
              {toast.undo && (
                <button type="button" onClick={() => { toast.undo?.(); setToast(null); }}>
                  Undo
                </button>
              )}
            </div>
          )}
        </>
      ) : (
        <AuthForm onAuthed={load} />
      )}
      </main>
    </>
  );
}

function Pipeline({ apps }: { apps: Application[] }) {
  const count = (s: Status) => apps.filter((a) => a.status === s).length;
  const sent = apps.length - count('saved');
  const advanced = count('interview') + count('offer');
  const rate = sent > 0 ? Math.round((advanced / sent) * 100) : 0;
  const kpis: [string | number, string][] = [
    [apps.length, 'Total tracked'],
    [count('applied') + count('interview'), 'In progress'],
    [count('offer'), 'Offers'],
    [`${rate}%`, 'Interview rate'],
  ];
  return (
    <section className="pipeline" aria-label="Pipeline summary">
      <div className="kpis">
        {kpis.map(([v, l]) => (
          <div className="kpi" key={l}>
            <b>{v}</b>
            <span>{l}</span>
          </div>
        ))}
      </div>
      <div className="funnel" role="img" aria-label={STATUSES.map((s) => `${count(s)} ${STATUS_LABEL[s]}`).join(', ')}>
        {STATUSES.map((s) => (
          <i key={s} data-status={s} style={{ flexGrow: count(s), flexBasis: 0 }} />
        ))}
      </div>
      <div className="legend">
        {STATUSES.map((s) => (
          <span key={s} data-status={s}>
            <i /> {STATUS_LABEL[s]} {count(s)}
          </span>
        ))}
      </div>
    </section>
  );
}
