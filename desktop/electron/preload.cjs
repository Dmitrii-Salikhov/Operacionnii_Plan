const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('plan', {
  rpc: (method, params) => ipcRenderer.invoke('bridge:rpc', method, params || {}),
  openExcelDialog: () => ipcRenderer.invoke('dialog:openExcel'),
  openJsonDialog: () => ipcRenderer.invoke('dialog:openJson'),
  saveExcelDialog: (opts) => ipcRenderer.invoke('dialog:saveExcel', opts || {}),
  saveJsonDialog: (opts) => ipcRenderer.invoke('dialog:saveJson', opts || {}),
  openExternal: (url) => ipcRenderer.invoke('shell:openExternal', url),
  getAppVersion: () => ipcRenderer.invoke('app:getVersion'),
  getBridgeStatus: () => ipcRenderer.invoke('bridge:status'),
  quitAfterUpdate: () => ipcRenderer.invoke('app:quitAfterUpdate'),
  openPath: (filePath) => ipcRenderer.invoke('shell:openPath', filePath),
  syncExportAdmissionsMenu: (checked) =>
    ipcRenderer.invoke('app:syncExportAdmissionsMenu', checked),
  menuReady: () => ipcRenderer.invoke('app:menuReady'),
  onMenuAction: (callback) => {
    const listener = (_event, action) => callback(String(action));
    ipcRenderer.on('menu:action', listener);
    return () => ipcRenderer.removeListener('menu:action', listener);
  },
});
