"""Bridge command handlers (no Tk)."""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from app_logging import LOG_FILENAME, read_log_tail, setup_app_logger
from calendar_provider import (
    calendar_display_name,
    calendar_setup_help,
    fetch_week_events,
    is_calendar_configured,
    load_calendar_ids,
    reauthorize,
    save_calendar_ids,
)
from calendar_provider.config import load_provider
from gui.helpers import load_config, open_folder, save_config, tag_for_log_line
from patient_parser import patient_parser
from phone_extractor import extract_phones_from_events
from plan_core import OperationPlanGenerator, admissions_excel_filename
import config_surgeons
from updater import (
    fetch_latest_release,
    find_release_asset,
    get_base_dir,
    install_update_headless,
    parse_version,
    read_current_version,
)

# In-memory plan session between prepare / export
_SESSION: Dict[str, Any] = {
    "events": None,
    "filepath": None,
    "gen": None,
    "week_start": None,
}

_logger = setup_app_logger(LOG_FILENAME)


def _serialize_date(d: Optional[date]) -> Optional[str]:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()
    return d.isoformat()


def _parse_monday(value: str) -> date:
    d = datetime.strptime(value, "%Y-%m-%d").date()
    if d.weekday() != 0:
        d = d - timedelta(days=d.weekday())
    return d


def _patient_review_row(p: dict, idx: int) -> dict:
    conf = p.get("confidence")
    reason = []
    if p.get("is_unknown_diag"):
        reason.append("диагноз")
    if p.get("needs_name_review"):
        reason.append("имя")
    return {
        "id": idx,
        "name": p.get("name") or "",
        "diagnosis_raw": p.get("diagnosis_raw") or "",
        "diagnosis": p.get("diagnosis") or "",
        "operation": p.get("operation") or "",
        "confidence": conf,
        "reason": ", ".join(reason) or "—",
        "is_unknown_diag": bool(p.get("is_unknown_diag")),
        "needs_name_review": bool(p.get("needs_name_review")),
    }


def _collect_reviews(gen: OperationPlanGenerator) -> List[dict]:
    rows = []
    idx = 0
    for day in range(5):
        for room in ["5", "7", "MA"]:
            for p in gen.daily_blocks[day][room]:
                if p.get("is_unknown_diag") or p.get("needs_name_review"):
                    rows.append(_patient_review_row(p, idx))
                # Always assign stable index for apply
                p["_bridge_id"] = idx
                idx += 1
    return [r for r in rows]


def _diag_options():
    diags = []
    opers = []
    seen_d = set()
    seen_o = set()
    for diag, oper in patient_parser.diagnosis_map.values():
        if diag not in seen_d:
            seen_d.add(diag)
            diags.append(diag)
        if oper not in seen_o:
            seen_o.add(oper)
            opers.append(oper)
    return sorted(diags, key=str.lower), sorted(opers, key=str.lower)


def ping(_params: dict) -> dict:
    return {"ok": True, "base_dir": os.getcwd(), "version": read_current_version()}


def config_get(_params: dict) -> dict:
    cfg = load_config()
    return {
        "last_dir": cfg.get("last_dir") or "",
        "last_monday": _serialize_date(cfg.get("last_monday")),
        "export_admissions": bool(cfg.get("export_admissions", False)),
        "ui_appearance": cfg.get("ui_appearance") or "Dark",
        "version": read_current_version(),
    }


def config_save(params: dict) -> dict:
    kwargs = {}
    if "last_dir" in params:
        kwargs["last_dir"] = params["last_dir"]
    if "last_monday" in params and params["last_monday"]:
        kwargs["last_monday"] = _parse_monday(str(params["last_monday"]))
    if "export_admissions" in params:
        kwargs["export_admissions"] = bool(params["export_admissions"])
    if "ui_appearance" in params and params["ui_appearance"] is not None:
        kwargs["ui_appearance"] = str(params["ui_appearance"])
    save_config(**kwargs)
    return config_get({})


