'use client';

import { ChangeEvent, useState } from 'react';
import { MAX_UPLOAD_MB, Resume } from '../lib/api';

interface Props {
  resumes: Resume[];
  onUpload: (file: File) => Promise<void>;
  onDelete: (id: string) => void;
}

export default function ResumePanel({ resumes, onUpload, onDelete }: Props) {
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  async function pick(e: ChangeEvent<HTMLInputElement>) {
    const input = e.target;
    const file = input.files?.[0];
    if (!file) return;
    setLocalError(null);

    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setLocalError(`That file is over ${MAX_UPLOAD_MB} MB.`);
      input.value = '';
      return;
    }

    setBusy(true);
    try {
      await onUpload(file);
    } finally {
      setBusy(false);
      input.value = ''; // allow re-selecting the same file
    }
  }

  return (
    <details className="panel resumes" open={resumes.length === 0}>
      <summary>Resumes ({resumes.length})</summary>

      <label className="upload">
        {busy ? 'Reading your resume…' : 'Upload a resume (PDF or .txt, up to 5 MB)'}
        <input type="file" accept=".pdf,.txt,application/pdf,text/plain" onChange={pick} disabled={busy} />
      </label>
      {localError && <p className="error" role="alert">{localError}</p>}

      {resumes.length === 0 ? (
        <p className="hint">No resumes yet. Upload one to use it for matching.</p>
      ) : (
        <ul className="resume-list">
          {resumes.map((r) => (
            <li key={r.id}>
              <div className="resume-head">
                <strong>{r.filename}</strong>
                <span className="hint">{r.charCount.toLocaleString()} characters</span>
                <button
                  type="button"
                  className="link danger"
                  onClick={() => window.confirm(`Delete ${r.filename}?`) && onDelete(r.id)}
                >
                  Delete
                </button>
              </div>
              <details>
                <summary className="hint">Check the extracted text</summary>
                <pre className="preview">{r.preview}{r.charCount > r.preview.length ? '…' : ''}</pre>
              </details>
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}
