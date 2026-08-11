import { useCallback, useEffect, useRef, useState } from 'react';
import { ReviewDialog, type ReviewRow } from './components/ReviewDialog';
import { SurgeonsDialog } from './components/SurgeonsDialog';
import { WeekDialog } from './components/WeekDialog';
import { CalendarsDialog, type CalendarsData } from './components/CalendarsDialog';
import { SetupWizard, type SetupStatus } from './components/SetupWizard';
import { UpdateDialog, INSTALL_STEPS, type UpdateInfo } from './components/UpdateDialog';
import { PhonesDialog, type PhoneFormat } from './components/PhonesDialog';
import './App.css';

type LogLine = { text: string; tag: string };
type Theme = 'dark' | 'light';
type GenStep = 'idle' | 'parse' | 'distribute' | 'excel' | 'done';

const LOG_MAX = 320;
const LOG_KEEP = 240;

type CalendarStatus = {
  configured: boolean;
  display_name: string;
  help: string;
  provider?: string;
  calendar_ids?: string[];
  switch_steps?: string[];
};

type CalendarCount = { calendar_id: string; count: number };

type PrepareResult = {
  week_start: string;
  week_end: string;
  default_filename: string;
  reviews: ReviewRow[];
  diagnosis_options: string[];
  operation_options: string[];
  key_options?: string[];
  key_entries?: Record<string, { diagnosis?: string; operation?: string; note?: string }>;
  logs: { message: string; tag: string }[];
};

function api() {
  if (!window.plan) throw new Error('Electron bridge недоступен (window.plan)');
  return window.plan;
}

async function rpc<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
  return (await api().rpc(method, params)) as T;
}

function nowStamp(): string {
  return new Date().toLocaleString('ru-RU');
}

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme);
}

