import type { ReactNode } from 'react';
import './Modal.css';

export function Modal({
  title,
  hint,
  wide,
  xl,
  children,
  onClose,
  closeOnBackdrop = true,
}: {
  title: string;
  hint?: string;
  wide?: boolean;
  /** Крупное окно (уточнение событий и т.п.) */
  xl?: boolean;
  children: ReactNode;
  onClose: () => void;
  closeOnBackdrop?: boolean;
}) {
  const sizeClass = xl ? ' modal--xl' : wide ? ' modal--wide' : '';
  return (
    <div
      className="modal-backdrop"
      onClick={closeOnBackdrop ? onClose : undefined}
      role="presentation"
    >
      <div
        className={`modal${sizeClass}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <h2>{title}</h2>
        {hint ? <p className="modal__hint">{hint}</p> : null}
        {children}
      </div>
    </div>
  );
}
