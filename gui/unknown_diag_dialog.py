"""Диалоги уточнения нераспознанных / сомнительных событий."""

import tkinter as tk
from tkinter import messagebox, ttk

from patient_parser import patient_parser

VALID_ROOMS = ("5", "7", "MA")
ROOM_LABELS = {"5": "5", "7": "7", "MA": "М/А"}
ROOM_FROM_LABEL = {"5": "5", "7": "7", "М/А": "MA"}


def _unique_diagnosis_options():
    """Уникальные диагнозы и операции (без дубликатов от синонимов-ключей)."""
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


def _needs_review(patient) -> bool:
    return bool(
        patient.get("is_unknown_diag") or patient.get("needs_name_review")
    )


def resolve_unknown_diagnoses(parent, gen):
    """Диалог для неизвестного диагноза, низкой уверенности или короткого имени."""
    unknown = []
    for day in range(5):
        for room in VALID_ROOMS:
            for p in gen.daily_blocks[day][room]:
                if _needs_review(p):
                    p["_review_day"] = day
                    p["_review_room"] = room
                    unknown.append(p)
    if not unknown:
        return

    top = tk.Toplevel(parent)
    top.title("Уточнение нераспознанных событий")
    top.geometry("1100x520")
    top.transient(parent)
    top.grab_set()

    frame = ttk.Frame(top, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)

    columns = ("name", "raw", "diag", "oper", "room", "conf", "reason")
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
    tree.heading("name", text="ФИО")
    tree.heading("raw", text="Исходный текст")
    tree.heading("diag", text="Диагноз")
    tree.heading("oper", text="Операция")
    tree.heading("room", text="Опер.")
    tree.heading("conf", text="Уверенность")
    tree.heading("reason", text="Причина")
    tree.column("name", width=140)
    tree.column("raw", width=180)
    tree.column("diag", width=200)
    tree.column("oper", width=160)
    tree.column("room", width=60)
    tree.column("conf", width=80)
    tree.column("reason", width=130)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree.configure(yscrollcommand=scrollbar.set)

    for p in unknown:
        conf = p.get("confidence")
        conf_label = f"{conf:.0%}" if isinstance(conf, (int, float)) else "—"
        room = p.get("_review_room") or "5"
        tree.insert(
            "",
            tk.END,
            iid=str(id(p)),
            values=(
                p["name"],
                p.get("diagnosis_raw", ""),
                p.get("diagnosis", "Диагноз не указан"),
                p.get("operation", "Операция не указана"),
                ROOM_LABELS.get(room, room),
                conf_label,
                _review_reason(p),
            ),
        )

    def on_double_click(_event=None):
        selection = tree.selection()
        if not selection:
            return
        item = selection[0]
        p = None
        for cand in unknown:
            if str(id(cand)) == item:
                p = cand
                break
        if not p:
            return
        edit_unknown_patient(parent, gen, p, tree)

    tree.bind("<Double-1>", on_double_click)

    btn_frame = ttk.Frame(top)
    btn_frame.pack(pady=10)
    ttk.Button(
        btn_frame, text="Уточнить выделенного", command=on_double_click
    ).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Закрыть", command=top.destroy).pack(
        side=tk.LEFT, padx=5
    )

    parent.wait_window(top)


def _review_reason(patient) -> str:
    parts = []
    if patient.get("needs_name_review"):
        parts.append("короткое ФИО")
    if patient.get("is_unknown_diag"):
        conf = patient.get("confidence")
        if isinstance(conf, (int, float)) and conf < 1.0:
            parts.append("низкая уверенность")
        else:
            parts.append("неизвестный диагноз")
    return ", ".join(parts) or "уточнение"


def _move_patient_room(gen, patient, to_room: str) -> None:
    day = patient.get("_review_day")
    from_room = patient.get("_review_room")
    if day is None or from_room is None or to_room not in VALID_ROOMS:
        return
    if to_room == from_room:
        return
    block = gen.daily_blocks[day][from_room]
    if patient in block:
        block.remove(patient)
    gen.daily_blocks[day][to_room].append(patient)
    patient["_review_room"] = to_room