CALENDAR_SWITCH_STEPS = [
    "Откройте «Календари» в программе (кнопка рядом с переподключением).",
    "Добавьте или измените email/ID календаря Google (например lorvidnoe@gmail.com).",
    "Можно указать несколько ID — события суммируются по всем спискам.",
    "Нажмите «Сохранить» — список пишется в calendars.json рядом с программой.",
    "Если доступ к новому календарю у другого Google-аккаунта — нажмите «Переподключить» и войдите нужным аккаунтом.",
    "Выберите неделю заново — в журнале и статусе будет число событий по каждому ID.",
]


def _event_counts_by_calendar(events) -> List[dict]:
    counts: Dict[str, int] = {}
    for ev in events or []:
        cal = str(ev.get("Календарь") or "").strip() or "(неизвестно)"
        counts[cal] = counts.get(cal, 0) + 1
    # Keep configured order first, then any extras
    ordered: List[dict] = []
    seen = set()
    for cal_id in load_calendar_ids():
        ordered.append({"calendar_id": cal_id, "count": counts.get(cal_id, 0)})
        seen.add(cal_id)
    for cal_id, count in sorted(counts.items()):
        if cal_id not in seen:
            ordered.append({"calendar_id": cal_id, "count": count})
    return ordered


def calendar_status(_params: dict) -> dict:
    configured = is_calendar_configured()
    ids = load_calendar_ids()
    return {
        "configured": configured,
        "display_name": calendar_display_name(),
        "help": calendar_setup_help() if not configured else "",
        "provider": load_provider(),
        "calendar_ids": ids,
        "switch_steps": list(CALENDAR_SWITCH_STEPS),
    }


def calendar_list(_params: dict) -> dict:
    return {
        "provider": load_provider(),
        "calendar_ids": load_calendar_ids(),
        "switch_steps": list(CALENDAR_SWITCH_STEPS),
        "configured": is_calendar_configured(),
        "display_name": calendar_display_name(),
    }


def calendar_set_ids(params: dict) -> dict:
    raw = params.get("calendar_ids")
    if raw is None:
        raise RuntimeError("Укажите calendar_ids (список строк).")
    if not isinstance(raw, list):
        raise RuntimeError("calendar_ids должен быть списком.")
    provider = params.get("provider")
    saved = save_calendar_ids(
        [str(x) for x in raw],
        provider=str(provider) if provider else None,
    )
    return {
        "calendar_ids": saved,
        "provider": load_provider(),
        "switch_steps": list(CALENDAR_SWITCH_STEPS),
    }


def calendar_fetch_week(params: dict) -> dict:
    if not is_calendar_configured():
        raise RuntimeError(calendar_setup_help())
    monday = _parse_monday(str(params["monday"]))
    save_config(last_monday=monday)
    events = fetch_week_events(monday)
    _SESSION["events"] = events
    _SESSION["filepath"] = None
    _SESSION["gen"] = None
    _SESSION["week_start"] = monday
    by_calendar = _event_counts_by_calendar(events)
    return {
        "count": len(events or []),
        "week_start": monday.isoformat(),
        "week_end": (monday + timedelta(days=6)).isoformat(),
        "empty": not bool(events),
        "by_calendar": by_calendar,
        "calendar_ids": load_calendar_ids(),
    }


def calendar_reauthorize(_params: dict) -> dict:
    if not is_calendar_configured():
        raise RuntimeError(calendar_setup_help())
    reauthorize()
    return {"ok": True}


def source_set_excel(params: dict) -> dict:
    path = str(params.get("path") or "")
    if not path or not os.path.isfile(path):
        raise RuntimeError("Файл Excel не найден")
    _SESSION["filepath"] = path
    _SESSION["events"] = None
    _SESSION["gen"] = None
    save_config(last_dir=os.path.dirname(path))
    return {"path": path, "name": os.path.basename(path)}


