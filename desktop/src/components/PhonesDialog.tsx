import { useState } from 'react';
import { Modal } from './Modal';

export type PhoneFormat = 'with_7' | 'without_7';

export function PhonesDialog({
  onCancel,
  onConfirm,
}: {
  onCancel: () => void;
  onConfirm: (format: PhoneFormat) => void;
}) {
  const [format, setFormat] = useState<PhoneFormat>('with_7');

  return (
    <Modal
      title="Выгрузка телефонов"
      hint="Выберите формат номера в Excel."
      onClose={onCancel}
    >
      <div className="stack" style={{ gap: 10 }}>
        <label className="check">
          <input
            type="radio"
            name="phone-fmt"
            checked={format === 'with_7'}
            onChange={() => setFormat('with_7')}
          />
          С кодом страны: <code>79573332211</code>
        </label>
        <label className="check">
          <input
            type="radio"
            name="phone-fmt"
            checked={format === 'without_7'}
            onChange={() => setFormat('without_7')}
          />
          Без «7»: <code>9573332211</code>
        </label>
      </div>
      <div className="modal__actions">
        <button type="button" className="btn btn--ghost" onClick={onCancel}>
          Отмена
        </button>
        <button type="button" className="btn btn--primary" onClick={() => onConfirm(format)}>
          Выгрузить
        </button>
      </div>
    </Modal>
  );
}
