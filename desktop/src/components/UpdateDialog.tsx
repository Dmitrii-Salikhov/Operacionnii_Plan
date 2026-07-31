import { useEffect, useRef, useState } from 'react';
import { Modal } from './Modal';
import './UpdateDialog.css';

export type UpdateInfo = {
  current: string;
  latest: string | null;
  update_available: boolean;
  html_url?: string;
  error?: string;
  can_install?: boolean;
};

const INSTALL_STEPS = [
  { id: 'release', label: 'Данные релиза с GitHub' },
  { id: 'download', label: 'Скачивание ZIP' },
  { id: 'checksum', label: 'Проверка SHA-256' },
  { id: 'installer', label: 'Запуск установщика' },
  { id: 'restart', label: 'Перезапуск приложения' },
] as const;

type StepState = 'pending' | 'active' | 'done' | 'error';

export function UpdateDialog({
  info,
  installing,
  installError,
  installLog,
  activeStepIndex,
  onClose,
  onInstall,
  onOpenRelease,
}: {
  info: UpdateInfo;
  installing: boolean;
  installError: string | null;
  installLog: { text: string; tag?: string }[];
  activeStepIndex: number;
  onClose: () => void;
  onInstall: () => void;
  onOpenRelease: () => void;
}) {
  const logRef = useRef<HTMLDivElement | null>(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [installLog, installing]);

  function stepState(i: number): StepState {
    if (installError && i === activeStepIndex) return 'error';
    if (i < activeStepIndex) return 'done';
    if (i === activeStepIndex && (installing || installError)) return 'active';
    return 'pending';
  }

  const title = installing
    ? 'Установка обновления'
    : installError
      ? 'Ошибка обновления'
      : 'Обновления';

  return (
    <Modal
      title={title}
      hint={
        installing
          ? 'Не закрывайте программу до перезапуска.'
          : `Текущая: v${info.current}${info.latest ? ` · GitHub: v${info.latest}` : ''}`
      }
      onClose={onClose}
      closeOnBackdrop={!installing}
      wide
    >
      {!installing && !installError ? (
        <>
          {info.error ? (
            <p className="upd__msg upd__msg--err">{info.error}</p>
          ) : info.update_available ? (
            <p className="upd__msg upd__msg--ok">
              Доступна новая версия. Перед установкой архив проверяется по SHA-256.
            </p>
          ) : (
            <p className="upd__msg">У вас актуальная версия.</p>
          )}
        </>
      ) : null}

      {installing || installError || installLog.length > 0 ? (
        <div className="upd__body">
          <ol className="upd__steps">
            {INSTALL_STEPS.map((s, i) => {
              const st = stepState(i);
              return (
                <li key={s.id} className={`upd__step upd__step--${st}`}>
                  <span className="upd__step-mark" aria-hidden>
                    {st === 'done' ? '✓' : st === 'error' ? '!' : st === 'active' ? '…' : '○'}
                  </span>
                  <span>{s.label}</span>
                </li>
              );
            })}
          </ol>
          <div className="upd__log" ref={logRef}>
            {installLog.length === 0 ? (
              <p className="upd__log-line upd__log-line--info">Ожидание…</p>
            ) : (
              installLog.map((line, i) => (
                <p
                  key={`${i}-${line.text.slice(0, 20)}`}
                  className={`upd__log-line upd__log-line--${line.tag || 'info'}`}
                >
                  {line.text}
                </p>
              ))
            )}
          </div>
        </div>
      ) : null}

      {installError ? <p className="upd__msg upd__msg--err">{installError}</p> : null}

      <div className="modal__actions">
        {!installing && info.update_available && info.can_install && !installError ? (
          confirming ? (
            <>
              <span className="upd__confirm">Установить и перезапустить?</span>
              <button type="button" className="btn btn--primary" onClick={onInstall}>
                Да, установить
              </button>
              <button type="button" className="btn btn--ghost" onClick={() => setConfirming(false)}>
                Отмена
              </button>
            </>
          ) : (
            <button type="button" className="btn btn--primary" onClick={() => setConfirming(true)}>
              Скачать и установить
            </button>
          )
        ) : null}
        {!installing && info.html_url ? (
          <button type="button" className="btn" onClick={onOpenRelease}>
            Открыть релиз
          </button>
        ) : null}
        {!installing ? (
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Закрыть
          </button>
        ) : (
          <span className="upd__wait">Идёт установка…</span>
        )}
      </div>
    </Modal>
  );
}

export { INSTALL_STEPS };
