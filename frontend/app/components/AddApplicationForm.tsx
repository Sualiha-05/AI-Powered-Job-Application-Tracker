'use client';

import { FormEvent, useState } from 'react';

export default function AddApplicationForm({
  onCreate,
}: {
  onCreate: (data: { company: string; title: string; jobDescription?: string }) => Promise<void>;
}) {
  const [company, setCompany] = useState('');
  const [title, setTitle] = useState('');
  const [jd, setJd] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await onCreate({ company: company.trim(), title: title.trim(), jobDescription: jd.trim() || undefined });
      setCompany('');
      setTitle('');
      setJd('');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel add" onSubmit={submit}>
      <div className="row">
        <label>
          Company
          <input value={company} onChange={(e) => setCompany(e.target.value)} required />
        </label>
        <label>
          Role
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
      </div>
      <label>
        Job description <span className="hint">(optional, used for matching later)</span>
        <textarea rows={3} value={jd} onChange={(e) => setJd(e.target.value)} />
      </label>
      <button className="primary" type="submit" disabled={busy}>
        {busy ? 'Adding…' : 'Add application'}
      </button>
    </form>
  );
}