def plan_prepare(params: dict) -> dict:
    logs: List[dict] = []

    def log_cb(msg, tag="info"):
        logs.append({"message": str(msg), "tag": tag})
        _logger.info("%s", msg)

    if _SESSION.get("events"):
        gen = OperationPlanGenerator(
            events_data=_SESSION["events"], log_callback=log_cb
        )
    elif _SESSION.get("filepath"):
        gen = OperationPlanGenerator(
            filepath=_SESSION["filepath"], log_callback=log_cb
        )
    else:
        raise RuntimeError("Сначала выберите файл или загрузите неделю из календаря.")

    gen.parse_all_events()
    if gen.week_start is None:
        raise RuntimeError("Не удалось определить дату начала недели.")
    gen.distribute_patients()
    _SESSION["gen"] = gen
    _SESSION["week_start"] = gen.week_start
    reviews = _collect_reviews(gen)
    diags, opers = _diag_options()
    week_end = gen.week_start + timedelta(days=6)
    default_name = (
        f"План операций за {gen.week_start.strftime('%d.%m.%Y')} - "
        f"{week_end.strftime('%d.%m.%Y')}.xlsx"
    )
    return {
        "week_start": gen.week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "default_filename": default_name,
        "reviews": reviews,
        "diagnosis_options": diags,
        "operation_options": opers,
        "logs": logs,
    }


def plan_export(params: dict) -> dict:
    gen: OperationPlanGenerator = _SESSION.get("gen")
    if gen is None:
        raise RuntimeError("Сначала выполните подготовку плана (plan.prepare).")

    output_path = str(params.get("output_path") or "")
    if not output_path:
        raise RuntimeError("Не указан путь сохранения.")

    reviews = params.get("reviews") or []
    by_id = {int(r["id"]): r for r in reviews if "id" in r}

    for day in range(5):
        for room in ["5", "7", "MA"]:
            for p in gen.daily_blocks[day][room]:
                rid = p.get("_bridge_id")
                if rid is None or rid not in by_id:
                    continue
                patch = by_id[rid]
                if "name" in patch and patch["name"]:
                    p["name"] = str(patch["name"]).strip()
                    p["needs_name_review"] = False
                if "diagnosis" in patch and patch["diagnosis"]:
                    p["diagnosis"] = str(patch["diagnosis"]).strip()
                    p["is_unknown_diag"] = False
                    raw = (p.get("diagnosis_raw") or "").strip()
                    if raw and patch.get("remember"):
                        patient_parser.save_custom_diagnosis(
                            raw, p["diagnosis"], str(patch.get("operation") or p.get("operation") or "")
                        )
                if "operation" in patch and patch["operation"] is not None:
                    p["operation"] = str(patch["operation"]).strip()

    logs: List[dict] = []

    def log_cb(msg, tag="info"):
        logs.append({"message": str(msg), "tag": tag})
        _logger.info("%s", msg)

    gen.log = log_cb
    gen.assign_surgeons()
    gen.sort_patients_in_rooms()
    gen.generate_excel(output_path)

    export_admissions = bool(params.get("export_admissions", False))
    admissions_path = None
    last_dir = os.path.dirname(output_path)
    save_config(last_dir=last_dir, export_admissions=export_admissions)

    if export_admissions and gen.week_start is not None:
        adm_name = admissions_excel_filename(gen.week_start)
        admissions_path = os.path.join(last_dir, adm_name)
        gen.generate_admissions_excel(admissions_path)

    if params.get("open_folder"):
        open_folder(last_dir)

    return {
        "output_path": output_path,
        "admissions_path": admissions_path,
        "logs": logs,
    }


def phones_extract(params: dict) -> dict:
    if not _SESSION.get("events"):
        raise RuntimeError("Телефоны доступны только после загрузки недели из календаря.")
    rows = extract_phones_from_events(_SESSION["events"])
    # format: "with_7" → 7957… ; "without_7" → 957…
    fmt = str(params.get("format") or "with_7").strip().lower()
    strip7 = fmt in ("without_7", "no_7", "10", "local")
    if params.get("strip_leading_7") is True:
        strip7 = True

    formatted = []
    for phone, name in rows:
        p = str(phone)
        if strip7 and len(p) == 11 and p.startswith("7"):
            p = p[1:]
        formatted.append((p, name))

    output_path = params.get("output_path")
    if output_path:
        df = pd.DataFrame(formatted, columns=["Phone", "Name"])
        df.to_excel(output_path, index=False, sheet_name="Телефоны")
        if params.get("open_folder"):
            open_folder(os.path.dirname(str(output_path)))
    return {
        "count": len(formatted),
        "format": "without_7" if strip7 else "with_7",
        "rows": [{"phone": a, "name": b} for a, b in formatted],
        "output_path": output_path,
    }


