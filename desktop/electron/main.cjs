const { app, BrowserWindow, dialog, ipcMain, shell, session, Menu } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { PythonBridge } = require('./pythonBridge.cjs');

/** @type {BrowserWindow | null} */
let mainWindow = null;
/** Renderer subscribed to menu:action (flush early clicks on Windows). */
let rendererMenuReady = false;
/** @type {string[]} */
const pendingMenuActions = [];
const bridge = new PythonBridge();

/** Paths allowed for shell.openPath (session allowlist). */
const allowedOpenPaths = new Set();

const GITHUB_REPO_PATH = '/Dmitrii-Salikhov/Operacionnii_Plan/';

/** Must stay in sync with bridge.handlers.HANDLERS */
const ALLOWED_RPC = new Set([
  'ping',
  'config.get',
  'config.save',
  'calendar.status',
  'calendar.list',
  'calendar.set_ids',
  'calendar.fetch_week',
  'calendar.reauthorize',
  'source.set_excel',
  'plan.prepare',
  'plan.export',
  'phones.extract',
  'surgeons.get',
  'surgeons.save',
  'diag.options',
  'diag.export',
  'diag.import',
  'diag.save_one',
  'log.tail',
  'updates.check',
  'updates.install',
  'setup.status',
  'setup.ensure_files',
]);

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
}

function rememberPath(filePath) {
  if (!filePath) return;
  try {
    const resolved = path.resolve(filePath);
    allowedOpenPaths.add(resolved);
    allowedOpenPaths.add(path.dirname(resolved));
  } catch {
    // ignore
  }
}

function isPathAllowed(filePath) {
  let resolved;
  try {
    resolved = path.resolve(String(filePath));
  } catch {
    return false;
  }
  if (allowedOpenPaths.has(resolved)) return true;
  const root = path.resolve(bridge.projectRoot());
  const rel = path.relative(root, resolved);
  if (rel && !rel.startsWith('..') && !path.isAbsolute(rel)) return true;
  // Allow opening a directory that is an ancestor of an allowed file
  for (const allowed of allowedOpenPaths) {
    const r = path.relative(resolved, allowed);
    if (r && !r.startsWith('..') && !path.isAbsolute(r)) return true;
  }
  return false;
}

function isTrustedExternalUrl(url) {
  let parsed;
  try {
    parsed = new URL(String(url));
  } catch {
    return false;
  }
  if (parsed.protocol !== 'https:') return false;
  if (parsed.hostname.toLowerCase() !== 'github.com') return false;
  return parsed.pathname.startsWith(GITHUB_REPO_PATH);
}

function applyCsp() {
  const isDev = !!process.env.VITE_DEV_SERVER_URL;
  const csp = isDev
    ? "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self' data:; connect-src 'self' ws://127.0.0.1:* http://127.0.0.1:* ws://localhost:* http://localhost:*; object-src 'none'; base-uri 'self';"
    : "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self';";

  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    const headers = { ...details.responseHeaders };
    headers['Content-Security-Policy'] = [csp];
    callback({ responseHeaders: headers });
  });
}

function sendMenuAction(action) {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
  mainWindow.webContents.focus();
  const payload = String(action);
  if (!rendererMenuReady) {
    pendingMenuActions.push(payload);
    return;
  }
  mainWindow.webContents.send('menu:action', payload);
}

function flushPendingMenuActions() {
  if (!mainWindow || mainWindow.isDestroyed() || !rendererMenuReady) return;
  while (pendingMenuActions.length) {
    mainWindow.webContents.send('menu:action', pendingMenuActions.shift());
  }
}

/** Подпись с мнемоникой Alt+буква для Windows/Linux. */
function menuLabel(text, letterIndex = 0) {
  const isWinLinux = process.platform === 'win32' || process.platform === 'linux';
  if (!isWinLinux || text.includes('&')) return text;
  const chars = [...text];
  if (letterIndex < 0 || letterIndex >= chars.length) return text;
  chars[letterIndex] = `&${chars[letterIndex]}`;
  return chars.join('');
}