export default function App() {
  const [version, setVersion] = useState('?.?.?');
  const [status, setStatus] = useState('Выберите источник данных');
  const [logs, setLogs] = useState<LogLine[]>([]);
  const logEndRef = useRef<HTMLDivElement | null>(null);
  const logBoxRef = useRef<HTMLDivElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [genStep, setGenStep] = useState<GenStep>('idle');
  const [exportAdmissions, setExportAdmissions] = useState(false);
  const [excelPath, setExcelPath] = useState('');
  const [sourceLabel, setSourceLabel] = useState('');
  const [hasSource, setHasSource] = useState(false);
  const [lastMonday, setLastMonday] = useState<string | null>(null);
  const [calendar, setCalendar] = useState<CalendarStatus | null>(null);
  const [calendarCounts, setCalendarCounts] = useState<CalendarCount[]>([]);
  const [calendarsOpen, setCalendarsOpen] = useState<CalendarsData | null>(null);
  const [setupOpen, setSetupOpen] = useState<SetupStatus | null>(null);
  const [phonesOpen, setPhonesOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>('dark');
  const [bridgeOk, setBridgeOk] = useState(false);

  const [weekOpen, setWeekOpen] = useState(false);
  const [review, setReview] = useState<PrepareResult | null>(null);
  const [surgeons, setSurgeons] = useState<{
    surgeon_5: Record<string, string>;
    surgeon_7: string;
    surgeon_ma: Record<string, string>;
    forbidden_ma: string[];
    roster: string[];
  } | null>(null);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [updateInstalling, setUpdateInstalling] = useState(false);
  const [updateInstallError, setUpdateInstallError] = useState<string | null>(null);
  const [updateInstallLog, setUpdateInstallLog] = useState<LogLine[]>([]);
  const [updateStepIndex, setUpdateStepIndex] = useState(0);

  const pushLog = useCallback((message: string, tag = 'info') => {
    const line = { text: `[${nowStamp()}] ${message}`, tag };
    setLogs((prev) => {
      const next = [...prev, line];
      return next.length > LOG_MAX ? next.slice(-LOG_KEEP) : next;
    });
  }, []);

  const pushUpdateLog = useCallback((message: string, tag = 'info') => {
    const line = { text: `[${nowStamp()}] ${message}`, tag };
    setUpdateInstallLog((prev) => {
      const next = [...prev, line];
      return next.length > 80 ? next.slice(-60) : next;
    });
    setLogs((prev) => {
      const next = [...prev, line];
      return next.length > LOG_MAX ? next.slice(-LOG_KEEP) : next;
    });
  }, []);

  const pushError = useCallback(
    (e: unknown) => {
      const text = e instanceof Error ? e.message : String(e);
      const first = text.split('\n')[0];
      pushLog(first, 'error');
      const rest = text.split('\n').slice(1).join('\n').trim();
      if (rest) pushLog(rest.slice(0, 500), 'warning');
    },
    [pushLog],
  );

  useEffect(() => {
    const box = logBoxRef.current;
    if (!box) {
      logEndRef.current?.scrollIntoView({ block: 'end' });
      return;
    }
    // Двойной rAF — после layout, чтобы всегда уезжать вниз.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        box.scrollTop = box.scrollHeight;
      });
    });
  }, [logs]);

  const refreshCalendar = useCallback(async () => {
    const cal = await rpc<CalendarStatus>('calendar.status');
    setCalendar(cal);
    return cal;
  }, []);

  async function onExportDictionary() {
    try {
      const path = await api().saveJsonDialog({
        defaultPath: 'custom_diagnoses.json',
      });
      if (!path) return;
      const res = await rpc<{ count: number }>('diag.export', { path });
      pushLog(`Экспорт словаря: ${res.count}`, 'success');
    } catch (e) {
      pushError(e);
    }
  }

  async function onImportDictionary() {
    try {
      const path = await api().openJsonDialog();
      if (!path) return;
      const res = await rpc<{ count: number }>('diag.import', { path });
      pushLog(`Импорт словаря: ${res.count}`, 'success');
    } catch (e) {
      pushError(e);
    }
  }

  async function openSurgeonsDialog() {
    try {
      setSurgeons(
        (await rpc('surgeons.get')) as {
          surgeon_5: Record<string, string>;
          surgeon_7: string;
          surgeon_ma: Record<string, string>;
          forbidden_ma: string[];
          roster: string[];
        },
      );
    } catch (e) {
      pushError(e);
    }
  }

  async function openSetupWizard() {
    try {
      setSetupOpen(await rpc<SetupStatus>('setup.status'));
    } catch (e) {
      pushError(e);
    }
  }

  async function openBaseDir() {
    try {
      const st = await rpc<SetupStatus>('setup.status');
      if (st?.base_dir) await api().openPath(st.base_dir);
    } catch (e) {
      pushError(e);
    }
  }

  function clearJournal() {
    setLogs([{ text: `[${nowStamp()}] Журнал очищен.`, tag: 'info' }]);
  }

  async function setExportAdmissionsOption(next: boolean) {
    setExportAdmissions(next);
    try {
      await rpc('config.save', { export_admissions: next });
      await api().syncExportAdmissionsMenu(next);
    } catch (e) {
      pushError(e);
    }
  }

  const menuHandlersRef = useRef({
    busy: false,
    hasSource: false,
    version: '?.?.?',
    onPickExcel,
    onGenerate,
    onExportDictionary,
    onImportDictionary,
    onExportPhones: () => setPhonesOpen(true),
    onPickWeek: () => setWeekOpen(true),
    openCalendarsDialog,
    onReconnect,
    openSurgeonsDialog,
    openSetupWizard,
    toggleTheme,
    clearJournal,
    onCheckUpdates,
    openBaseDir,
    setExportAdmissionsOption,
  });

  menuHandlersRef.current = {
    busy,
    hasSource,
    version,
    onPickExcel,
    onGenerate,
    onExportDictionary,
    onImportDictionary,
    onExportPhones: () => setPhonesOpen(true),
    onPickWeek: () => setWeekOpen(true),
    openCalendarsDialog,
    onReconnect,
    openSurgeonsDialog,
    openSetupWizard,
    toggleTheme,
    clearJournal,
    onCheckUpdates,
    openBaseDir,
    setExportAdmissionsOption,
  };

  useEffect(() => {
    const unsub = window.plan?.onMenuAction?.((action) => {
      const h = menuHandlersRef.current;
      if (h.busy && action !== 'about' && action !== 'clear-log') return;

      switch (action) {
        case 'open-excel':
          void h.onPickExcel();
          break;
        case 'generate-plan':
          if (h.hasSource) void h.onGenerate();
          break;
        case 'export-dictionary':
          void h.onExportDictionary();
          break;
        case 'import-dictionary':
          void h.onImportDictionary();
          break;
        case 'export-phones':
          if (h.hasSource) h.onExportPhones();
          break;
        case 'pick-week':
          h.onPickWeek();
          break;
        case 'calendars':
          void h.openCalendarsDialog();
          break;
        case 'reconnect-oauth':
          void h.onReconnect();
          break;
        case 'surgeons':
          void h.openSurgeonsDialog();
          break;
        case 'setup-wizard':
          void h.openSetupWizard();
          break;
        case 'toggle-theme':
          void h.toggleTheme();
          break;
        case 'clear-log':
          h.clearJournal();
          break;
        case 'check-updates':
          void h.onCheckUpdates();
          break;
        case 'open-base-dir':
          void h.openBaseDir();
          break;
        case 'about':
          window.alert(`План операций ЛОР\nВерсия v${h.version}`);
          break;
        default:
          if (action.startsWith('toggle-admissions:')) {
            const checked = action.endsWith(':true');
            void h.setExportAdmissionsOption(checked);
          }
          break;
      }
    });
    void window.plan?.menuReady?.();
    return () => {
      unsub?.();
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const st = await api().getBridgeStatus();
        if (!cancelled) setBridgeOk(!!st.ok);
        const ver = await api().getAppVersion();
        if (!cancelled) setVersion(ver);
        const cfg = await rpc<{
          export_admissions: boolean;
          last_monday: string | null;
          version: string;
          ui_appearance?: string;
        }>('config.get');
        if (cancelled) return;
        setExportAdmissions(!!cfg.export_admissions);
        await api().syncExportAdmissionsMenu(!!cfg.export_admissions);
        setLastMonday(cfg.last_monday);
        setVersion(cfg.version || ver);
        const nextTheme: Theme = cfg.ui_appearance === 'Light' ? 'light' : 'dark';
        setTheme(nextTheme);
        applyTheme(nextTheme);
        await refreshCalendar();
        const setup = await rpc<SetupStatus>('setup.status');
        if (!cancelled && !setup.configured) setSetupOpen(setup);
        const tail = await rpc<{ lines: LogLine[] }>('log.tail', { lines: 200 });
        if (!cancelled && tail.lines?.length) {
          const cleaned =
            tail.lines.length > LOG_MAX ? tail.lines.slice(-LOG_KEEP) : tail.lines;
          setLogs(cleaned.map((l) => ({ text: l.text, tag: l.tag || 'info' })));
        }
        pushLog('Готов к работе.', 'success');
      } catch (e) {
        if (!cancelled) {
          setBridgeOk(false);
          pushError(e);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pushLog, pushError, refreshCalendar]);

  async function toggleTheme() {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    applyTheme(next);
    try {
      await rpc('config.save', { ui_appearance: next === 'light' ? 'Light' : 'Dark' });
    } catch (e) {
      pushError(e);
    }
  }

  async function onPickWeek(mondayIso: string) {
    setWeekOpen(false);
    setBusy(true);
    try {
      const res = await rpc<{
        count: number;
        week_start: string;
        week_end: string;
        empty: boolean;
        by_calendar?: CalendarCount[];
      }>('calendar.fetch_week', { monday: mondayIso });
      setLastMonday(res.week_start);
      setExcelPath('');
      setCalendarCounts(res.by_calendar || []);
      if (res.empty) {
        setSourceLabel('');
        setHasSource(false);
        setStatus('На выбранную неделю нет событий.');
        pushLog('На выбранную неделю нет событий.', 'warning');
      } else {
        setHasSource(true);
        setSourceLabel(`Календарь · ${res.week_start} — ${res.week_end} (${res.count})`);
        setStatus(`Загружена неделя. Нажмите «Сформировать план».`);
        pushLog(`События загружены (${res.count}).`, 'success');
        for (const row of res.by_calendar || []) {
          pushLog(`  ${row.calendar_id}: ${row.count}`, 'info');
        }
      }
      await refreshCalendar();
    } catch (e) {
      pushError(e);
    } finally {
      setBusy(false);
    }
  }

  async function onPickExcel() {
    const path = await api().openExcelDialog();
    if (!path) return;
    setBusy(true);
    try {
      const res = await rpc<{ path: string; name: string }>('source.set_excel', { path });
      setExcelPath(res.path);
      setCalendarCounts([]);
      setHasSource(true);
      setSourceLabel(`Excel · ${res.name}`);
      setStatus('Файл выбран. Нажмите «Сформировать план».');
      pushLog(`Выбран файл: ${res.name}`, 'info');
    } catch (e) {
      pushError(e);
    } finally {
      setBusy(false);
    }
  }

  async function finishExport(prepared: PrepareResult, reviews: ReviewRow[]) {
    const out = await api().saveExcelDialog({ defaultPath: prepared.default_filename });
    if (!out) {
      pushLog('Сохранение отменено.', 'warning');
      setReview(null);
      setGenStep('idle');
      return;
    }
    setBusy(true);
    setGenStep('excel');
    try {
      const res = await rpc<{
        output_path: string;
        admissions_path: string | null;
        logs: { message: string; tag: string }[];
      }>('plan.export', {
        output_path: out,
        reviews,
        export_admissions: exportAdmissions,
        open_folder: false,
      });
      for (const item of res.logs || []) pushLog(item.message, item.tag || 'info');
      setGenStep('done');
      setStatus(`План сохранён: ${res.output_path.split(/[/\\]/).pop()}`);
      pushLog('План операций сохранён.', 'success');
      if (res.admissions_path) pushLog(`Список поступлений: ${res.admissions_path}`, 'success');
      if (window.confirm('План сохранён. Открыть папку?')) {
        await api().openPath(out.replace(/[/\\][^/\\]+$/, ''));
      }
    } catch (e) {
      pushError(e);
      setGenStep('idle');
    } finally {
      setBusy(false);
      setReview(null);
      setTimeout(() => setGenStep('idle'), 1200);
    }
  }

  async function onGenerate() {
    setBusy(true);
    setGenStep('parse');
    try {
      setGenStep('distribute');
      const prepared = await rpc<PrepareResult>('plan.prepare');
      for (const item of prepared.logs || []) pushLog(item.message, item.tag || 'info');
      if (prepared.reviews?.length) {
        setReview(prepared);
        setBusy(false);
      } else {
        await finishExport(prepared, []);
      }
    } catch (e) {
      pushError(e);
      setGenStep('idle');
      setBusy(false);
    }
  }

  async function onReconnect() {
    setBusy(true);
    try {
      await rpc('calendar.reauthorize');
      pushLog('Календарь переподключён.', 'success');
      await refreshCalendar();
    } catch (e) {
      pushError(e);
    } finally {
      setBusy(false);
    }
  }

  async function openCalendarsDialog() {
    try {
      setCalendarsOpen(await rpc<CalendarsData>('calendar.list'));
    } catch (e) {
      pushError(e);
    }
  }

  async function onCheckUpdates() {
    setBusy(true);
    setUpdateInstallError(null);
    setUpdateInstallLog([]);
    setUpdateStepIndex(0);
    setUpdateInstalling(false);
    pushLog('Проверка обновлений на GitHub…', 'info');
    try {
      const info = await rpc<UpdateInfo>('updates.check');
      setUpdateInfo(info);
      if (info.error) {
        pushLog(`Обновления: ${info.error}`, 'error');
      } else if (info.update_available) {
        pushLog(
          `Доступна версия v${info.latest} (сейчас v${info.current}).`,
          'success',
        );
      } else {
        pushLog(`Актуальная версия v${info.current}.`, 'success');
      }
    } catch (e) {
      pushError(e);
    } finally {
      setBusy(false);
    }
  }

  async function onInstallUpdate() {
    if (!updateInfo) return;
    setBusy(true);
    setUpdateInstalling(true);
    setUpdateInstallError(null);
    setUpdateInstallLog([]);
    setUpdateStepIndex(0);

    let step = 0;
    const advance = (msg: string, tag = 'info') => {
      setUpdateStepIndex(step);
      pushUpdateLog(msg, tag);
      step = Math.min(step + 1, INSTALL_STEPS.length - 1);
    };

    const ticker = window.setInterval(() => {
      setUpdateStepIndex((i) => Math.min(i + 1, INSTALL_STEPS.length - 2));
    }, 2800);

    try {
      advance('Запрос данных релиза…');
      advance('Скачивание PlanOperaciy-Windows.zip…');
      pushUpdateLog(
        'Идёт скачивание и проверка SHA-256 (архив большой, 2–10 мин — это нормально)…',
        'info',
      );
      setUpdateStepIndex(2); // checksum — реальный прогресс внутри одного RPC

      const res = await rpc<{
        ok: boolean;
        error?: string;
        restarting?: boolean;
        sha256?: string;
      }>('updates.install');

      window.clearInterval(ticker);

      if (!res.ok) {
        setUpdateStepIndex((i) => i);
        setUpdateInstallError(res.error || 'Ошибка установки обновления');
        pushUpdateLog(res.error || 'Ошибка установки обновления', 'error');
        setUpdateInstalling(false);
        return;
      }

      setUpdateStepIndex(INSTALL_STEPS.length - 2);
      if (res.sha256) {
        pushUpdateLog(`SHA-256 OK: ${res.sha256.slice(0, 16)}…`, 'success');
      }
      pushUpdateLog('Установщик запущен. Перезапуск…', 'success');
      setUpdateStepIndex(INSTALL_STEPS.length - 1);
      await api().quitAfterUpdate();
    } catch (e) {
      window.clearInterval(ticker);
      const text = e instanceof Error ? e.message : String(e);
      setUpdateInstallError(text);
      pushUpdateLog(text, 'error');
      setUpdateInstalling(false);
    } finally {
      window.clearInterval(ticker);
      setBusy(false);
    }
  }

  async function onExportPhones(format: PhoneFormat) {
    setPhonesOpen(false);
    setBusy(true);
    try {
      const out = await api().saveExcelDialog({ defaultPath: 'Телефоны.xlsx' });
      if (!out) return;
      const res = await rpc<{ count: number; format: string }>('phones.extract', {
        output_path: out,
        format,
      });
      pushLog(
        `Телефоны: ${res.count} (формат ${res.format === 'without_7' ? 'без 7' : 'с 7'})`,
        'success',
      );
      await api().openPath(out.replace(/[/\\][^/\\]+$/, ''));
    } catch (e) {
      pushError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <span className="app__logo">План операций ЛОР</span>
          <span className="app__version">v{version}</span>
        </div>
        <div className="toolbar">
          <div className="toolbar__row">
            <div className="toolbar__group">
              <button
                type="button"
                className="btn"
                title="Выбрать Excel-файл экспорта календаря"
                disabled={busy}
                onClick={onPickExcel}
              >
                Excel
              </button>
              <button
                type="button"
                className="btn"
                title="Сохранить словарь диагнозов в JSON-файл"
                disabled={busy}
                onClick={() => void onExportDictionary()}
              >
                Экспорт словаря
              </button>
              <button
                type="button"
                className="btn"
                title="Загрузить словарь диагнозов из JSON-файла"
                disabled={busy}
                onClick={() => void onImportDictionary()}
              >
                Импорт
              </button>
            </div>
            <div className="toolbar__group">
              <button
                type="button"
                className="btn"
                title="Выбрать неделю и загрузить события из Google Календаря"
                disabled={busy || !calendar?.configured}
                onClick={() => setWeekOpen(true)}
              >
                Неделя
              </button>
              <button
                type="button"
                className="btn"
                title="Выбрать календари Google и посмотреть число событий"
                disabled={busy}
                onClick={openCalendarsDialog}
              >
                Календари
              </button>
              <button
                type="button"
                className="btn"
                title="Повторно подключить Google аккаунт (OAuth)"
                disabled={busy || !calendar?.configured}
                onClick={onReconnect}
              >
                OAuth
              </button>
            </div>
          </div>
          <div className="toolbar__row">
            <div className="toolbar__group">
              <button
                type="button"
                className="btn"
                title="Настроить хирургов, расписание и ограничения"
                disabled={busy}
                onClick={() => void openSurgeonsDialog()}
              >
                Хирурги
              </button>
              <button
                type="button"
                className="btn"
                title={
                  theme === 'dark'
                    ? 'Переключить на светлую тему'
                    : 'Переключить на тёмную тему'
                }
                disabled={busy}
                onClick={toggleTheme}
              >
                {theme === 'dark' ? 'Светлая' : 'Тёмная'}
              </button>
              <button
                type="button"
                className="btn"
                title="Проверить наличие новой версии приложения"
                disabled={busy}
                onClick={onCheckUpdates}
              >
                Обновления
              </button>
              <button
                type="button"
                className="btn"
                title="Мастер первой настройки календаря и доступа"
                disabled={busy}
                onClick={() => void openSetupWizard()}
              >
                Мастер
              </button>
            </div>
          </div>
        </div>
        <span className="app__version">{bridgeOk ? 'ok' : 'bridge?'}</span>
      </header>
      {busy ? <div className="busy" /> : null}

      <div className="app__body">
        <main className="app__main">
          {!hasSource ? (
            <div className="empty">
              <h2 className="empty__title">Нет источника данных</h2>
              <p className="empty__hint">
                Загрузите неделю из Google Календаря или выберите Excel-файл экспорта.
              </p>
              <div className="empty__actions">
                <button
                  type="button"
                  className="btn btn--primary"
                  title="Выбрать неделю и загрузить события из Google Календаря"
                  disabled={busy || !calendar?.configured}
                  onClick={() => setWeekOpen(true)}
                >
                  Выбрать неделю
                </button>
                <button
                  type="button"
                  className="btn"
                  title="Открыть Excel-файл экспорта календаря"
                  disabled={busy}
                  onClick={onPickExcel}
                >
                  Открыть Excel
                </button>
              </div>
            </div>
          ) : null}

          {genStep !== 'idle' ? (
            <div className="steps">
              {(
                [
                  ['parse', 'Парсинг'],
                  ['distribute', 'Распределение'],
                  ['excel', 'Excel'],
                  ['done', 'Готово'],
                ] as const
              ).map(([id, label]) => {
                const order = ['parse', 'distribute', 'excel', 'done'];
                const cur = order.indexOf(genStep);
                const idx = order.indexOf(id);
                const cls =
                  idx < cur ? 'step step--done' : idx === cur ? 'step step--active' : 'step';
                return (
                  <span key={id} className={cls}>
                    {label}
                  </span>
                );
              })}
            </div>
          ) : null}

          <div className="grid-2">
            <section className="panel">
              <h3 className="panel__title">
                Календарь
                {calendar?.display_name ? ` · ${calendar.display_name}` : ''}
              </h3>
              <div className="stack">
                {sourceLabel ? <p className="status">{sourceLabel}</p> : null}
                {calendar?.calendar_ids && calendar.calendar_ids.length > 0 ? (
                  <ul className="cal-stats">
                    {calendar.calendar_ids.map((id) => {
                      const hit = calendarCounts.find((c) => c.calendar_id === id);
                      return (
                        <li key={id}>
                          <span>{id}</span>
                          <span className="cal-stats__count">{hit ? hit.count : '—'}</span>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p className="status">Календари не заданы — откройте «Календари» в панели.</p>
                )}
                <button
                  type="button"
                  className="btn btn--primary btn--block btn--lg"
                  title="Распределить операции и сохранить план в Excel"
                  disabled={busy || !hasSource}
                  onClick={onGenerate}
                >
                  Сформировать план
                </button>
                <button
                  type="button"
                  className="btn btn--block btn--lg"
                  title="Выгрузить телефоны пациентов в Excel (с 7 или без)"
                  disabled={busy || !hasSource}
                  onClick={() => setPhonesOpen(true)}
                >
                  Выгрузить телефоны
                </button>
              </div>
            </section>

            <section className="panel">
              <h3 className="panel__title">Excel / опции</h3>
              <div className="stack">
                <input
                  className="input input--readonly"
                  readOnly
                  value={excelPath}
                  placeholder="Файл не выбран"
                />
                <label className="check">
                  <input
                    type="checkbox"
                    checked={exportAdmissions}
                    onChange={async (e) => {
                      await setExportAdmissionsOption(e.target.checked);
                    }}
                  />
                  Также «Список поступлений ЛОР»
                </label>
              </div>
            </section>
          </div>

          <p className="status">{status}</p>
        </main>

        <aside className="app__aside">
          <div className="aside__head">
            <h3 className="aside__title">Журнал</h3>
            <div className="aside__actions">
              <span className="aside__meta" title="Строк в журнале (старые удаляются автоматически)">
                {logs.length}
              </span>
              <button
                type="button"
                className="btn btn--ghost aside__clear"
                title="Очистить журнал на экране"
                disabled={busy || logs.length === 0}
                onClick={clearJournal}
              >
                Очистить
              </button>
            </div>
          </div>
          <div className="log" ref={logBoxRef}>
            {logs.length === 0 ? (
              <p className="log__line log__line--info">Пока пусто — действия появятся здесь.</p>
            ) : (
              logs.map((line, i) => (
                <p
                  key={`${i}-${line.text.slice(0, 32)}`}
                  className={`log__line log__line--${line.tag || 'info'}`}
                >
                  <span className="log__tag">{(line.tag || 'info').toUpperCase()}</span>
                  {line.text}
                </p>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </aside>
      </div>

      {phonesOpen ? (
        <PhonesDialog onCancel={() => setPhonesOpen(false)} onConfirm={onExportPhones} />
      ) : null}

      {weekOpen ? (
        <WeekDialog
          initialIso={lastMonday}
          onCancel={() => setWeekOpen(false)}
          onConfirm={onPickWeek}
        />
      ) : null}

      {calendarsOpen ? (
        <CalendarsDialog
          data={calendarsOpen}
          onCancel={() => setCalendarsOpen(null)}
          onReauthorize={onReconnect}
          onSave={async (ids) => {
            await rpc('calendar.set_ids', { calendar_ids: ids });
            setCalendarsOpen(null);
            setCalendarCounts([]);
            await refreshCalendar();
            pushLog(
              ids.length ? `Календари сохранены (${ids.length})` : 'Список календарей очищен',
              'success',
            );
          }}
        />
      ) : null}

      {setupOpen ? (
        <SetupWizard
          data={setupOpen}
          onClose={() => setSetupOpen(null)}
          onEnsureFiles={async () => {
            const res = await rpc<SetupStatus>('setup.ensure_files');
            setSetupOpen(res);
            pushLog(
              res.created_credentials_stub
                ? 'Созданы файлы-заготовки. Заполните credentials.json.'
                : 'Проверены файлы конфигурации.',
              'info',
            );
          }}
          onOpenCalendars={() => {
            setSetupOpen(null);
            void openCalendarsDialog();
          }}
          onOpenFolder={() => api().openPath(setupOpen.base_dir)}
          onReauthorize={onReconnect}
        />
      ) : null}

      {review ? (
        <ReviewDialog
          rows={review.reviews}
          diagnosisOptions={review.diagnosis_options}
          operationOptions={review.operation_options}
          keyOptions={review.key_options || []}
          keyEntries={review.key_entries || {}}
          onCancel={() => {
            setReview(null);
            setGenStep('idle');
          }}
          onConfirm={(rows) => finishExport(review, rows)}
        />
      ) : null}

      {surgeons ? (
        <SurgeonsDialog
          data={surgeons}
          onCancel={() => setSurgeons(null)}
          onSave={async (data) => {
            try {
              await rpc('surgeons.save', data);
              pushLog('Хирурги сохранены.', 'success');
              setSurgeons(null);
            } catch (e) {
              pushError(e);
            }
          }}
        />
      ) : null}

      {updateInfo ? (
        <UpdateDialog
          info={updateInfo}
          installing={updateInstalling}
          installError={updateInstallError}
          installLog={updateInstallLog}
          activeStepIndex={updateStepIndex}
          onClose={() => {
            if (updateInstalling) return;
            setUpdateInfo(null);
            setUpdateInstallError(null);
            setUpdateInstallLog([]);
            setUpdateStepIndex(0);
          }}
          onInstall={onInstallUpdate}
          onOpenRelease={() => {
            if (updateInfo.html_url) void api().openExternal(updateInfo.html_url);
          }}
        />
      ) : null}
    </div>
  );
}
