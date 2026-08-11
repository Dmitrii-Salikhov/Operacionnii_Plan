import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

type ListRect = { top: number; left: number; width: number };

/** Свободный ввод + выпадающий список по клику/фокусу (можно значение не из списка). */
export function SuggestInput({
  value,
  options,
  placeholder,
  onChange,
  'aria-label': ariaLabel,
}: {
  value: string;
  options: string[];
  placeholder?: string;
  onChange: (value: string) => void;
  'aria-label'?: string;
}) {
  const listId = useId();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const listRef = useRef<HTMLUListElement | null>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [listRect, setListRect] = useState<ListRect | null>(null);

  const filtered = useMemo(() => {
    const q = value.trim().toLowerCase();
    if (!q) return options.slice(0, 80);
    const starts = options.filter((o) => o.toLowerCase().startsWith(q));
    const contains = options.filter(
      (o) => !o.toLowerCase().startsWith(q) && o.toLowerCase().includes(q),
    );
    return [...starts, ...contains].slice(0, 80);
  }, [options, value]);

  const updateListRect = () => {
    const input = rootRef.current?.querySelector('input');
    if (!input) return;
    const r = input.getBoundingClientRect();
    setListRect({
      top: r.bottom + 2,
      left: r.left,
      width: r.width,
    });
  };

  useEffect(() => {
    if (!open) {
      setListRect(null);
      return;
    }
    updateListRect();
    const onReposition = () => updateListRect();
    window.addEventListener('scroll', onReposition, true);
    window.addEventListener('resize', onReposition);
    return () => {
      window.removeEventListener('scroll', onReposition, true);
      window.removeEventListener('resize', onReposition);
    };
  }, [open, filtered]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (rootRef.current?.contains(t) || listRef.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  useEffect(() => {
    setActive(0);
  }, [filtered, open]);

  const pick = (opt: string) => {
    onChange(opt);
    setOpen(false);
  };

  const list =
    open && filtered.length > 0 && listRect
      ? createPortal(
          <ul
            id={listId}
            ref={listRef}
            className="suggest__list"
            role="listbox"
            style={{
              top: listRect.top,
              left: listRect.left,
              width: listRect.width,
            }}
          >
            {filtered.map((opt, i) => (
              <li
                key={opt}
                role="option"
                aria-selected={i === active}
                className={
                  i === active ? 'suggest__item suggest__item--active' : 'suggest__item'
                }
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(opt);
                }}
                onMouseEnter={() => setActive(i)}
              >
                {opt}
              </li>
            ))}
          </ul>,
          document.body,
        )
      : null;

  return (
    <div className="suggest" ref={rootRef}>
      <input
        className="input"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-label={ariaLabel}
        value={value}
        placeholder={placeholder}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onClick={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            setOpen(false);
            return;
          }
          if (!open && (e.key === 'ArrowDown' || e.key === 'Enter')) {
            setOpen(true);
            return;
          }
          if (!open || filtered.length === 0) return;
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActive((i) => Math.min(i + 1, filtered.length - 1));
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (e.key === 'Enter') {
            e.preventDefault();
            pick(filtered[active]);
          }
        }}
      />
      {list}
    </div>
  );
}
