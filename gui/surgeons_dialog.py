"""Диалог настройки хирургов."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import config_surgeons


class SurgeonsDialog:
    def __init__(self, parent, log_message):
        self.parent = parent
        self.log_message = log_message

        self.top = tk.Toplevel(parent)
        self.top.title("Настройка хирургов")
        self.top.geometry("550x550")
        self.top.transient(parent)
        self.top.grab_set()

        notebook = ttk.Notebook(self.top)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tab_list = ttk.Frame(notebook)
        notebook.add(tab_list, text="Общий список")

        list_frame = tk.Frame(tab_list)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.surgeons_listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set, font=("Segoe UI", 11)
        )
        self.surgeons_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.surgeons_listbox.yview)

        btn_frame_list = tk.Frame(tab_list)
        btn_frame_list.pack(pady=5)
        ttk.Button(btn_frame_list, text="Добавить", command=self.add_surgeon).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame_list, text="Удалить", command=self.remove_surgeon).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(
            btn_frame_list, text="Переименовать", command=self.rename_surgeon
        ).pack(side=tk.LEFT, padx=5)

        tab_sched = ttk.Frame(notebook)
        notebook.add(tab_sched, text="Расписание")

        sched_frame = tk.Frame(tab_sched)
        sched_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.schedule_combos = {}
        days = ["Пн", "Вт", "Ср", "Чт", "Пт"]
        ops = ["№5", "№7", "М/А"]

        tk.Label(sched_frame, text="", width=8).grid(row=0, column=0)
        for col_idx, day in enumerate(days):
            tk.Label(sched_frame, text=day, font=("Segoe UI", 10, "bold")).grid(
                row=0, column=col_idx + 1, padx=5
            )

        for row_idx, op in enumerate(ops):
            tk.Label(sched_frame, text=op, font=("Segoe UI", 10, "bold")).grid(
                row=row_idx + 1, column=0, padx=10, pady=5, sticky="w"
            )
            for col_idx, day in enumerate(days):
                combo = ttk.Combobox(
                    sched_frame, values=self.get_surgeons_list(), width=20
                )
                combo.grid(row=row_idx + 1, column=col_idx + 1, padx=5, pady=3)
                self.schedule_combos[(op, day)] = combo

        tab_forbid = ttk.Frame(notebook)
        notebook.add(tab_forbid, text="Запреты для М/А")

        forbid_frame = tk.Frame(tab_forbid)
        forbid_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.forbid_listbox = tk.Listbox(
            forbid_frame, selectmode=tk.MULTIPLE, font=("Segoe UI", 11)
        )
        self.forbid_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        forbid_scroll = tk.Scrollbar(
            forbid_frame, command=self.forbid_listbox.yview
        )
        forbid_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.forbid_listbox.config(yscrollcommand=forbid_scroll.set)

        save_btn = ttk.Button(
            self.top, text="Сохранить все изменения", command=self.save_surgeons
        )
        save_btn.pack(pady=10)

        self.refresh_surgeons_ui()

    def get_surgeons_list(self):
        all_names = set(config_surgeons.FORBIDDEN_MA)
        for v in config_surgeons.SURGEON_5.values():
            all_names.add(v)
        all_names.add(config_surgeons.SURGEON_7)
        for v in config_surgeons.SURGEON_MA.values():
            all_names.add(v)
        return sorted(n for n in all_names if n)

    def refresh_surgeons_ui(self):
        self.surgeons_listbox.delete(0, tk.END)
        for name in self.get_surgeons_list():
            self.surgeons_listbox.insert(tk.END, name)

        updated_list = self.get_surgeons_list()
        for combo in self.schedule_combos.values():
            combo["values"] = updated_list

        days = ["Пн", "Вт", "Ср", "Чт", "Пт"]
        for i, day in enumerate(days):
            self.schedule_combos[("№5", day)].set(
                config_surgeons.SURGEON_5.get(i, "")
            )
            self.schedule_combos[("№7", day)].set(config_surgeons.SURGEON_7)
            self.schedule_combos[("М/А", day)].set(
                config_surgeons.SURGEON_MA.get(i, "")
            )

        self.forbid_listbox.delete(0, tk.END)
        for name in self.get_surgeons_list():
            self.forbid_listbox.insert(tk.END, name)
            if name in config_surgeons.FORBIDDEN_MA:
                idx = self.forbid_listbox.size() - 1
                self.forbid_listbox.selection_set(idx)

    def add_surgeon(self):
        new_name = simpledialog.askstring(
            "Добавить хирурга", "Введите ФИО нового хирурга:"
        )
        if new_name:
            new_name = new_name.strip()
            if new_name and new_name not in self.get_surgeons_list():
                config_surgeons.SURGEON_MA[99] = new_name
                config_surgeons.save_surgeons(
                    config_surgeons.SURGEON_5,
                    config_surgeons.SURGEON_7,
                    config_surgeons.SURGEON_MA,
                    config_surgeons.FORBIDDEN_MA,
                )
                self.refresh_surgeons_ui()
                self.log_message(f"Хирург '{new_name}' добавлен.", "success")

    def remove_surgeon(self):
        sel = self.surgeons_listbox.curselection()
        if not sel:
            messagebox.showwarning("Не выбрано", "Выберите хирурга для удаления.")
            return
        name = self.surgeons_listbox.get(sel[0])
        modified = False
        for key, val in config_surgeons.SURGEON_5.items():
            if val == name:
                config_surgeons.SURGEON_5[key] = ""
                modified = True
        if config_surgeons.SURGEON_7 == name:
            config_surgeons.SURGEON_7 = ""
            modified = True
        for key, val in config_surgeons.SURGEON_MA.items():
            if val == name:
                config_surgeons.SURGEON_MA[key] = ""
                modified = True
        if name in config_surgeons.FORBIDDEN_MA:
            config_surgeons.FORBIDDEN_MA.remove(name)
            modified = True
        if modified:
            config_surgeons.save_surgeons(
                config_surgeons.SURGEON_5,
                config_surgeons.SURGEON_7,
                config_surgeons.SURGEON_MA,
                config_surgeons.FORBIDDEN_MA,
            )
            self.refresh_surgeons_ui()
            self.log_message(f"Хирург '{name}' удалён.", "warning")

    def rename_surgeon(self):
        sel = self.surgeons_listbox.curselection()
        if not sel:
            messagebox.showwarning(
                "Не выбрано", "Выберите хирурга для переименования."
            )
            return
        old_name = self.surgeons_listbox.get(sel[0])
        new_name = simpledialog.askstring(
            "Переименовать хирурга", f"Новое имя для '{old_name}':"
        )
        if new_name and new_name.strip() != old_name:
            new_name = new_name.strip()
            modified = False
            for key, val in config_surgeons.SURGEON_5.items():
                if val == old_name:
                    config_surgeons.SURGEON_5[key] = new_name
                    modified = True
            if config_surgeons.SURGEON_7 == old_name:
                config_surgeons.SURGEON_7 = new_name
                modified = True
            for key, val in config_surgeons.SURGEON_MA.items():
                if val == old_name:
                    config_surgeons.SURGEON_MA[key] = new_name
                    modified = True
            if old_name in config_surgeons.FORBIDDEN_MA:
                config_surgeons.FORBIDDEN_MA.remove(old_name)
                config_surgeons.FORBIDDEN_MA.append(new_name)
                modified = True
            if modified:
                config_surgeons.save_surgeons(
                    config_surgeons.SURGEON_5,
                    config_surgeons.SURGEON_7,
                    config_surgeons.SURGEON_MA,
                    config_surgeons.FORBIDDEN_MA,
                )
                self.refresh_surgeons_ui()
                self.log_message(
                    f"Хирург '{old_name}' переименован в '{new_name}'.", "info"
                )

    def save_surgeons(self):
        days = ["Пн", "Вт", "Ср", "Чт", "Пт"]
        surg_5 = {}
        surg_ma = {}
        for i, day in enumerate(days):
            surg_5[i] = self.schedule_combos[("№5", day)].get().strip()
            surg_ma[i] = self.schedule_combos[("М/А", day)].get().strip()
        surg_7 = self.schedule_combos[("№7", days[0])].get().strip()

        selected_indices = self.forbid_listbox.curselection()
        forbidden = [self.forbid_listbox.get(i) for i in selected_indices]

        config_surgeons.save_surgeons(surg_5, surg_7, surg_ma, forbidden)
        (
            config_surgeons.SURGEON_5,
            config_surgeons.SURGEON_7,
            config_surgeons.SURGEON_MA,
            config_surgeons.FORBIDDEN_MA,
        ) = (surg_5, surg_7, surg_ma, forbidden)
        self.log_message("Расписание хирургов обновлено.", "success")
        messagebox.showinfo("Готово", "Расписание хирургов сохранено.")
        self.top.destroy()


def open_surgeons_dialog(parent, log_message):
    SurgeonsDialog(parent, log_message)
