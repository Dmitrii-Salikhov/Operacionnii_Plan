## 1.1.2 — Windows UTF-8 bridge

- Исправлена ошибка `'charmap' codec can't encode character '\u2192'` на Windows.
- JSON-RPC bridge всегда пишет ответы в UTF-8; Electron задаёт `PYTHONUTF8` / `PYTHONIOENCODING`.
- Стрелки `→` в текстах настройки заменены на `->`.

## 1.1.1 — Security hardening

- IPC allowlist: RPC-методы, `openExternal` (только GitHub репозитория), `openPath` (base_dir + диалоги).
- Автообновление: TLS + доверенные URL + SHA-256; установщик `.cmd`/`tar` без PowerShell Bypass.
- Права на `credentials.json` / `token.pickle` только для текущего пользователя.
- Ошибки bridge без traceback в UI; подтверждение перед установкой обновления.

## 1.1.0 — Electron UI

- Интерфейс **Electron + React** (тема Slice, светлая/тёмная).
- Логика по-прежнему **Python** (JSON-RPC bridge / sidecar).
- Крупные кнопки «Сформировать план» и «Выгрузить телефоны» под панелью календаря.
- Выгрузка телефонов с выбором формата: `7957…` или без ведущей `7` (`957…`).
- Подсказки при наведении на кнопки панели.
- Автообновление Windows: zip + SHA-256, установщик без PowerShell Bypass.
- Мастер первого запуска и управление списком календарей из UI.
- Статус событий **по каждому calendar ID**.
- Ужесточение IPC: allowlist RPC / URL / путей; права на `credentials.json` / `token.pickle`.

См. [MIGRATION.md](MIGRATION.md), [SECURITY.md](SECURITY.md).

## Целостность

Проверьте `PlanOperaciy-Windows.zip.sha256`.