def _as_day_map(raw) -> dict:
    """Normalize {0: name, ...} or {"0": name} day maps."""
    if isinstance(raw, dict):
        return {int(k): str(v or "") for k, v in raw.items()}
    if isinstance(raw, list):
        return {i: str(v or "") for i, v in enumerate(raw)}
    return {}


def surgeons_get(_params: dict) -> dict:
    s5, s7, sma, forbidden = config_surgeons.load_surgeons()
    roster = sorted(
        config_surgeons.collect_surgeon_names(s5, s7, sma, forbidden)
    )
    return {
        "surgeon_5": {str(k): v for k, v in s5.items()},
        "surgeon_7": s7,
        "surgeon_ma": {str(k): v for k, v in sma.items()},
        "forbidden_ma": list(forbidden or []),
        "roster": roster,
    }


def surgeons_save(params: dict) -> dict:
    s5 = _as_day_map(params.get("surgeon_5"))
    sma = _as_day_map(params.get("surgeon_ma"))
    s7 = str(params.get("surgeon_7") or "")
    forbidden = [str(x) for x in (params.get("forbidden_ma") or []) if str(x).strip()]
    config_surgeons.save_surgeons(s5, s7, sma, forbidden)
    config_surgeons.SURGEON_5 = s5
    config_surgeons.SURGEON_7 = s7
    config_surgeons.SURGEON_MA = sma
    config_surgeons.FORBIDDEN_MA = forbidden
    return surgeons_get({})


def diag_options(_params: dict) -> dict:
    diags, opers = _diag_options()
    return {"diagnoses": diags, "operations": opers}


def diag_export(params: dict) -> dict:
    path = str(params.get("path") or "")
    if not path:
        raise RuntimeError("Не указан путь экспорта.")
    src = patient_parser.custom_diag_file
    if os.path.exists(src):
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"path": path, "count": len(data) if isinstance(data, dict) else 0}


def diag_import(params: dict) -> dict:
    path = str(params.get("path") or "")
    if not path or not os.path.isfile(path):
        raise RuntimeError("Файл словаря не найден.")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise RuntimeError("Ожидался JSON-объект.")
    count = 0
    for key, value in data.items():
        if isinstance(value, (list, tuple)) and len(value) == 2:
            patient_parser.diagnosis_map[str(key)] = (str(value[0]), str(value[1]))
            count += 1
    patient_parser.save_custom_diagnoses_full()
    patient_parser.sort_keys()
    return {"count": count}


def diag_save_one(params: dict) -> dict:
    raw = str(params.get("raw") or "").strip()
    diagnosis = str(params.get("diagnosis") or "").strip()
    operation = str(params.get("operation") or "").strip()
    if not raw or not diagnosis:
        raise RuntimeError("Нужны исходный текст и диагноз.")
    patient_parser.save_custom_diagnosis(raw, diagnosis, operation)
    return {"ok": True}


def log_tail(params: dict) -> dict:
    n = int(params.get("lines") or 500)
    content = read_log_tail(LOG_FILENAME, n)
    lines = []
    for line in content.splitlines():
        lines.append({"text": line, "tag": tag_for_log_line(line)})
    return {"lines": lines, "raw": content}


