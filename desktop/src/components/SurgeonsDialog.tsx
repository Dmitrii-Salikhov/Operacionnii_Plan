import { useEffect, useMemo, useState } from 'react';
import { Modal } from './Modal';

type SurgeonsData = {
  surgeon_5: Record<string, string>;
  surgeon_7: string;
  surgeon_ma: Record<string, string>;
  forbidden_ma: string[];
  roster: string[];
};

const DAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт'];

export function SurgeonsDialog({
  data,
  onCancel,
  onSave,
}: {
  data: SurgeonsData;
  onCancel: () => void;
  onSave: (data: SurgeonsData) => void;
}) {
  const [tab, setTab] = useState<'roster' | 'schedule' | 'forbid'>('schedule');
  const [roster, setRoster] = useState(data.roster);
  const [s5, setS5] = useState({ ...data.surgeon_5 });
  const [s7, setS7] = useState(data.surgeon_7);
  const [sma, setSma] = useState({ ...data.surgeon_ma });
  const [forbidden, setForbidden] = useState(new Set(data.forbidden_ma));
  const [selected, setSelected] = useState<string | null>(null);
  const [newName, setNewName] = useState('');

  useEffect(() => {
    setRoster(data.roster);
    setS5({ ...data.surgeon_5 });
    setS7(data.surgeon_7);
    setSma({ ...data.surgeon_ma });
    setForbidden(new Set(data.forbidden_ma));
  }, [data]);

  const options = useMemo(() => [...roster].sort(), [roster]);

  const addName = () => {
    const n = newName.trim();
    if (!n || roster.includes(n)) return;
    setRoster((r) => [...r, n]);
    setNewName('');
  };

  const removeSelected = () => {
    if (!selected) return;
    setRoster((r) => r.filter((x) => x !== selected));
    setS5((prev) => {
      const next = { ...prev };
      for (const [k, v] of Object.entries(next)) {
        if (v === selected) next[k] = '';
      }
      return next;
    });
    setSma((prev) => {
      const next = { ...prev };
      for (const [k, v] of Object.entries(next)) {
        if (v === selected) next[k] = '';
      }
      return next;
    });
    if (s7 === selected) setS7('');
    setForbidden((f) => {
      const n = new Set(f);
      n.delete(selected);
      return n;
    });
    setSelected(null);
  };

  return (
    <Modal title="Настройка хирургов" wide onClose={onCancel}>
      <div className="tabs">
        <button
          type="button"
          className={`tab${tab === 'roster' ? ' tab--active' : ''}`}
          onClick={() => setTab('roster')}
        >
          Список
        </button>
        <button
          type="button"
          className={`tab${tab === 'schedule' ? ' tab--active' : ''}`}
          onClick={() => setTab('schedule')}
        >
          Расписание
        </button>
        <button
          type="button"
          className={`tab${tab === 'forbid' ? ' tab--active' : ''}`}
          onClick={() => setTab('forbid')}
        >
          Запреты М/А
        </button>
      </div>

      {tab === 'roster' ? (
        <div className="stack">
          <ul className="list">
            {options.map((name) => (
              <li
                key={name}
                className={selected === name ? 'selected' : ''}
                onClick={() => setSelected(name)}
              >
                <span>{name}</span>
              </li>
            ))}
          </ul>
          <div className="row">
            <input
              className="input"
              placeholder="ФИО"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <button type="button" className="btn" onClick={addName}>
              Добавить
            </button>
            <button type="button" className="btn" onClick={removeSelected}>
              Удалить
            </button>
          </div>
        </div>
      ) : null}

      {tab === 'schedule' ? (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th />
                {DAYS.map((d) => (
                  <th key={d}>{d}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>№5</td>
                {DAYS.map((_, i) => (
                  <td key={`5-${i}`}>
                    <select
                      className="select"
                      value={s5[String(i)] || ''}
                      onChange={(e) =>
                        setS5((prev) => ({ ...prev, [String(i)]: e.target.value }))
                      }
                    >
                      <option value="">—</option>
                      {options.map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </td>
                ))}
              </tr>
              <tr>
                <td>№7</td>
                {DAYS.map((_, i) => (
                  <td key={`7-${i}`}>
                    <select
                      className="select"
                      value={s7}
                      onChange={(e) => setS7(e.target.value)}
                    >
                      <option value="">—</option>
                      {options.map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </td>
                ))}
              </tr>
              <tr>
                <td>М/А</td>
                {DAYS.map((_, i) => (
                  <td key={`ma-${i}`}>
                    <select
                      className="select"
                      value={sma[String(i)] || ''}
                      onChange={(e) =>
                        setSma((prev) => ({ ...prev, [String(i)]: e.target.value }))
                      }
                    >
                      <option value="">—</option>
                      {options.map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      ) : null}

      {tab === 'forbid' ? (
        <ul className="list">
          {options.map((name) => (
            <li key={name}>
              <label className="check">
                <input
                  type="checkbox"
                  checked={forbidden.has(name)}
                  onChange={(e) => {
                    setForbidden((f) => {
                      const n = new Set(f);
                      if (e.target.checked) n.add(name);
                      else n.delete(name);
                      return n;
                    });
                  }}
                />
                {name}
              </label>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="modal__actions">
        <button type="button" className="btn btn--ghost" onClick={onCancel}>
          Отмена
        </button>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() =>
            onSave({
              surgeon_5: s5,
              surgeon_7: s7,
              surgeon_ma: sma,
              forbidden_ma: [...forbidden],
              roster: options,
            })
          }
        >
          Сохранить
        </button>
      </div>
    </Modal>
  );
}
