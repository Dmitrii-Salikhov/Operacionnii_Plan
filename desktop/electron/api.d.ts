/** @typedef {{
  rpc: (method: string, params?: Record<string, unknown>) => Promise<unknown>;
  openExcelDialog: () => Promise<string | null>;
  openJsonDialog: () => Promise<string | null>;
  saveExcelDialog: (opts?: { defaultPath?: string }) => Promise<string | null>;
  saveJsonDialog: (opts?: { defaultPath?: string }) => Promise<string | null>;
  openPath: (filePath: string) => Promise<string>;
  openExternal: (url: string) => Promise<void>;
  getAppVersion: () => Promise<string>;
  getBridgeStatus: () => Promise<{ ok: boolean; detail?: string }>;
  quitAfterUpdate: () => Promise<{ ok: boolean }>;
}} PlanApi */

export {};

declare global {
  interface Window {
    plan?: PlanApi;
  }
}