def updates_check(_params: dict) -> dict:
    current = read_current_version()
    release = fetch_latest_release()
    if not release:
        return {
            "current": current,
            "latest": None,
            "update_available": False,
            "error": "Не удалось получить релиз с GitHub",
        }
    tag = release.get("tag_name") or ""
    latest = tag.lstrip("v")
    update_available = parse_version(tag) > parse_version(current)
    zip_asset = find_release_asset(release, "PlanOperaciy-Windows.zip")
    html_url = release.get("html_url")
    return {
        "current": current,
        "latest": latest,
        "tag": tag,
        "update_available": update_available,
        "html_url": html_url,
        "has_zip": bool(zip_asset),
        "can_install": bool(zip_asset) and sys.platform == "win32",
    }


def updates_install(_params: dict) -> dict:
    release = fetch_latest_release()
    result = install_update_headless(get_base_dir(), release=release)
    return result


def setup_status(_params: dict) -> dict:
    """Состояние для мастера первого запуска."""
    from constants import (
        CALENDARS_EXAMPLE_FILE,
        CALENDARS_FILE,
        CREDENTIALS_EXAMPLE_FILE,
        CREDENTIALS_FILE,
    )

    base = get_base_dir()
    ids = load_calendar_ids()
    creds_ok = os.path.exists(CREDENTIALS_FILE)
    cal_file = os.path.exists(CALENDARS_FILE)
    return {
        "base_dir": base,
        "credentials_ok": creds_ok,
        "credentials_path": os.path.join(base, CREDENTIALS_FILE),
        "credentials_example": os.path.join(base, CREDENTIALS_EXAMPLE_FILE),
        "calendars_file_exists": cal_file,
        "calendars_path": os.path.join(base, CALENDARS_FILE),
        "calendars_example": os.path.join(base, CALENDARS_EXAMPLE_FILE),
        "calendar_ids": ids,
        "calendars_ready": bool(ids),
        "configured": is_calendar_configured() and bool(ids),
        "steps": [
            f"Папка программы: {base}",
            (
                f"Скопируйте {CREDENTIALS_EXAMPLE_FILE} → {CREDENTIALS_FILE} "
                "и вставьте client_id / client_secret из Google Cloud (OAuth Desktop)."
            ),
            f"В «Календари…» укажите email/ID календарей (или отредактируйте {CALENDARS_FILE}).",
            "Нажмите «Переподключить Google» и войдите нужным аккаунтом.",
            "Выберите неделю — в статусе появятся числа событий по каждому ID.",
        ],
    }


def setup_ensure_files(_params: dict) -> dict:
    """Создаёт calendars.json из example, если его ещё нет."""
    from calendar_provider.config import ensure_calendars_config
    from constants import CREDENTIALS_EXAMPLE_FILE, CREDENTIALS_FILE
    import shutil

    ensure_calendars_config()
    created_creds = False
    if not os.path.exists(CREDENTIALS_FILE) and os.path.exists(CREDENTIALS_EXAMPLE_FILE):
        shutil.copyfile(CREDENTIALS_EXAMPLE_FILE, CREDENTIALS_FILE)
        created_creds = True
    return {
        **setup_status({}),
        "created_credentials_stub": created_creds,
    }


HANDLERS = {
    "ping": ping,
    "config.get": config_get,
    "config.save": config_save,
    "calendar.status": calendar_status,
    "calendar.list": calendar_list,
    "calendar.set_ids": calendar_set_ids,
    "calendar.fetch_week": calendar_fetch_week,
    "calendar.reauthorize": calendar_reauthorize,
    "source.set_excel": source_set_excel,
    "plan.prepare": plan_prepare,
    "plan.export": plan_export,
    "phones.extract": phones_extract,
    "surgeons.get": surgeons_get,
    "surgeons.save": surgeons_save,
    "diag.options": diag_options,
    "diag.export": diag_export,
    "diag.import": diag_import,
    "diag.save_one": diag_save_one,
    "log.tail": log_tail,
    "updates.check": updates_check,
    "updates.install": updates_install,
    "setup.status": setup_status,
    "setup.ensure_files": setup_ensure_files,
}


def dispatch(method: str, params: dict) -> Any:
    if method not in HANDLERS:
        raise RuntimeError(f"Unknown method: {method}")
    return HANDLERS[method](params)
