import type { ReactNode } from 'react';
import './Modal.css';

export function Modal({
  title,
  hint,
  wide,
  children,
  onClose,
  closeOnBackdrop = true,
}: {
  title: string;
  hint?: string;
  wide?: boolean;
  children: ReactNode;
  onClose: () => void;
  closeOnBackdrop?: boolean;
}) {
  return (
    <div
      className="modal-backdrop"
      onClick={closeOnBackdrop ? onClose : undefined}
      role="presentation"
    >
      <div
        className={`modal${wide ? ' modal--wide' : ''}`}
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
