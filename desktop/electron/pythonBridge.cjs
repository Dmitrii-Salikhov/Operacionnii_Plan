const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const readline = require('node:readline');

/** @typedef {{ resolve: (v: unknown) => void; reject: (e: Error) => void }} Pending */

class PythonBridge {
  constructor() {
    /** @type {import('node:child_process').ChildProcessWithoutNullStreams | null} */
    this.proc = null;
    /** @type {Map<number, Pending>} */
    this.pending = new Map();
    this.nextId = 1;
    this.starting = null;
  }

  resolvePython() {
    if (process.env.PLAN_PYTHON) return process.env.PLAN_PYTHON;
    if (process.platform === 'win32') {
      const packaged = path.join(process.resourcesPath || '', 'backend', 'PlanOperaciyBackend.exe');
      if (fs.existsSync(packaged)) return packaged;
    } else {
      const packaged = path.join(process.resourcesPath || '', 'backend', 'PlanOperaciyBackend');
      if (fs.existsSync(packaged)) return packaged;
    }
    const root = this.projectRoot();
    const venvPy =
      process.platform === 'win32'
        ? path.join(root, '.venv', 'Scripts', 'python.exe')
        : path.join(root, '.venv', 'bin', 'python');
    if (fs.existsSync(venvPy)) return venvPy;
    return process.platform === 'win32' ? 'python' : 'python3';
  }

  projectRoot() {
    // Dev (Vite): repository root. Packaged: folder next to PlanOperaciy.exe
    if (process.env.VITE_DEV_SERVER_URL) {
      return path.resolve(__dirname, '..', '..');
    }
    if (process.resourcesPath && !process.env.PLAN_FORCE_REPO_ROOT) {
      return path.dirname(process.execPath);
    }
    return path.resolve(__dirname, '..', '..');
  }

  cliPath() {
    return path.join(this.projectRoot(), 'bridge', 'cli.py');
  }

  async ensureStarted() {
    if (this.proc && !this.proc.killed) return;
    if (this.starting) return this.starting;
    this.starting = this._start();
    try {
      await this.starting;
    } finally {
      this.starting = null;
    }
  }

  async _start() {
    const python = this.resolvePython();
    const root = this.projectRoot();
    const isPackagedExe =
      python.endsWith('PlanOperaciyBackend.exe') || python.endsWith('PlanOperaciyBackend');

    const args = isPackagedExe ? [] : [this.cliPath()];
    const env = {
      ...process.env,
      PLAN_BASE_DIR: root,
      PYTHONUNBUFFERED: '1',
      PYTHONUTF8: '1',
      PYTHONIOENCODING: 'utf-8',
      PYTHONPATH: root,
    };

    this.proc = spawn(python, args, {
      cwd: root,
      env,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    this.proc.stdout.setEncoding('utf8');
    const rl = readline.createInterface({
      input: this.proc.stdout,
      crlfDelay: Infinity,
    });
    rl.on('line', (line) => this._onLine(line));

    this.proc.stderr.on('data', (buf) => {
      const text = buf.toString();
      if (text.trim()) console.error('[bridge]', text.trimEnd());
    });

    this.proc.on('exit', (code) => {
      const err = new Error(`Python bridge exited (${code})`);
      for (const [, p] of this.pending) p.reject(err);
      this.pending.clear();
      this.proc = null;
    });

    // Wait until bridge answers ping
    await this.rpc('ping', {}, 8000);
  }

  _onLine(line) {
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      console.error('[bridge] bad JSON', line);
      return;
    }
    const id = msg.id;
    const pending = this.pending.get(id);
    if (!pending) return;
    this.pending.delete(id);
    if (msg.error) {
      pending.reject(new Error(msg.error.message || String(msg.error)));
    } else {
      pending.resolve(msg.result);
    }
  }

  /**
   * @param {string} method
   * @param {Record<string, unknown>} params
   * @param {number} [timeoutMs]
   */
  async rpc(method, params = {}, timeoutMs = 120000) {
    await this.ensureStarted();
    if (!this.proc || !this.proc.stdin.writable) {
      throw new Error('Python bridge is not running');
    }
    const id = this.nextId++;
    const payload = JSON.stringify({ id, method, params }) + '\n';
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`RPC timeout: ${method}`));
      }, timeoutMs);
      this.pending.set(id, {
        resolve: (v) => {
          clearTimeout(timer);
          resolve(v);
        },
        reject: (e) => {
          clearTimeout(timer);
          reject(e);
        },
      });
      this.proc.stdin.write(Buffer.from(payload, 'utf8'), (err) => {
        if (err) {
          clearTimeout(timer);
          this.pending.delete(id);
          reject(err);
        }
      });
    });
  }

  status() {
    return {
      ok: !!(this.proc && !this.proc.killed),
      detail: this.proc ? 'running' : 'stopped',
    };
  }

  stop() {
    if (this.proc && !this.proc.killed) {
      try {
        this.proc.stdin.end();
      } catch {
        // ignore
      }
      this.proc.kill();
    }
    this.proc = null;
  }
}

module.exports = { PythonBridge };
