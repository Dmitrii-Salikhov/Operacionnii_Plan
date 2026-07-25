import { Modal } from './Modal';
import './SetupWizard.css';

export type SetupStatus = {
  base_dir: string;
  credentials_ok: boolean;
  credentials_path: string;
  calendars_path: string;
  calendar_ids: string[];
  calendars_ready: boolean;
  configured: boolean;
  steps: string[];
  created_credentials_stub?: boolean;
};

export function SetupWizard({
  data,
  onClose,
  onEnsureFiles,
  onOpenCalendars,
  onOpenFolder,
  onReauthorize,
}: {
  data: SetupStatus;
  onClose: () => void;
  onEnsureFiles: () => Promise<void> | void;
  onOpenCalendars: () => void;
  onOpenFolder: () => void;
  onReauthorize: () => Promise<void> | void;
}) {
  return (
    <Modal
      title="Первый запуск — настройка календаря"
      hint="Нужны credentials.json и список календарей рядом с программой. Файлы с секретами не кладите в облако."
      wide
      onClose={onClose}
    >
      <div className="wizard">
        <div className="wizard__checks">
          <div className={`wizard__check${data.credentials_ok ? ' wizard__check--ok' : ''}`}>
            {data.credentials_ok ? '✓' : '○'} credentials.json
          </div>
          <div className={`wizard__check${data.calendars_ready ? ' wizard__check--ok' : ''}`}>
            {data.calendars_ready ? '✓' : '○'} calendar_ids
            {data.calendar_ids?.length
              ? ` (${data.calendar_ids.length})`
              : ' — пусто'}
          </div>
        </div>

        <ol className="wizard__steps">
          {data.steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>

        <p className="wizard__path">
          Папка: <code>{data.base_dir}</code>
        </p>
      </div>

      <div className="modal__actions modal__actions--wrap">
        <button type="button" className="btn" onClick={() => onEnsureFiles()}>
          Создать файлы из примеров
        </button>
        <button type="button" className="btn" onClick={onOpenFolder}>
          Открыть папку программы
        </button>
        <button type="button" className="btn" onClick={onOpenCalendars}>
          Календари…
        </button>
        <button type="button" className="btn" onClick={() => onReauthorize()}>
          Переподключить Google
        </button>
        <button type="button" className="btn btn--primary" onClick={onClose}>
          {data.configured ? 'Готово' : 'Закрыть и продолжить'}
        </button>
      </div>
    </Modal>
  );
}