def edit_unknown_patient(parent, gen, patient, tree):
    edit = tk.Toplevel(parent)
    edit.title("Редактирование события")
    edit.geometry("520x430")
    edit.transient(parent)
    edit.grab_set()

    ttk.Label(edit, text="ФИО:").pack(pady=(10, 0))
    name_var = tk.StringVar(value=patient.get("name", ""))
    name_entry = ttk.Entry(edit, textvariable=name_var)
    name_entry.pack(fill=tk.X, padx=10, pady=2)
    if patient.get("needs_name_review"):
        ttk.Label(
            edit,
            text="Имя короткое — можно оставить как есть или дополнить.",
            foreground="#555",
        ).pack(anchor="w", padx=10)

    ttk.Label(
        edit, text="Ключевая фраза (можно выбрать или ввести свою):"
    ).pack(pady=(8, 0))
    key_var = tk.StringVar(value=patient.get("diagnosis_raw", ""))
    keys = sorted(patient_parser.diagnosis_map.keys(), key=str.lower)
    key_combo = ttk.Combobox(edit, textvariable=key_var, values=keys, state="normal")
    key_combo.pack(fill=tk.X, padx=10, pady=2)

    ttk.Label(edit, text="Диагноз (можно новый):").pack()
    diag_var = tk.StringVar(value=patient.get("diagnosis", "Диагноз не указан"))
    diag_vals, oper_vals = _unique_diagnosis_options()
    diag_combo = ttk.Combobox(
        edit, textvariable=diag_var, values=diag_vals, state="normal"
    )
    diag_combo.pack(fill=tk.X, padx=10, pady=2)

    ttk.Label(edit, text="Операция (можно новая):").pack()
    oper_var = tk.StringVar(value=patient.get("operation", "Операция не указана"))
    oper_combo = ttk.Combobox(
        edit, textvariable=oper_var, values=oper_vals, state="normal"
    )
    oper_combo.pack(fill=tk.X, padx=10, pady=2)

    ttk.Label(edit, text="Примечание (к ключу, напр. Н.С.):").pack(pady=(8, 0))
    note_var = tk.StringVar(
        value=patient.get("notes")
        or patient_parser.key_notes.get(patient.get("diagnosis_raw") or "", "")
    )
    note_entry = ttk.Entry(edit, textvariable=note_var)
    note_entry.pack(fill=tk.X, padx=10, pady=2)

    def on_key_selected(_event=None):
        key = key_var.get().strip()
        entry = patient_parser.get_entry(key)
        if entry.get("diagnosis"):
            diag_var.set(entry["diagnosis"])
        if entry.get("operation"):
            oper_var.set(entry["operation"])
        if entry.get("note"):
            note_var.set(entry["note"])

    key_combo.bind("<<ComboboxSelected>>", on_key_selected)

    current_room = patient.get("_review_room") or "5"
    ttk.Label(edit, text="Операционная:").pack(pady=(8, 0))
    room_var = tk.StringVar(value=ROOM_LABELS.get(current_room, "5"))
    room_combo = ttk.Combobox(
        edit,
        textvariable=room_var,
        values=[ROOM_LABELS[r] for r in VALID_ROOMS],
        state="readonly",
    )
    room_combo.pack(fill=tk.X, padx=10, pady=2)

    def apply():
        name = name_var.get().strip()
        key = key_var.get().strip()
        diag = diag_var.get().strip()
        oper = oper_var.get().strip()
        note = note_var.get().strip()
        room_label = room_var.get().strip()
        to_room = ROOM_FROM_LABEL.get(room_label, "5")
        if not name or not key or not diag or not oper:
            messagebox.showerror("Ошибка", "ФИО, ключ, диагноз и операция обязательны.")
            return
        patient["name"] = name
        patient["diagnosis_raw"] = key
        patient["diagnosis"] = diag
        patient["operation"] = oper
        patient["notes"] = note
        patient["is_unknown_diag"] = False
        patient["needs_name_review"] = False
        patient["confidence"] = 1.0
        patient["confidence_source"] = "manual"

        patient_parser.save_custom_diagnosis(key, diag, oper, note=note)
        _move_patient_room(gen, patient, to_room)

        if tree:
            iid = str(id(patient))
            if tree.exists(iid):
                tree.item(
                    iid,
                    values=(
                        patient["name"],
                        patient.get("diagnosis_raw", ""),
                        diag,
                        oper,
                        ROOM_LABELS.get(to_room, to_room),
                        "100%",
                        "готово",
                    ),
                )
        edit.destroy()

    ttk.Button(edit, text="Применить", command=apply).pack(pady=10)
