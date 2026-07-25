"""Точка входа.

Предпочтительный UI — Electron (`desktop/`, npm run dev / PlanOperaciy.exe).
Этот скрипт запускает legacy Tk только явно: PLAN_LEGACY_TK=1.
"""

import os
import sys


def _print_electron_hint() -> None:
    print(
        "План операций 2.0: основной интерфейс — Electron.\n"
        "  Dev:  cd desktop && npm run dev\n"
        "  Win:  PlanOperaciy.exe из релиза\n"
        "Legacy Tk: PLAN_LEGACY_TK=1 python plan_generator.py\n"
        "Документация миграции: MIGRATION.md",
        file=sys.stderr,
    )


if __name__ == "__main__":
    if os.environ.get("PLAN_LEGACY_TK") == "1":
        from app_gui import App
        from updater import check_for_updates, read_current_version

        current_ver = read_current_version()
        check_for_updates(current_ver, silent_if_updated=True)
        app = App()
        app.mainloop()
    else:
        _print_electron_hint()
        raise SystemExit(0)
