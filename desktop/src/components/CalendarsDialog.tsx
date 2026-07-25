import { useEffect, useState } from 'react';
import { Modal } from './Modal';
import './CalendarsDialog.css';

export type CalendarsData = {
  provider: string;
  calendar_ids: string[];
  switch_steps: string[];
  configured?: boolean;
  display_name?: string;
};

export function CalendarsDialog({
  data,
  onCancel,
  onSave,
  onReauthorize,
}: {
  data: CalendarsData;
  onCancel: () => void;
  onSave: (ids: string[]) => Promise<void> | void;
  onReauthorize: () => Promise<void> | void;
}) {
  const [ids, setIds] = useState<string[]>(data.calendar_ids);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [showHelp, setShowHelp] = useState(true);

  useEffect(() => {
    setIds(data.calendar_ids);
  }, [data]);

  const addId = () => {
    const v = draft.trim();
    if (!v) return;
    if (ids.includes(v)) {
      setDraft('');
      return;
    }
    setIds((prev) => [...prev, v]);
    setDraft('');
  };

  const removeAt = (index: number) => {
    setIds((prev) => prev.filter((_, i) => i !== index));
  };

  const move = (index: number, delta: number) => {
    setIds((prev) => {
      const next = [...prev];
      const j = index + delta;
      if (j < 0 || j >= next.length) return prev;
      const tmp = next[index];
      next[index] = next[j];
      next[j] = tmp;
      return next;
    });
  };

  return (
    <Modal
      title="Календари Google"
      hint="Список ID/email, с которых загружается неделя. Можно указать несколько."
      wide
      onClose={onCancel}
    >
      <div className="calcfg">
        <div className="calcfg__list">
          {ids.length === 0 ? (
            <p className="calcfg__empty">Список пуст — добавьте хотя бы один календарь.</p>
          ) : (
            <ul className="list">
              {ids.map((id, index) => (
                <li key={`${id}-${index}`}>
                  <code className="calcfg__id">{id}</code>
                  <span className="calcfg__actions">
                    <button type="button" className="btn btn--ghost" onClick={() => move(index, -1)}>
                      ↑
                    </button>
                    <button type="button" className="btn btn--ghost" onClick={() => move(index, 1)}>
                      ↓
                    </button>
                    <button type="button" className="btn" onClick={() => removeAt(index)}>
                      Удалить
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="row">
          <input
            className="input"
            placeholder="email или ID календаря"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                addId();
              }
            }}
          />
          <button type="button" className="btn" onClick={addId}>
            Добавить
          </button>
        </div>

        <button
          type="button"
          className="btn btn--ghost calcfg__toggle"
          onClick={() => setShowHelp((v) => !v)}
        >
          {showHelp ? 'Скрыть инструкцию' : 'Как переключить календарь'}
        </button>

        {showHelp ? (
          <ol className="calcfg__steps">
            {data.switch_steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        ) : null}
      </div>

      <div className="modal__actions">
        <button
          type="button"
          className="btn"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onReauthorize();
            } finally {
              setBusy(false);
            }
          }}
        >
          Переподключить Google
        </button>
        <button type="button" className="btn btn--ghost" onClick={onCancel} disabled={busy}>
          Отмена
        </button>
        <button
          type="button"
          className="btn btn--primary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onSave(ids);
            } finally {
              setBusy(false);
            }
          }}
        >
          Сохранить
        </button>
      </div>
    </Modal>
  );
}
