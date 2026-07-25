# Desktop (Electron)

UI «План операций ЛОР» — Electron + Vite + React, тема как в Slice.

## Dev

```bash
# нужен Node 20+ и .venv с requirements.txt
cd desktop
export PLAN_PYTHON="../.venv/bin/python"   # Windows: ..\\.venv\\Scripts\\python.exe
npm install
npm run dev
```

Legacy Tk: `PLAN_LEGACY_TK=1 python plan_generator.py`

## Build (Windows)

См. `.github/workflows/release.yml`: PyInstaller sidecar → `desktop/backend/` → `electron-builder`.