function buildApplicationMenu() {
  const isMac = process.platform === 'darwin';
  const isWin = process.platform === 'win32';
  const isDev = !!process.env.VITE_DEV_SERVER_URL;

  /** @type {import('electron').MenuItemConstructorOptions[]} */
  const template = [];

  if (isMac) {
    template.push({
      label: app.name,
      submenu: [
        {
          label: 'О программе',
          click: () => sendMenuAction('about'),
        },
        { type: 'separator' },
        { role: 'services', label: 'Службы' },
        { type: 'separator' },
        { role: 'hide', label: 'Скрыть' },
        { role: 'hideOthers', label: 'Скрыть остальные' },
        { role: 'unhide', label: 'Показать все' },
        { type: 'separator' },
        { role: 'quit', label: 'Выход' },
      ],
    });
  }

  template.push({
    label: menuLabel('Файл'),
    submenu: [
      {
        label: menuLabel('Открыть Excel…', 0),
        accelerator: 'CmdOrCtrl+O',
        click: () => sendMenuAction('open-excel'),
      },
      {
        label: menuLabel('Сформировать план', 0),
        accelerator: 'CmdOrCtrl+Enter',
        click: () => sendMenuAction('generate-plan'),
      },
      { type: 'separator' },
      {
        label: menuLabel('Экспорт словаря…', 0),
        click: () => sendMenuAction('export-dictionary'),
      },
      {
        label: menuLabel('Импорт словаря…', 0),
        click: () => sendMenuAction('import-dictionary'),
      },
      { type: 'separator' },
      {
        label: menuLabel('Выгрузить телефоны…', 0),
        click: () => sendMenuAction('export-phones'),
      },
      { type: 'separator' },
      ...(isMac
        ? []
        : [
            {
              role: 'quit',
              label: menuLabel('Выход', 0),
            },
          ]),
    ],
  });

  template.push({
    label: menuLabel('Календарь'),
    submenu: [
      {
        label: menuLabel('Выбрать неделю…', 0),
        accelerator: 'CmdOrCtrl+Shift+W',
        click: () => sendMenuAction('pick-week'),
      },
      {
        label: menuLabel('Календари…', 0),
        click: () => sendMenuAction('calendars'),
      },
      {
        label: menuLabel('Переподключить OAuth', 0),
        click: () => sendMenuAction('reconnect-oauth'),
      },
    ],
  });

  template.push({
    label: menuLabel('Настройки'),
    submenu: [
      {
        label: menuLabel('Хирурги…', 0),
        click: () => sendMenuAction('surgeons'),
      },
      {
        label: menuLabel('Мастер настройки…', 0),
        click: () => sendMenuAction('setup-wizard'),
      },
      { type: 'separator' },
      {
        label: menuLabel('Тема оформления', 0),
        accelerator: 'CmdOrCtrl+Shift+T',
        click: () => sendMenuAction('toggle-theme'),
      },
      {
        label: 'Список поступлений при экспорте',
        type: 'checkbox',
        checked: false,
        id: 'export-admissions',
        click: (item) => sendMenuAction(`toggle-admissions:${item.checked}`),
      },
    ],
  });

  template.push({
    label: menuLabel('Правка'),
    submenu: [
      { role: 'undo', label: menuLabel('Отменить', 0) },
      { role: 'redo', label: menuLabel('Повторить', 0) },
      { type: 'separator' },
      { role: 'cut', label: menuLabel('Вырезать', 0) },
      { role: 'copy', label: menuLabel('Копировать', 0) },
      { role: 'paste', label: menuLabel('Вставить', 0) },
      { role: 'selectAll', label: menuLabel('Выделить всё', 0) },
    ],
  });

  template.push({
    label: menuLabel('Вид'),
    submenu: [
      { role: 'resetZoom', label: menuLabel('Сбросить масштаб', 0) },
      { role: 'zoomIn', label: menuLabel('Увеличить', 0) },
      { role: 'zoomOut', label: menuLabel('Уменьшить', 0) },
      ...(isDev
        ? [
            { type: 'separator' },
            { role: 'reload', label: menuLabel('Перезагрузить', 0) },
            { role: 'forceReload', label: 'Перезагрузить принудительно' },
            { role: 'toggleDevTools', label: 'Инструменты разработчика' },
          ]
        : []),
    ],
  });

  template.push({
    label: menuLabel('Журнал'),
    submenu: [
      {
        label: menuLabel('Очистить журнал', 0),
        accelerator: 'CmdOrCtrl+L',
        click: () => sendMenuAction('clear-log'),
      },
    ],
  });

  template.push({
    label: menuLabel('Справка'),
    submenu: [
      {
        label: menuLabel('Проверить обновления', 0),
        click: () => sendMenuAction('check-updates'),
      },
      {
        label: menuLabel('Открыть папку программы', 0),
        click: () => sendMenuAction('open-base-dir'),
      },
      ...(isMac
        ? []
        : [
            { type: 'separator' },
            {
              label: menuLabel('О программе', 0),
              click: () => sendMenuAction('about'),
            },
          ]),
    ],
  });

  if (isMac) {
    template.push({
      label: menuLabel('Окно'),
      submenu: [
        { role: 'minimize', label: menuLabel('Свернуть', 0) },
        { role: 'zoom', label: menuLabel('Масштабировать', 0) },
        { type: 'separator' },
        { role: 'front', label: menuLabel('На передний план', 0) },
      ],
    });
  } else {
    template.push({
      label: menuLabel('Окно'),
      submenu: [
        { role: 'minimize', label: menuLabel('Свернуть', 0) },
        { role: 'close', label: menuLabel('Закрыть', 0) },
      ],
    });
  }

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
  if (isWin && mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.setMenuBarVisibility(true);
    mainWindow.setMenu(menu);
  }
  return menu;
}

