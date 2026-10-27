'use client';

import { useEffect, useRef, useState } from 'react';
import { ApiError, Application, MatchResult, MatcherChoice, Resume, listMatches, runMatch } from '../lib/api';

interface Props {
  app: Application;
  resumes: Resume[];
  onClose: () => void;
  onSaveJobDescription: (id: string, jobDescription: string) => Promise<void>;
  onUnauthorized: () => void;
}

const pct = (score: number) => Math.round(score * 100);

const isAi = (matcher: string) => matcher.startsWith('llm:');
const isTfidf = (matcher: string) => matcher.startsWith('tfidf');
const shortLabel = (matcher: string) => (isAi(matcher) ? 'AI' : isTfidf(matcher) ? 'TF-IDF' : 'Keyword');
const matcherLabel = (matcher: string) =>
  isAi(matcher) ? `AI (${matcher.slice(4)})` : isTfidf(matcher) ? 'TF-IDF term overlap' : 'Keyword baseline';

export default function MatchDialog({ app, resumes, onClose, onSaveJobDescription, onUnauthorized }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [resumeId, setResumeId] = useState(resumes[0]?.id ?? '');
  const [matcher, setMatcher] = useState<MatcherChoice>('keyword');
  const [history, setHistory] = useState<MatchResult[]>([]);
  const [current, setCurrent] = useState<MatchResult | null>(null);
  const [jd, setJd] = useState(app.jobDescription ?? '');
  const [busy, setBusy] = useState(false);
  const [savingJd, setSavingJd] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasJd = Boolean(app.jobDescription?.trim());

  function fail(err: unknown) {
    if (err instanceof ApiError && err.status === 401) return onUnauthorized();
    setError(err instanceof Error ? err.message : 'Something went wrong');
  }

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  useEffect(() => {
    let live = true;
    listMatches(app.id)
      .then((h) => {
        if (!live) return;
        setHistory(h);
        setCurrent(h[0] ?? null);
      })
      .catch((e) => live && fail(e));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [app.id]);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const result = await runMatch(app.id, resumeId, matcher);
      setCurrent(result);
      setHistory((h) => [result, ...h]);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function saveJd() {
    setSavingJd(true);
    setError(null);
    try {
      await onSaveJobDescription(app.id, jd.trim());
    } catch (e) {
      fail(e);
    } finally {
      setSavingJd(false);
    }
  }

  return (
    <dialog
      ref={ref}
      className="match-dialog"
      aria-labelledby="match-title"
      onClose={onClose}
      onClick={(e) => e.target === ref.current && ref.current?.close()}
    >
      <div className="match-body">
        <header className="match-head">
          <h2 id="match-title">
            {app.title} <span className="hint">at {app.company}</span>
          </h2>
          <button type="button" className="link" onClick={() => ref.current?.close()}>
            Close
          </button>
        </header>

        {error && <p className="error" role="alert">{error}</p>}

        <details className="jd" open={!hasJd}>
          <summary>{hasJd ? 'Job description' : 'Add the job description to enable matching'}</summary>
          <textarea rows={6} value={jd} onChange={(e) => setJd(e.target.value)} aria-label="Job description" />
          <button type="button" className="primary" onClick={saveJd} disabled={savingJd || jd.trim() === (app.jobDescription ?? '').trim()}>
            {savingJd ? 'Saving…' : 'Save job description'}
          </button>
        </details>

        <div className="run-row">
          {resumes.length === 0 ? (
            <p className="hint">Upload a resume first (the Resumes panel above the board).</p>
          ) : (
            <>
              <label>
                Resume
                <select value={resumeId} onChange={(e) => setResumeId(e.target.value)}>
                  {resumes.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.filename}
                    </option>
                  ))}
                </select>
              </label>
              <fieldset className="matcher-choice">
                <legend>Matcher</legend>
                <label className="radio">
                  <input type="radio" name="matcher" checked={matcher === 'keyword'} onChange={() => setMatcher('keyword')} />
                  <span>
                    Keyword <span className="hint">free, instant; matches skills by name</span>
                  </span>
                </label>
                <label className="radio">
                  <input type="radio" name="matcher" checked={matcher === 'tfidf'} onChange={() => setMatcher('tfidf')} />
                  <span>
                    TF-IDF <span className="hint">free; weighs rare terms, so it also finds skills outside the keyword list</span>
                  </span>
                </label>
                <label className="radio">
                  <input type="radio" name="matcher" checked={matcher === 'llm'} onChange={() => setMatcher('llm')} />
                  <span>
                    AI <span className="hint">understands related experience; sends the texts to an AI provider; slower, limited per day</span>
                  </span>
                </label>
              </fieldset>
              <button type="button" className="primary" onClick={run} disabled={busy || !hasJd || !resumeId}>
                {busy ? (matcher === 'llm' ? 'Asking the AI…' : 'Matching…') : 'Run match'}
              </button>
            </>
          )}
        </div>

        {current && <ResultView result={current} />}

        {history.length > 1 && (
          <section aria-label="Previous results">
            <h3>Previous results</h3>
            <ul className="history">
              {history.map((h) => (
                <li key={h.id}>
                  <button type="button" className="link" aria-current={h.id === current?.id} onClick={() => setCurrent(h)}>
                    {new Date(h.createdAt).toLocaleString()} · {shortLabel(h.matcher)} · {h.resumeFilename} · {pct(h.score)}%
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </dialog>
  );
}

function ResultView({ result }: { result: MatchResult }) {
  const reqs = result.result.requirements;
  const supported = reqs.filter((r) => r.supported).length;
  const ai = isAi(result.matcher);
  const tfidf = isTfidf(result.matcher);
  const docSimilarity = result.result.meta?.docSimilarity;
  const ungrounded = result.result.meta?.ungrounded ?? 0;

  return (
    <section className="result" aria-label="Match result">
      {reqs.length === 0 ? (
        <p className="hint">
          {ai
            ? 'The AI found no concrete requirements in this job description, so there is nothing to match.'
            : tfidf
              ? 'No requirement-like lines were found. Try a job description with a Requirements section or a list of skills.'
              : 'No known skills were found in this job description, so there is nothing to match yet. The keyword matcher only knows a fixed list of skills.'}
        </p>
      ) : (
        <>
          <p className="score-line">
            <strong>{pct(result.score)}%</strong> of requirements supported ({supported} of {reqs.length}) · {result.resumeFilename}
          </p>
          <div className="meter" role="img" aria-label={`${pct(result.score)} percent supported`}>
            <span style={{ width: `${pct(result.score)}%` }} />
          </div>

          <ul className="reqs">
            {reqs.map((r) => (
              <li key={r.requirement} className={r.supported ? 'ok' : 'missing'}>
                <span className="req-name">
                  <span aria-hidden="true">{r.supported ? '✓' : '✗'}</span> {r.requirement}
                  <span className="sr-only">{r.supported ? ' (supported)' : ' (missing)'}</span>
                  {r.importance && <span className={`tag ${r.importance}`}>{r.importance}</span>}
                </span>
                {r.supported ? (
                  r.evidence.map((e) => (
                    <q key={e.line_number} className="evidence">
                      {e.line}
                    </q>
                  ))
                ) : (
                  <span className="hint">{ai ? 'No resume line shows it.' : 'No resume line mentions it.'}</span>
                )}
                {r.note && <span className="ai-note">{ai ? 'AI note' : 'Details'}: {r.note}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      {ungrounded > 0 && (
        <p className="error" role="status">
          {ungrounded} claim{ungrounded === 1 ? ' was' : 's were'} removed because the AI cited a resume line that
          does not exist.
        </p>
      )}
      <p className="hint note">
        Matcher: {matcherLabel(result.matcher)}.{' '}
        {ai
          ? 'The quoted lines are copied from your resume, but whether a line really supports a requirement is the AI’s judgement, so check them. Every requirement counts equally in the percentage.'
          : tfidf
            ? 'Requirements are split out of the job description by simple rules, and a requirement counts as supported when one resume line contains most of its distinctive words. It cannot understand synonyms, and the splitting can be wrong on unusual layouts. Resume lines that only say you are curious about or want to learn something are ignored.'
            : 'A skill counts as supported when the resume mentions it by name or a common alias, so synonyms can be missed.'}
        {tfidf && typeof docSimilarity === 'number' && <> Whole-document TF-IDF similarity: {docSimilarity.toFixed(2)} (shown for reference; not part of the percentage).</>}
      </p>
    </section>
  );
}
