const { app, BrowserWindow, dialog, ipcMain, shell, session } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { PythonBridge } = require('./pythonBridge.cjs');

/** @type {BrowserWindow | null} */
let mainWindow = null;
const bridge = new PythonBridge();

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
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

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function registerIpc() {
  ipcMain.handle('bridge:rpc', async (_e, method, params) => {
    return bridge.rpc(String(method), params || {});
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
    return res.filePaths[0];
  });

  ipcMain.handle('dialog:openJson', async () => {
    const res = await dialog.showOpenDialog(mainWindow, {
      title: 'Импорт словаря',
      properties: ['openFile'],
      filters: [{ name: 'JSON', extensions: ['json'] }],
    });
    if (res.canceled || !res.filePaths[0]) return null;
    return res.filePaths[0];
  });

  ipcMain.handle('dialog:saveExcel', async (_e, opts = {}) => {
    const res = await dialog.showSaveDialog(mainWindow, {
      title: 'Сохранить план операций',
      defaultPath: opts.defaultPath || 'plan.xlsx',
      filters: [{ name: 'Excel', extensions: ['xlsx'] }],
    });
    if (res.canceled || !res.filePath) return null;
    return res.filePath;
  });

  ipcMain.handle('dialog:saveJson', async (_e, opts = {}) => {
    const res = await dialog.showSaveDialog(mainWindow, {
      title: 'Экспорт словаря',
      defaultPath: opts.defaultPath || 'custom_diagnoses.json',
      filters: [{ name: 'JSON', extensions: ['json'] }],
    });
    if (res.canceled || !res.filePath) return null;
    return res.filePath;
  });

  ipcMain.handle('shell:openPath', async (_e, filePath) => {
    return shell.openPath(String(filePath));
  });

  ipcMain.handle('shell:openExternal', async (_e, url) => {
    await shell.openExternal(String(url));
  });

  ipcMain.handle('app:quitAfterUpdate', async () => {
    // Give PowerShell a moment to attach, then exit so Expand-Archive can run.
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
  applyCsp();
  registerIpc();
  createWindow();
  try {
    await bridge.ensureStarted();
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
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
