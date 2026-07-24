"""Главное окно приложения."""

import json
import os
from datetime import datetime, timedelta

import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app_logging import (
    LOG_FILENAME,
    MAX_LOG_LINES as LOG_LINE_LIMIT,
    now_timestamp,
    read_log_tail,
    setup_app_logger,
)
from calendar_provider import (
    calendar_display_name,
    calendar_setup_help,
    fetch_week_events,
    is_calendar_configured,
    reauthorize,
)
from gui.helpers import (
    configure_log_text_tags,
    insert_colored_log,
    load_config,
    open_folder,
    save_config,
)
from gui.surgeons_dialog import open_surgeons_dialog
from gui.unknown_diag_dialog import resolve_unknown_diagnoses
from gui.week_dialog import ask_week_monday
from patient_parser import patient_parser
from phone_extractor import extract_phones_from_events
from plan_core import OperationPlanGenerator, admissions_excel_filename
from updater import check_for_updates


class App(tk.Tk):
    MAX_LOG_LINES = LOG_LINE_LIMIT

    def __init__(self):
        super().__init__()
        self.title("План операций ЛОР-отделения")
        self.geometry("650x750")
        self.resizable(True, True)

        self.file_logger = setup_app_logger(LOG_FILENAME)

        config = load_config()
        self.last_dir = config.get("last_dir", "")
        self.last_monday_date = config.get("last_monday")
        self.export_admissions_var = tk.BooleanVar(
            value=bool(config.get("export_admissions", False))
        )

        self.input_file = None
        self.calendar_data = None
        self.week_start_date = None
        self.week_end_date = None

        self.status_text = tk.StringVar(
            value="Выберите источник данных и нажмите «Сформировать план»"
        )

        try:
            from updater import get_base_dir

            version_file = os.path.join(get_base_dir(), "version.txt")
            with open(version_file, "r", encoding="utf-8") as vf:
                self.current_version = vf.read().strip()
        except OSError:
            self.current_version = "?.?.?"

        self._build_ui()
        self._load_existing_log()
        self.log_message("Готов к работе. Выберите источник данных.", tag="success")

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Action.TButton", font=("Segoe UI", 10), padding=6)
        style.configure("Browse.TButton", font=("Segoe UI", 10), padding=4)
        style.configure("Small.TButton", font=("Segoe UI", 9), padding=4)

        main_frame = tk.Frame(self, padx=12, pady=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.version_label = tk.Label(
            main_frame,
            text=f"Версия: {self.current_version}",
            anchor="e",
            fg="gray",
            font=("Segoe UI", 8),
        )
        self.version_label.pack(side=tk.BOTTOM, anchor="se", pady=(0, 5))

        cal_frame = tk.LabelFrame(
            main_frame,
            text=f" Загрузка из календаря ({calendar_display_name()}) ",
            padx=10,
            pady=10,
            font=("Segoe UI", 10, "bold"),
        )
        cal_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(
            cal_frame,
            text=" 📅 Выбрать неделю (понедельник)...",
            command=self.choose_week,
            style="Action.TButton",
        ).pack(fill=tk.X)
        ttk.Button(
            cal_frame,
            text=" 🔄 Переподключить календарь",
            command=self.reconnect_calendar,
            style="Small.TButton",
        ).pack(pady=(5, 0))

        xl_frame = tk.LabelFrame(
            main_frame,
            text=" Загрузка из Excel-файла ",
            padx=10,
            pady=10,
            font=("Segoe UI", 10, "bold"),
        )
        xl_frame.pack(fill=tk.X, pady=(0, 8))
        self.file_path_var = tk.StringVar()
        tk.Entry(
            xl_frame,
            textvariable=self.file_path_var,
            state="readonly",
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        ttk.Button(
            xl_frame,
            text=" 📂 Обзор...",
            command=self.choose_file,
            style="Browse.TButton",
        ).pack(side=tk.RIGHT)

        ttk.Checkbutton(
            main_frame,
            text="Также сохранить отдельный «Список поступлений ЛОР»",
            variable=self.export_admissions_var,
            command=self._on_export_admissions_toggle,
        ).pack(anchor="w", pady=(4, 0))

        ttk.Button(
            main_frame,
            text=" ▶️ Сформировать план",
            command=self.generate_plan,
            style="Action.TButton",
        ).pack(pady=10, fill=tk.X)

        ttk.Button(
            main_frame,
            text=" 📞 Выгрузить телефоны",
            command=self.extract_phones_action,
            style="Action.TButton",
        ).pack(pady=5, fill=tk.X)

        ttk.Button(
            main_frame,
            text=" 👨‍⚕️ Настроить хирургов",
            command=self.configure_surgeons,
            style="Action.TButton",
        ).pack(pady=5, fill=tk.X)

        ttk.Button(
            main_frame,
            text=" 🔄 Проверить обновления",
            command=self.check_updates_action,
            style="Action.TButton",
        ).pack(pady=5, fill=tk.X)

        ttk.Button(
            main_frame,
            text=" 📋 Открыть лог",
            command=self.open_log_window,
            style="Action.TButton",
        ).pack(pady=5, fill=tk.X)

        diag_frame = tk.LabelFrame(
            main_frame,
            text=" Пользовательские диагнозы ",
            padx=10,
            pady=10,
            font=("Segoe UI", 10, "bold"),
        )
        diag_frame.pack(fill=tk.X, pady=(0, 8))
        diag_buttons = tk.Frame(diag_frame)
        diag_buttons.pack(fill=tk.X)
        ttk.Button(
            diag_buttons,
            text="📤 Экспорт словаря",
            command=self.export_custom_diag,
            style="Small.TButton",
        ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(
            diag_buttons,
            text="📥 Импорт словаря",
            command=self.import_custom_diag,
            style="Small.TButton",
        ).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        tk.Label(
            main_frame,
            textvariable=self.status_text,
            anchor="w",
            fg="#555",
            font=("Segoe UI", 9),
        ).pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            main_frame,
            text="Журнал (дата и время у каждого события; Ctrl+C / ⌘C — копировать):",
            anchor="w",
            font=("Segoe UI", 9, "bold"),
        ).pack(fill=tk.X)
        log_frame = tk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.log_text = tk.Text(
            log_frame,
            height=8,
            state="normal",
            bg="white",
            fg="#1a1a1a",
            insertbackground="#1a1a1a",
            selectbackground="#cce5ff",
            wrap="word",
            font=("Consolas", 9),
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.log_text.yview)

        self.log_text.bind("<Command-c>", self.copy_log)
        self.log_text.bind("<Control-c>", self.copy_log)

        configure_log_text_tags(self.log_text)

        self.progress = ttk.Progressbar(main_frame, mode="indeterminate")

    def check_updates_action(self):
        self.log_message("Проверка обновлений...", "info")
        check_for_updates(self.current_version)
        self.log_message("Проверка обновлений завершена.", "info")

    def _on_export_admissions_toggle(self):
        save_config(export_admissions=self.export_admissions_var.get())

    def _scroll_log_to_end(self, widget=None):
        target = widget if widget is not None else self.log_text
        target.see(tk.END)
        target.mark_set(tk.INSERT, tk.END)

    def _trim_log(self):
        lines = self.log_text.get("1.0", "end-1c").split("\n")
        if len(lines) > self.MAX_LOG_LINES:
            new_text = "\n".join(lines[-self.MAX_LOG_LINES :])
            insert_colored_log(self.log_text, new_text, clear=True)

    def _load_existing_log(self):
        """Подгружает хвост plan_generator.log в окно и пролистывает вниз."""
        content = read_log_tail(LOG_FILENAME, self.MAX_LOG_LINES).rstrip("\n")
        if not content:
            return
        insert_colored_log(self.log_text, content + "\n", clear=True)
        self._scroll_log_to_end()

    def log_message(self, msg, tag="info"):
        formatted_msg = f"[{now_timestamp()}] {msg}"
        self.log_text.insert(tk.END, formatted_msg + "\n", tag)
        self._trim_log()
        self._scroll_log_to_end()
        # В файл — только текст сообщения: дату пишет Formatter
        if tag == "error":
            self.file_logger.error("%s", msg)
        elif tag == "warning":
            self.file_logger.warning("%s", msg)
        else:
            self.file_logger.info("%s", msg)
        self.update_idletasks()

    def open_log_window(self):
        """Отдельное окно с логом (последние MAX_LOG_LINES), сразу в конце."""
        top = tk.Toplevel(self)
        top.title(f"Журнал — {LOG_FILENAME} (не более {self.MAX_LOG_LINES} строк)")
        top.geometry("800x500")
        top.transient(self)

        frame = tk.Frame(top)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        text = tk.Text(
            frame,
            wrap="word",
            font=("Consolas", 9),
            bg="white",
            fg="#1a1a1a",
            insertbackground="#1a1a1a",
            selectbackground="#cce5ff",
        )
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(frame, command=text.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        text.config(yscrollcommand=sb.set)
        configure_log_text_tags(text)

        content = read_log_tail(LOG_FILENAME, self.MAX_LOG_LINES)
        if not content.strip():
            content = self.log_text.get("1.0", tk.END)
        insert_colored_log(text, content, clear=True)
        text.config(state="disabled")
        top.update_idletasks()
        self._scroll_log_to_end(text)

        btn_row = tk.Frame(top)
        btn_row.pack(pady=(0, 8))
        ttk.Button(
            btn_row,
            text="Обновить",
            command=lambda: self._refresh_log_window(text),
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Закрыть", command=top.destroy).pack(
            side=tk.LEFT, padx=5
        )

    def _refresh_log_window(self, text_widget):
        content = read_log_tail(LOG_FILENAME, self.MAX_LOG_LINES)
        if not content.strip():
            content = self.log_text.get("1.0", tk.END)
        text_widget.config(state="normal")
        insert_colored_log(text_widget, content, clear=True)
        text_widget.config(state="disabled")
        self._scroll_log_to_end(text_widget)

    def copy_log(self, event=None):
        try:
            sel = self.log_text.tag_ranges(tk.SEL)
            if sel:
                content = self.log_text.get(sel[0], sel[1])
            else:
                content = self.log_text.get("1.0", tk.END).strip()
            if content:
                self.clipboard_clear()
                self.clipboard_append(content)
                self.status_text.set("Текст скопирован в буфер обмена")
        except tk.TclError:
            pass

    def extract_phones_action(self):
        if not self.calendar_data and not self.input_file:
            messagebox.showwarning(
                "Нет данных", "Сначала загрузите данные из календаря или Excel."
            )
            return
        events = []
        if self.calendar_data:
            events = self.calendar_data
        else:
            try:
                xls = pd.ExcelFile(self.input_file)
                for sheet in xls.sheet_names:
                    df = pd.read_excel(self.input_file, sheet_name=sheet)
                    if "Название события" in df.columns:
                        for _, row in df.iterrows():
                            events.append(
                                {
                                    "Название события": row["Название события"],
                                    "Описание": row.get("Описание", ""),
                                }
                            )
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось прочитать файл:\n{e}")
                return

        if not events:
            messagebox.showinfo("Информация", "Нет данных для извлечения телефонов.")
            return

        phones = extract_phones_from_events(events)
        if not phones:
            messagebox.showinfo("Информация", "Телефоны не найдены в событиях.")
            return

        if self.week_start_date and self.week_end_date:
            date_prefix = (
                f"телефоны за {self.week_start_date.strftime('%d.%m.%Y')} - "
                f"{self.week_end_date.strftime('%d.%m.%Y')}"
            )
        else:
            date_prefix = "телефоны"
        default_name = f"{date_prefix}.xlsx"
        output_file = filedialog.asksaveasfilename(
            title="Сохранить телефоны",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel files", "*.xlsx")],
        )
        if not output_file:
            return
        try:
            df_out = pd.DataFrame(phones, columns=["Phone", "Name"])
            with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
                df_out.to_excel(writer, index=False, sheet_name="Телефоны")
            self.log_message(f"Телефоны сохранены в {output_file}", "success")
            messagebox.showinfo("Готово", f"Файл сохранён:\n{output_file}")
        except Exception as e:
            self.log_message(f"Ошибка при сохранении телефонов: {e}", "error")
            messagebox.showerror("Ошибка", str(e))

    def choose_week(self):
        if not is_calendar_configured():
            messagebox.showwarning(
                "Календарь не настроен",
                calendar_setup_help(),
            )
            return

        selected_date = ask_week_monday(self, self.last_monday_date)
        if selected_date is None:
            return

        self.last_monday_date = selected_date
        save_config(last_monday=selected_date)
        self.load_week_from_calendar(selected_date)

    def load_week_from_calendar(self, monday_date):
        try:
            name = calendar_display_name()
            self.log_message(f"Загрузка событий из {name}...", "info")
            events = fetch_week_events(monday_date)
            if not events:
                self.log_message("На выбранную неделю нет событий.", "warning")
                messagebox.showinfo("Информация", "Нет событий на выбранную неделю.")
                return
            self.calendar_data = events
            self.input_file = None
            self.file_path_var.set("")
            self.week_start_date = monday_date
            self.week_end_date = monday_date + timedelta(days=6)
            self.status_text.set(
                f"Загружена неделя {self.week_start_date.strftime('%d.%m.%Y')} – "
                f"{self.week_end_date.strftime('%d.%m.%Y')}. "
                "Нажмите «Сформировать план»."
            )
            self.log_message(
                f"События за неделю успешно загружены ({len(events)} записей).",
                "success",
            )
        except Exception as e:
            self.log_message(f"Ошибка загрузки: {str(e)}", "error")
            messagebox.showerror(
                "Ошибка", f"Не удалось загрузить данные:\n{str(e)}"
            )

    def choose_file(self):
        initial_dir = self.last_dir
        filename = filedialog.askopenfilename(
            title="Выберите файл Excel",
            filetypes=[("Excel files", "*.xlsx *.xls")],
            initialdir=initial_dir if initial_dir else None,
        )
        if filename:
            self.input_file = filename
            self.file_path_var.set(filename)
            self.calendar_data = None
            self.last_dir = os.path.dirname(filename)
            save_config(last_dir=self.last_dir)
            self.status_text.set("Файл выбран. Нажмите «Сформировать план».")
            self.log_message(f"Выбран файл: {os.path.basename(filename)}", "info")

    def generate_plan(self):
        if not self.input_file and not self.calendar_data:
            self.log_message("Не выбран источник данных!", "error")
            messagebox.showerror(
                "Ошибка",
                "Сначала выберите файл или загрузите неделю из календаря.",
            )
            return

        try:
            log_cb = lambda msg, tag="info": self.log_message(msg, tag)
            if self.calendar_data:
                gen = OperationPlanGenerator(
                    events_data=self.calendar_data, log_callback=log_cb
                )
            else:
                gen = OperationPlanGenerator(
                    filepath=self.input_file, log_callback=log_cb
                )

            self.log_message("Обработка событий...", "info")
            gen.parse_all_events()
            if gen.week_start is None:
                self.log_message(
                    "Не удалось определить дату начала недели.", "error"
                )
                messagebox.showerror(
                    "Ошибка", "Не удалось определить дату начала недели."
                )
                return
            self.week_start_date = gen.week_start
            self.week_end_date = gen.week_start + timedelta(days=6)
            self.log_message(
                f"Неделя: {self.week_start_date.strftime('%d.%m.%Y')} – "
                f"{self.week_end_date.strftime('%d.%m.%Y')}",
                "info",
            )
        except Exception as e:
            self.log_message(f"Ошибка при обработке данных: {str(e)}", "error")
            messagebox.showerror(
                "Ошибка", f"Ошибка при обработке данных:\n{str(e)}"
            )
            return

        date_prefix = (
            f"План операций за {self.week_start_date.strftime('%d.%m.%Y')} - "
            f"{self.week_end_date.strftime('%d.%m.%Y')}"
        )
        default_name = f"{date_prefix}.xlsx"
        output_file = filedialog.asksaveasfilename(
            title="Сохранить план операций",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel files", "*.xlsx")],
        )
        if not output_file:
            self.log_message("Сохранение отменено пользователем.", "warning")
            return

        self.progress.pack(pady=5)
        self.progress.start()
        self.status_text.set("Обработка данных...")
        self.update()

        try:
            self.log_message("Распределение пациентов...", "info")
            gen.distribute_patients()

            resolve_unknown_diagnoses(self, gen)

            gen.assign_surgeons()
            gen.sort_patients_in_rooms()
            self.log_message("Генерация Excel-файла...", "info")
            gen.generate_excel(output_file)
            self.status_text.set(f"План сохранён: {os.path.basename(output_file)}")

            self.last_dir = os.path.dirname(output_file)
            save_config(
                last_dir=self.last_dir,
                export_admissions=self.export_admissions_var.get(),
            )

            self.log_message(
                "План операций успешно сформирован и сохранён.", "success"
            )

            if self.export_admissions_var.get():
                adm_name = admissions_excel_filename(self.week_start_date)
                adm_path = os.path.join(self.last_dir, adm_name)
                gen.generate_admissions_excel(adm_path)
                self.log_message(
                    f"Список поступлений сохранён: {adm_name}", "success"
                )

            done_msg = "План операций сформирован и сохранён."
            if self.export_admissions_var.get():
                done_msg += "\nСписок поступлений сохранён рядом."
            if messagebox.askyesno(
                "Готово",
                f"{done_msg}\n\nОткрыть папку с файлом?",
            ):
                open_folder(os.path.dirname(output_file))
        except Exception as e:
            self.status_text.set("Ошибка!")
            self.log_message(f"Не удалось создать план: {str(e)}", "error")
            messagebox.showerror("Ошибка", f"Не удалось создать план:\n{str(e)}")
        finally:
            self.progress.stop()
            self.progress.pack_forget()

    def configure_surgeons(self):
        open_surgeons_dialog(self, self.log_message)

    def reconnect_calendar(self):
        if not is_calendar_configured():
            messagebox.showwarning(
                "Календарь не настроен",
                calendar_setup_help(),
            )
            return
        try:
            reauthorize()
            name = calendar_display_name()
            self.log_message(
                f"Переавторизация ({name}) выполнена успешно.", "success"
            )
            messagebox.showinfo(
                "Готово",
                "Календарь переподключён. Теперь можно загружать недели.",
            )
        except Exception as e:
            self.log_message(f"Ошибка переавторизации: {e}", "error")
            messagebox.showerror("Ошибка", str(e))

    def export_custom_diag(self):
        custom_file = patient_parser.custom_diag_file
        if not os.path.exists(custom_file):
            messagebox.showinfo(
                "Экспорт",
                "Файл пользовательских диагнозов не найден.\nНичего не экспортировано.",
            )
            return
        initial = self.last_dir if self.last_dir else "."
        path = filedialog.asksaveasfilename(
            title="Экспорт пользовательских диагнозов",
            initialdir=initial,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="custom_diagnoses.json",
        )
        if path:
            try:
                with open(custom_file, "r", encoding="utf-8") as src:
                    data = json.load(src)
                with open(path, "w", encoding="utf-8") as dst:
                    json.dump(data, dst, ensure_ascii=False, indent=2)
                self.log_message(f"Словарь экспортирован в {path}", "success")
                messagebox.showinfo("Готово", f"Файл сохранён:\n{path}")
            except Exception as e:
                self.log_message(f"Ошибка экспорта: {e}", "error")
                messagebox.showerror("Ошибка", str(e))

    def import_custom_diag(self):
        initial = self.last_dir if self.last_dir else "."
        path = filedialog.askopenfilename(
            title="Импорт пользовательских диагнозов",
            initialdir=initial,
            filetypes=[("JSON files", "*.json")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                new_data = json.load(f)
            if not isinstance(new_data, dict):
                raise ValueError("Файл должен содержать JSON-объект (словарь).")
            for key, value in new_data.items():
                if (
                    not isinstance(value, list)
                    or len(value) != 2
                    or not all(isinstance(v, str) for v in value)
                ):
                    raise ValueError(
                        f"Неверный формат значения для ключа '{key}': "
                        "ожидался список из двух строк."
                    )
            patient_parser.load_custom_diagnoses()
            for key, (diag, op) in new_data.items():
                patient_parser.diagnosis_map[key] = (diag, op)
            patient_parser.save_custom_diagnoses_full()
            patient_parser.sort_keys()
            self.log_message(
                f"Импортировано ключей: {len(new_data)}. Файл обновлён.", "success"
            )
            messagebox.showinfo(
                "Готово", f"Успешно импортировано {len(new_data)} записей."
            )
        except Exception as e:
            self.log_message(f"Ошибка импорта: {e}", "error")
            messagebox.showerror("Ошибка", str(e))


if __name__ == "__main__":
    app = App()
    app.mainloop()
