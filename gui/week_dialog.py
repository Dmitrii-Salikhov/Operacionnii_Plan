"""Диалог выбора понедельника для загрузки недели из календаря."""

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox


def ask_week_monday(parent, last_monday_date=None):
    """
    Показывает календарь и возвращает выбранный понедельник (date) или None.
    """
    result = {"date": None}

    dialog = tk.Toplevel(parent)
    dialog.title("Выберите понедельник нужной недели")
    dialog.geometry("400x360")
    dialog.resizable(False, False)
    dialog.transient(parent)

    tk.Label(dialog, text="Выберите дату понедельника:", font=("Segoe UI", 10)).pack(
        pady=(15, 5)
    )

    from tkcalendar import Calendar

    cal = Calendar(dialog, date_pattern="dd.MM.yyyy", locale="ru_RU", selectmode="day")
    cal.pack(pady=10)

    if last_monday_date is not None:
        cal.selection_set(last_monday_date)

    def on_ok():
        selected_date = cal.selection_get()
        if selected_date.weekday() != 0:
            monday = selected_date - timedelta(days=selected_date.weekday())
            confirm = messagebox.askyesno(
                "Не понедельник",
                f"Вы выбрали {selected_date.strftime('%d.%m.%Y')}, это не понедельник.\n"
                f"Взять ближайший понедельник {monday.strftime('%d.%m.%Y')}?",
            )
            if not confirm:
                return
            selected_date = monday

        today = datetime.now().date()
        if selected_date < today:
            if not messagebox.askyesno(
                "Неделя в прошлом",
                f"Вы выбрали неделю, начинающуюся {selected_date.strftime('%d.%m.%Y')}, "
                "которая уже прошла.\nПродолжить?",
            ):
                return

        result["date"] = selected_date
        dialog.destroy()

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(pady=15)
    tk.Button(
        btn_frame, text="Загрузить", command=on_ok, font=("Segoe UI", 10), width=10
    ).pack(side=tk.LEFT, padx=5)
    tk.Button(
        btn_frame, text="Отмена", command=dialog.destroy, font=("Segoe UI", 10), width=10
    ).pack(side=tk.LEFT, padx=5)

    dialog.grab_set()
    parent.wait_window(dialog)
    return result["date"]
