'use client';

import { DragEvent, useState } from 'react';
import { Application, STATUSES, STATUS_LABEL, Status } from '../lib/api';

interface Props {
  apps: Application[];
  onMove: (id: string, status: Status) => void;
  onDelete: (id: string) => void;
  onMatch: (app: Application) => void;
}

export default function Board({ apps, onMove, onDelete, onMatch }: Props) {
  const [over, setOver] = useState<Status | null>(null);

  function drop(e: DragEvent, status: Status) {
    e.preventDefault();
    setOver(null);
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

            {items.length === 0 && <div className="empty">No applications here yet.</div>}

            {items.map((a) => (
              <article
                key={a.id}
                className="card"
                draggable
                onDragStart={(e) => e.dataTransfer.setData('text/plain', a.id)}
              >
                <strong>{a.title}</strong>
                <span className="company">{a.company}</span>

                <button type="button" className="match-btn" onClick={() => onMatch(a)}>
                  Match resume
                </button>

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
                    className="link danger"
                    onClick={() => {
                      if (window.confirm(`Delete "${a.title}" at ${a.company}?`)) onDelete(a.id);
                    }}
                  >
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        );
      })}
    </section>
  );
}