function syncExportAdmissionsMenu(checked) {
  const menu = Menu.getApplicationMenu();
  if (!menu) return;
  const item = menu.getMenuItemById('export-admissions');
  if (item) item.checked = !!checked;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 920,
    height: 860,
    minWidth: 720,
    minHeight: 640,
    backgroundColor: '#0c0e12',
    title: 'План операций ЛОР',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
    show: false,
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) {
    mainWindow.loadURL(devUrl);
    if (process.env.PLAN_DEVTOOLS === '1') {
      mainWindow.webContents.openDevTools({ mode: 'detach' });
    }
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isTrustedExternalUrl(url)) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
    rendererMenuReady = false;
    pendingMenuActions.length = 0;
  });

  if (process.platform === 'win32') {
    mainWindow.setMenuBarVisibility(true);
  }

  buildApplicationMenu();
}

function registerIpc() {
  ipcMain.handle('bridge:rpc', async (_e, method, params) => {
    const name = String(method || '');
    if (!ALLOWED_RPC.has(name)) {
      throw new Error(`RPC method not allowed: ${name}`);
    }
    return bridge.rpc(name, params || {});
  });

  ipcMain.handle('bridge:status', async () => {
    try {
      await bridge.ensureStarted();
      return bridge.status();
    } catch (e) {
      return { ok: false, detail: e instanceof Error ? e.message : String(e) };
    }
  });

  ipcMain.handle('app:getVersion', async () => {
    try {
      const root = bridge.projectRoot();
      const vf = path.join(root, 'version.txt');
      if (fs.existsSync(vf)) return fs.readFileSync(vf, 'utf8').trim();
    } catch {
      // ignore
    }
    return app.getVersion();
  });

  ipcMain.handle('dialog:openExcel', async () => {
    const res = await dialog.showOpenDialog(mainWindow, {
      title: 'Выберите файл Excel',
      properties: ['openFile'],
      filters: [{ name: 'Excel', extensions: ['xlsx', 'xls'] }],
    });
    if (res.canceled || !res.filePaths[0]) return null;
    rememberPath(res.filePaths[0]);
    return res.filePaths[0];
  });

  ipcMain.handle('dialog:openJson', async () => {
    const res = await dialog.showOpenDialog(mainWindow, {
      title: 'Импорт словаря',
      properties: ['openFile'],
      filters: [{ name: 'JSON', extensions: ['json'] }],
    });
    if (res.canceled || !res.filePaths[0]) return null;
    rememberPath(res.filePaths[0]);
    return res.filePaths[0];
  });

  ipcMain.handle('dialog:saveExcel', async (_e, opts = {}) => {
    const res = await dialog.showSaveDialog(mainWindow, {
      title: 'Сохранить план операций',
      defaultPath: opts.defaultPath || 'plan.xlsx',
      filters: [{ name: 'Excel', extensions: ['xlsx'] }],
    });
    if (res.canceled || !res.filePath) return null;
    rememberPath(res.filePath);
    return res.filePath;
  });

  ipcMain.handle('dialog:saveJson', async (_e, opts = {}) => {
    const res = await dialog.showSaveDialog(mainWindow, {
      title: 'Экспорт словаря',
      defaultPath: opts.defaultPath || 'custom_diagnoses.json',
      filters: [{ name: 'JSON', extensions: ['json'] }],
    });
    if (res.canceled || !res.filePath) return null;
    rememberPath(res.filePath);
    return res.filePath;
  });

  ipcMain.handle('shell:openPath', async (_e, filePath) => {
    if (!isPathAllowed(filePath)) {
      throw new Error('Путь не разрешён для открытия');
    }
    return shell.openPath(String(filePath));
  });

  ipcMain.handle('shell:openExternal', async (_e, url) => {
    if (!isTrustedExternalUrl(url)) {
      throw new Error('URL не разрешён для открытия');
    }
    await shell.openExternal(String(url));
  });

  ipcMain.handle('app:syncExportAdmissionsMenu', async (_e, checked) => {
    syncExportAdmissionsMenu(checked);
    return { ok: true };
  });

  ipcMain.handle('app:menuReady', async () => {
    rendererMenuReady = true;
    flushPendingMenuActions();
    return { ok: true };
  });

  ipcMain.handle('app:quitAfterUpdate', async () => {
    setTimeout(() => {
      try {
        bridge.stop();
      } catch {
        // ignore
      }
      app.quit();
    }, 400);
    return { ok: true };
  });
}

app.whenReady().then(async () => {
  if (process.platform === 'darwin') {
    app.setName('План операций ЛОР');
  }
  applyCsp();
  registerIpc();
  rememberPath(bridge.projectRoot());
  createWindow();
  try {
    await bridge.ensureStarted();
    const st = await bridge.rpc('setup.status', {});
    if (st && st.base_dir) rememberPath(st.base_dir);
  } catch (e) {
    console.error('Failed to start Python bridge', e);
  }
});

app.on('window-all-closed', () => {
  bridge.stop();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  bridge.stop();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
