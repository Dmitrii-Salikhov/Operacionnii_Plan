import { useState } from 'react';
import { Modal } from './Modal';
import { SuggestInput } from './SuggestInput';

export type ReviewRoom = '5' | '7' | 'MA';

export type ReviewRow = {
  id: number;
  name: string;
  source_text?: string;
  diagnosis_raw: string;
  diagnosis: string;
  operation: string;
  note?: string;
  room: ReviewRoom;
  confidence: number | null;
  reason: string;
  remember?: boolean;
};

const ROOM_OPTIONS: { value: ReviewRoom; label: string }[] = [
  { value: '5', label: '5' },
  { value: '7', label: '7' },
  { value: 'MA', label: 'М/А' },
];

const PLACEHOLDER_DIAG = 'диагноз не указан';
const PLACEHOLDER_OPER = 'операция не указана';

function normalizeRoom(room: string | undefined): ReviewRoom {
  if (room === '7' || room === 'MA') return room;
  return '5';
}

function isBlankDiag(value: string) {
  const v = value.trim().toLowerCase();
  return !v || v === PLACEHOLDER_DIAG;
}

function isBlankOper(value: string) {
  const v = value.trim().toLowerCase();
  return !v || v === PLACEHOLDER_OPER;
}

function clearPlaceholder(value: string, kind: 'diag' | 'oper') {
  const v = value.trim();
  if (kind === 'diag' && v.toLowerCase() === PLACEHOLDER_DIAG) return '';
  if (kind === 'oper' && v.toLowerCase() === PLACEHOLDER_OPER) return '';
  return v;
}

export function ReviewDialog({
  rows,
  diagnosisOptions,
  operationOptions,
  keyOptions = [],
  keyEntries = {},
  onCancel,
  onConfirm,
}: {
  rows: ReviewRow[];
  diagnosisOptions: string[];
  operationOptions: string[];
  keyOptions?: string[];
  /** ключ → { diagnosis, operation, note } для автозаполнения */
  keyEntries?: Record<string, { diagnosis?: string; operation?: string; note?: string }>;
  onCancel: () => void;
  onConfirm: (rows: ReviewRow[]) => void;
}) {
  const [draft, setDraft] = useState<ReviewRow[]>(() =>
    rows.map((r) => ({
      ...r,
      source_text: r.source_text || r.diagnosis_raw || '',
      diagnosis: clearPlaceholder(r.diagnosis || '', 'diag'),
      operation: clearPlaceholder(r.operation || '', 'oper'),
      note: r.note || '',
      room: normalizeRoom(r.room),
      remember: true,
    })),
  );
  const [error, setError] = useState('');

  const patch = (id: number, part: Partial<ReviewRow>) => {
    setDraft((prev) => prev.map((r) => (r.id === id ? { ...r, ...part } : r)));
  };

  const onKeyChange = (id: number, key: string) => {
    const entry = keyEntries[key];
    if (entry) {
      patch(id, {
        diagnosis_raw: key,
        diagnosis: entry.diagnosis || '',
        operation: entry.operation || '',
        note: entry.note || '',
      });
      return;
    }
    patch(id, { diagnosis_raw: key });
  };

  const handleConfirm = () => {
    for (const r of draft) {
      if (!r.remember) continue;
      if (!r.diagnosis_raw.trim() || isBlankDiag(r.diagnosis) || isBlankOper(r.operation)) {
        setError(
          `«${r.name || 'событие'}»: для сохранения в парсер укажите ключ, диагноз и операцию (можно новые, не из списка).`,
        );
        return;
      }
    }
    setError('');
    onConfirm(draft);
  };

  return (
    <Modal
      title="Уточнение нераспознанных событий"
      hint="Клик по полю открывает список; можно ввести новый диагноз/операцию. Примечание сохранится с ключом."
      xl
      onClose={onCancel}
    >
      <div className="table-wrap table-wrap--review">
        <table className="table">
          <thead>
            <tr>
              <th>ФИО</th>
              <th>Исходный текст</th>
              <th>Ключ в парсере</th>
              <th>Диагноз</th>
              <th>Операция</th>
              <th>Примечание</th>
              <th>Опер.</th>
              <th>Причина</th>
              <th>Запомнить</th>
            </tr>
          </thead>
          <tbody>
            {draft.map((r) => (
              <tr key={r.id}>
                <td>
                  <input
                    className="input"
                    value={r.name}
                    onChange={(e) => patch(r.id, { name: e.target.value })}
                  />
                </td>
                <td className="muted">{r.source_text || '—'}</td>
                <td>
                  <SuggestInput
                    value={r.diagnosis_raw}
                    options={keyOptions}
                    placeholder="фраза из календаря"
                    aria-label="Ключ в парсере"
                    onChange={(v) => onKeyChange(r.id, v)}
                  />
                </td>
                <td>
                  <SuggestInput
                    value={r.diagnosis}
                    options={diagnosisOptions}
                    placeholder="новый или из списка"
                    aria-label="Диагноз"
                    onChange={(v) => patch(r.id, { diagnosis: v })}
                  />
                </td>
                <td>
                  <SuggestInput
                    value={r.operation}
                    options={operationOptions}
                    placeholder="новая или из списка"
                    aria-label="Операция"
                    onChange={(v) => patch(r.id, { operation: v })}
                  />
                </td>
                <td>
                  <input
                    className="input"
                    value={r.note || ''}
                    placeholder="напр. Н.С."
                    onChange={(e) => patch(r.id, { note: e.target.value })}
                    title="Привязывается к ключу и попадает в «Примечания» на Поступлении"
                  />
                </td>
                <td>
                  <select
                    className="input"
                    value={r.room}
                    onChange={(e) =>
                      patch(r.id, { room: normalizeRoom(e.target.value) })
                    }
                    aria-label="Операционная"
                  >
                    {ROOM_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </td>
                <td>{r.reason}</td>
                <td>
                  <input
                    type="checkbox"
                    checked={!!r.remember}
                    onChange={(e) => patch(r.id, { remember: e.target.checked })}
                    title="Сохранить ключ → диагноз / операция / примечание в парсер"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {error ? <p className="form-error">{error}</p> : null}
      <div className="modal__actions">
        <button type="button" className="btn btn--ghost" onClick={onCancel}>
          Отмена
        </button>
        <button type="button" className="btn btn--primary" onClick={handleConfirm}>
          Продолжить
        </button>
      </div>
    </Modal>
  );
}
