import { useMemo, useState } from 'react';
import { Modal } from './Modal';
import './WeekDialog.css';

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const MONTHS_RU = [
  'Январь',
  'Февраль',
  'Март',
  'Апрель',
  'Май',
  'Июнь',
  'Июль',
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь',
];

function mondayOf(d: Date): Date {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const day = (x.getDay() + 6) % 7;
  x.setDate(x.getDate() - day);
  return x;
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function toIso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function fmt(d: Date): string {
  return d.toLocaleDateString('ru-RU');
}

function parseIso(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function buildMonthCells(viewYear: number, viewMonth: number): Date[] {
  const first = new Date(viewYear, viewMonth, 1);
  const start = mondayOf(first);
  const cells: Date[] = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    cells.push(d);
  }
  return cells;
}

export function WeekDialog({
  initialIso,
  onCancel,
  onConfirm,
}: {
  initialIso?: string | null;
  onCancel: () => void;
  onConfirm: (mondayIso: string) => void;
}) {
  const initialMonday = useMemo(() => {
    if (initialIso) return mondayOf(parseIso(initialIso));
    return mondayOf(new Date());
  }, [initialIso]);

  const [monday, setMonday] = useState(initialMonday);
  const [view, setView] = useState({
    year: initialMonday.getFullYear(),
    month: initialMonday.getMonth(),
  });

  const cells = useMemo(
    () => buildMonthCells(view.year, view.month),
    [view.year, view.month],
  );
  const weekEnd = useMemo(() => {
    const e = new Date(monday);
    e.setDate(monday.getDate() + 6);
    return e;
  }, [monday]);
  const today = useMemo(() => new Date(), []);

  const shiftMonth = (delta: number) => {
    setView((v) => {
      const d = new Date(v.year, v.month + delta, 1);
      return { year: d.getFullYear(), month: d.getMonth() };
    });
  };

  const pickDay = (d: Date) => {
    const m = mondayOf(d);
    setMonday(m);
    setView({ year: m.getFullYear(), month: m.getMonth() });
  };

  return (
    <Modal
      title="Выберите неделю"
      hint={`Неделя: ${fmt(monday)} — ${fmt(weekEnd)} (понедельник ${fmt(monday)})`}
      onClose={onCancel}
    >
      <div className="cal">
        <div className="cal__nav">
          <button type="button" className="btn btn--ghost cal__nav-btn" onClick={() => shiftMonth(-1)}>
            ‹
          </button>
          <div className="cal__title">
            {MONTHS_RU[view.month]} {view.year}
          </div>
          <button type="button" className="btn btn--ghost cal__nav-btn" onClick={() => shiftMonth(1)}>
            ›
          </button>
        </div>

        <div className="cal__weekdays">
          {WEEKDAYS.map((w) => (
            <div key={w} className="cal__weekday">
              {w}
            </div>
          ))}
        </div>

        <div className="cal__grid">
          {cells.map((d) => {
            const inMonth = d.getMonth() === view.month;
            const isMon = sameDay(d, monday);
            const inWeek =
              d.getTime() >= monday.getTime() &&
              d.getTime() <= weekEnd.getTime();
            const isToday = sameDay(d, today);
            const cls = [
              'cal__day',
              inMonth ? '' : 'cal__day--muted',
              inWeek ? 'cal__day--week' : '',
              isMon ? 'cal__day--monday' : '',
              isToday ? 'cal__day--today' : '',
            ]
              .filter(Boolean)
              .join(' ');
            return (
              <button
                key={toIso(d)}
                type="button"
                className={cls}
                onClick={() => pickDay(d)}
              >
                {d.getDate()}
              </button>
            );
          })}
        </div>
      </div>

      <div className="modal__actions">
        <button type="button" className="btn btn--ghost" onClick={onCancel}>
          Отмена
        </button>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => onConfirm(toIso(monday))}
        >
          Загрузить
        </button>
      </div>
    </Modal>
  );
}
