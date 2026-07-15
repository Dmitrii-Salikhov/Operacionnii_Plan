"""Диалоги уточнения неизвестных диагнозов."""

import tkinter as tk
from tkinter import messagebox, ttk

from patient_parser import patient_parser


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


def resolve_unknown_diagnoses(parent, gen):
    """Показывает диалог для пациентов с неизвестным диагнозом."""
    unknown = []
    for day in range(5):
        for room in ["5", "7", "MA"]:
            for p in gen.daily_blocks[day][room]:
                if p.get("is_unknown_diag"):
                    unknown.append(p)
    if not unknown:
        return

    top = tk.Toplevel(parent)
    top.title("Уточнение диагнозов (неизвестные / низкая уверенность)")
    top.geometry("960x520")
    top.transient(parent)
    top.grab_set()

    frame = ttk.Frame(top, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)

    columns = ("name", "raw", "diag", "oper", "conf")
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
    tree.heading("name", text="ФИО")
    tree.heading("raw", text="Исходный текст")
    tree.heading("diag", text="Диагноз")
    tree.heading("oper", text="Операция")
    tree.heading("conf", text="Уверенность")
    tree.column("name", width=160)
    tree.column("raw", width=220)
    tree.column("diag", width=240)
    tree.column("oper", width=200)
    tree.column("conf", width=90)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree.configure(yscrollcommand=scrollbar.set)

    for p in unknown:
        conf = p.get("confidence")
        conf_label = f"{conf:.0%}" if isinstance(conf, (int, float)) else "—"
        tree.insert(
            "",
            tk.END,
            iid=str(id(p)),
            values=(
                p["name"],
                p.get("diagnosis_raw", ""),
                p.get("diagnosis", "Диагноз не указан"),
                p.get("operation", "Операция не указана"),
                conf_label,
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
        edit_unknown_patient(parent, p, tree)

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


def edit_unknown_patient(parent, patient, tree):
    edit = tk.Toplevel(parent)
    edit.title("Редактирование диагноза")
    edit.geometry("500x250")
    edit.transient(parent)
    edit.grab_set()

    ttk.Label(
        edit, text="Ключевая фраза (можно выбрать или ввести свою):"
    ).pack(pady=(10, 0))
    key_var = tk.StringVar(value=patient.get("diagnosis_raw", ""))
    keys = sorted(patient_parser.diagnosis_map.keys(), key=str.lower)
    key_combo = ttk.Combobox(edit, textvariable=key_var, values=keys, state="normal")
    key_combo.pack(fill=tk.X, padx=10, pady=2)

    ttk.Label(edit, text="Диагноз:").pack()
    diag_var = tk.StringVar(value=patient.get("diagnosis", "Диагноз не указан"))
    diag_vals, oper_vals = _unique_diagnosis_options()
    diag_combo = ttk.Combobox(
        edit, textvariable=diag_var, values=diag_vals, state="normal"
    )
    diag_combo.pack(fill=tk.X, padx=10, pady=2)

    ttk.Label(edit, text="Операция:").pack()
    oper_var = tk.StringVar(value=patient.get("operation", "Операция не указана"))
    oper_combo = ttk.Combobox(
        edit, textvariable=oper_var, values=oper_vals, state="normal"
    )
    oper_combo.pack(fill=tk.X, padx=10, pady=2)

    def apply():
        key = key_var.get().strip()
        diag = diag_var.get().strip()
        oper = oper_var.get().strip()
        if not key or not diag or not oper:
            messagebox.showerror("Ошибка", "Все поля должны быть заполнены.")
            return
        patient["diagnosis_raw"] = key
        patient["diagnosis"] = diag
        patient["operation"] = oper
        patient["is_unknown_diag"] = False
        patient["confidence"] = 1.0
        patient["confidence_source"] = "manual"

        patient_parser.save_custom_diagnosis(key, diag, oper)

        if tree:
            for item in tree.get_children():
                if tree.item(item)["values"][0] == patient["name"]:
                    tree.item(
                        item,
                        values=(
                            patient["name"],
                            patient.get("diagnosis_raw", ""),
                            diag,
                            oper,
                            "100%",
                        ),
                    )
                    break
        edit.destroy()

    ttk.Button(edit, text="Применить", command=apply).pack(pady=10)
