'use client';

import { DragEvent, useState } from 'react';
import { Application, STATUSES, STATUS_LABEL, Status } from '../lib/api';

interface Props {
  apps: Application[];
  loading?: boolean;
  onMove: (id: string, status: Status) => void;
  onDelete: (id: string) => void;
  onMatch: (app: Application) => void;
}

const hue = (s: string) => [...s].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);
const initials = (s: string) =>
  s.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join('') || '?';

function age(iso: string) {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days < 1) return 'Today';
  if (days === 1) return 'Yesterday';
  return days < 30 ? `${days}d ago` : `${Math.floor(days / 30)}mo ago`;
}

export default function Board({ apps, loading, onMove, onDelete, onMatch }: Props) {
  const [over, setOver] = useState<Status | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);

  function drop(e: DragEvent, status: Status) {
    e.preventDefault();
    setOver(null);
    setDragId(null);
    const id = e.dataTransfer.getData('text/plain');
    const app = apps.find((a) => a.id === id);
    if (app && app.status !== status) onMove(id, status);
  }

  return (
    <section className="board" aria-label="Application board">
      {STATUSES.map((status) => {
        const items = apps.filter((a) => a.status === status);
        return (
          <div
            key={status}
            data-status={status}
            className={`column${over === status ? ' over' : ''}`}
            onDragOver={(e) => {
              e.preventDefault();
              setOver(status);
            }}
            onDragLeave={() => setOver((cur) => (cur === status ? null : cur))}
            onDrop={(e) => drop(e, status)}
          >
            <h2>
              {STATUS_LABEL[status]} <span>{items.length}</span>
            </h2>

            {loading && <div className="skeleton" aria-hidden="true" />}
            {!loading && items.length === 0 && (
              <div className="empty">{over === status ? 'Drop to move here' : 'Nothing here yet'}</div>
            )}

            {items.map((a) => (
              <article
                key={a.id}
                data-status={a.status}
                className={`card${dragId === a.id ? ' dragging' : ''}`}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData('text/plain', a.id);
                  setDragId(a.id);
                }}
                onDragEnd={() => {
                  setDragId(null);
                  setOver(null);
                }}
              >
                <div className="card-head">
                  <span className="avatar" aria-hidden="true" style={{ background: `hsl(${hue(a.company)} 55% 42%)` }}>
                    {initials(a.company)}
                  </span>
                  <div>
                    <strong className="card-title">{a.title}</strong>
                    <span className="company">{a.company}</span>
                  </div>
                </div>

                <button type="button" className="match-btn" onClick={() => onMatch(a)}>
                  Match resume
                </button>

                <div className="card-foot">
                  <span className="age">{age(a.updatedAt)}</span>
                  <div className="card-actions">
                    {/* Keyboard / touch alternative to drag and drop */}
                    <select
                      aria-label={`Move ${a.title} at ${a.company}`}
                      value={a.status}
                      onChange={(e) => onMove(a.id, e.target.value as Status)}
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {STATUS_LABEL[s]}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="icon-btn"
                      aria-label={`Delete ${a.title} at ${a.company}`}
                      onClick={() => {
                        if (window.confirm(`Delete "${a.title}" at ${a.company}?`)) onDelete(a.id);
                      }}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        );
      })}
    </section>
  );
}
