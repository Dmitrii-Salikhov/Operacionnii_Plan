import { useState } from 'react';
import { Modal } from './Modal';

export type ReviewRow = {
  id: number;
  name: string;
  diagnosis_raw: string;
  diagnosis: string;
  operation: string;
  confidence: number | null;
  reason: string;
  remember?: boolean;
};

export function ReviewDialog({
  rows,
  diagnosisOptions,
  operationOptions,
  onCancel,
  onConfirm,
}: {
  rows: ReviewRow[];
  diagnosisOptions: string[];
  operationOptions: string[];
  onCancel: () => void;
  onConfirm: (rows: ReviewRow[]) => void;
}) {
  const [draft, setDraft] = useState<ReviewRow[]>(() =>
    rows.map((r) => ({ ...r, remember: true })),
  );

  const patch = (id: number, part: Partial<ReviewRow>) => {
    setDraft((prev) => prev.map((r) => (r.id === id ? { ...r, ...part } : r)));
  };

  return (
    <Modal
      title="Уточнение нераспознанных событий"
      hint="Проверьте ФИО и диагноз перед сохранением плана."
      wide
      onClose={onCancel}
    >
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>ФИО</th>
              <th>Исходный текст</th>
              <th>Диагноз</th>
              <th>Операция</th>
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
                <td>{r.diagnosis_raw}</td>
                <td>
                  <input
                    className="input"
                    list={`diag-${r.id}`}
                    value={r.diagnosis}
                    onChange={(e) => patch(r.id, { diagnosis: e.target.value })}
                  />
                  <datalist id={`diag-${r.id}`}>
                    {diagnosisOptions.map((d) => (
                      <option key={d} value={d} />
                    ))}
                  </datalist>
                </td>
                <td>
                  <input
                    className="input"
                    list={`oper-${r.id}`}
                    value={r.operation}
                    onChange={(e) => patch(r.id, { operation: e.target.value })}
                  />
                  <datalist id={`oper-${r.id}`}>
                    {operationOptions.map((d) => (
                      <option key={d} value={d} />
                    ))}
                  </datalist>
                </td>
                <td>{r.reason}</td>
                <td>
                  <input
                    type="checkbox"
                    checked={!!r.remember}
                    onChange={(e) => patch(r.id, { remember: e.target.checked })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="modal__actions">
        <button type="button" className="btn btn--ghost" onClick={onCancel}>
          Отмена
        </button>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => onConfirm(draft)}
        >
          Продолжить
        </button>
      </div>
    </Modal>
  );
}
