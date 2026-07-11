import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import pandas as pd
import json
import os
import sys
import subprocess
from datetime import datetime, timedelta
import logging

from phone_extractor import extract_phones_from_events
from patient_parser import patient_parser
from plan_core import OperationPlanGenerator
from google_calendar import fetch_google_calendar_events, reauthorize_google
from constants import CONFIG_FILE, OLD_CONFIG_FILE
from updater import check_for_updates, read_current_version   # <-- импорт для автообновления

def resource_path(relative_path):
    """Получить абсолютный путь к ресурсу (работает в PyInstaller и при разработке)."""
    try:
        # PyInstaller создаёт временную папку и сохраняет путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_config():
    config = {'last_dir': '', 'last_monday': None}
    if os.path.exists(OLD_CONFIG_FILE):
        try:
            with open(OLD_CONFIG_FILE, 'r') as f:
                old_data = json.load(f)
            config['last_dir'] = old_data.get('last_dir', '')
            os.remove(OLD_CONFIG_FILE)
        except:
            pass
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
            config.update(data)
        except:
            pass
    if config.get('last_monday'):
        try:
            config['last_monday'] = datetime.strptime(config['last_monday'], '%Y-%m-%d').date()
        except:
            config['last_monday'] = None
    else:
        config['last_monday'] = None
    return config

def save_config(last_dir=None, last_monday=None):
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except:
            pass
    if last_dir is not None:
        config['last_dir'] = last_dir
    if last_monday is not None:
        config['last_monday'] = last_monday.isoformat() if hasattr(last_monday, 'isoformat') else last_monday
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def open_folder(path):
    if sys.platform == "darwin":
        subprocess.call(["open", path])
    elif sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.call(["xdg-open", path])

class App(tk.Tk):
    MAX_LOG_LINES = 500   # максимальное число строк в виджете лога

    def __init__(self):
        super().__init__()
        self.title("План операций ЛОР-отделения")
        self.geometry("650x750")
        self.resizable(True, True)

        self.file_logger = logging.getLogger('plan_generator')
        self.file_logger.setLevel(logging.INFO)
        if not self.file_logger.handlers:
            fh = logging.FileHandler('plan_generator.log', encoding='utf-8')
            fh.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            fh.setFormatter(formatter)
            self.file_logger.addHandler(fh)

        config = load_config()
        self.last_dir = config.get('last_dir', '')
        self.last_monday_date = config.get('last_monday')

        self.input_file = None
        self.google_data = None
        self.week_start_date = None
        self.week_end_date = None

        self.status_text = tk.StringVar(value="Выберите источник данных и нажмите «Сформировать план»")

        # === Чтение текущей версии из папки с программой ===
        try:
            from updater import get_base_dir
            version_file = os.path.join(get_base_dir(), 'version.txt')
            with open(version_file, 'r', encoding='utf-8') as vf:
                self.current_version = vf.read().strip()
        except Exception:
            self.current_version = "?.?.?"
        # =====================================================
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Action.TButton', font=('Segoe UI', 10), padding=6)
        style.configure('Browse.TButton', font=('Segoe UI', 10), padding=4)
        style.configure('Small.TButton', font=('Segoe UI', 9), padding=4)

        main_frame = tk.Frame(self, padx=12, pady=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === Блок отображения версии ===
        self.version_label = tk.Label(
            main_frame,
            text=f"Версия: {self.current_version}",
            anchor='e',
            fg="gray",
            font=('Segoe UI', 8)
        )
        self.version_label.pack(side=tk.BOTTOM, anchor='se', pady=(0, 5))
        # ===============================

        # ===== Блок 1: Google Календарь =====
        cal_frame = tk.LabelFrame(main_frame, text=" Загрузка из Google Календаря ", padx=10, pady=10,
                                  font=('Segoe UI', 10, 'bold'))
        cal_frame.pack(fill=tk.X, pady=(0, 8))
        cal_btn = ttk.Button(cal_frame, text=" 📅 Выбрать неделю (понедельник)...",
                             command=self.choose_week, style='Action.TButton')
        cal_btn.pack(fill=tk.X)
        reconnect_btn = ttk.Button(cal_frame, text=" 🔄 Переподключить календарь",
                                   command=self.reconnect_google, style='Small.TButton')
        reconnect_btn.pack(pady=(5, 0))

        # ===== Блок 2: Excel =====
        xl_frame = tk.LabelFrame(main_frame, text=" Загрузка из Excel-файла ", padx=10, pady=10,
                                 font=('Segoe UI', 10, 'bold'))
        xl_frame.pack(fill=tk.X, pady=(0, 8))
        self.file_path_var = tk.StringVar()
        path_entry = tk.Entry(xl_frame, textvariable=self.file_path_var, state='readonly',
                              font=('Segoe UI', 9))
        path_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        browse_btn = ttk.Button(xl_frame, text=" 📂 Обзор...", command=self.choose_file,
                                style='Browse.TButton')
        browse_btn.pack(side=tk.RIGHT)

        # ===== Кнопка генерации =====
        gen_btn = ttk.Button(main_frame, text=" ▶️ Сформировать план",
                             command=self.generate_plan, style='Action.TButton')
        gen_btn.pack(pady=10, fill=tk.X)

        # ===== Кнопка выгрузки телефонов =====
        phone_btn = ttk.Button(main_frame, text=" 📞 Выгрузить телефоны",
                               command=self.extract_phones_action, style='Action.TButton')
        phone_btn.pack(pady=5, fill=tk.X)

        # ===== Кнопка настройки хирургов =====
        surg_btn = ttk.Button(main_frame, text=" 👨‍⚕️ Настроить хирургов",
                              command=self.configure_surgeons, style='Action.TButton')
        surg_btn.pack(pady=5, fill=tk.X)

        # ===== КНОПКА ПРОВЕРКИ ОБНОВЛЕНИЙ =====
        update_btn = ttk.Button(main_frame, text=" 🔄 Проверить обновления",
                                command=self.check_updates_action, style='Action.TButton')
        update_btn.pack(pady=5, fill=tk.X)

        # ===== Блок 3: Пользовательские диагнозы =====
        diag_frame = tk.LabelFrame(main_frame, text=" Пользовательские диагнозы ", padx=10, pady=10,
                                   font=('Segoe UI', 10, 'bold'))
        diag_frame.pack(fill=tk.X, pady=(0, 8))
        diag_buttons = tk.Frame(diag_frame)
        diag_buttons.pack(fill=tk.X)
        export_btn = ttk.Button(diag_buttons, text="📤 Экспорт словаря", command=self.export_custom_diag,
                                style='Small.TButton')
        export_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        import_btn = ttk.Button(diag_buttons, text="📥 Импорт словаря", command=self.import_custom_diag,
                                style='Small.TButton')
        import_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # ===== Статус =====
        status_label = tk.Label(main_frame, textvariable=self.status_text, anchor='w',
                                fg="#555", font=('Segoe UI', 9))
        status_label.pack(fill=tk.X, pady=(0, 6))

        # ===== Лог =====
        log_header = tk.Label(main_frame, text="Пояснения / предупреждения (Ctrl+C / ⌘C — копировать):",
                              anchor='w', font=('Segoe UI', 9, 'bold'))
        log_header.pack(fill=tk.X)
        log_frame = tk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.log_text = tk.Text(log_frame, height=8, state='normal', bg='white', wrap='word',
                                font=('Consolas', 9))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.log_text.yview)

        self.log_text.bind("<Command-c>", self.copy_log)
        self.log_text.bind("<Control-c>", self.copy_log)

        self.log_text.tag_configure('info', foreground='black')
        self.log_text.tag_configure('warning', foreground='#E67E22')
        self.log_text.tag_configure('error', foreground='#E74C3C')
        self.log_text.tag_configure('success', foreground='#27AE60')

        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.log_message("Готов к работе. Выберите источник данных.", tag='success')

    # === Новый метод для ручной проверки обновлений ===
    def check_updates_action(self):
        """Обработчик кнопки 'Проверить обновления'."""
        self.log_message("Проверка обновлений...", 'info')
        check_for_updates(self.current_version)
        self.log_message("Проверка обновлений завершена.", 'info')
    # =================================================

    def _trim_log(self):
        """Удаляет старые строки, если их больше MAX_LOG_LINES."""
        lines = self.log_text.get('1.0', 'end-1c').split('\n')
        if len(lines) > self.MAX_LOG_LINES:
            # Оставляем последние MAX_LOG_LINES строк
            new_text = '\n'.join(lines[-self.MAX_LOG_LINES:])
            self.log_text.delete('1.0', tk.END)
            self.log_text.insert('1.0', new_text)

    def log_message(self, msg, tag='info'):
        """Добавляет сообщение с временной меткой и прокручивает лог вниз."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_msg = f"[{timestamp}] {msg}"
        self.log_text.insert(tk.END, formatted_msg + "\n", tag)
        self._trim_log()
        self.log_text.see(tk.END)   # прокрутка к последней записи
        if tag == 'error':
            self.file_logger.error(formatted_msg)
        elif tag == 'warning':
            self.file_logger.warning(formatted_msg)
        else:
            self.file_logger.info(formatted_msg)
        self.update_idletasks()

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

    # ---------- Выгрузка телефонов ----------
    def extract_phones_action(self):
        if not self.google_data and not self.input_file:
            messagebox.showwarning("Нет данных", "Сначала загрузите данные из календаря или Excel.")
            return
        events = []
        if self.google_data:
            events = self.google_data
        else:
            try:
                xls = pd.ExcelFile(self.input_file)
                for sheet in xls.sheet_names:
                    df = pd.read_excel(self.input_file, sheet_name=sheet)
                    if 'Название события' in df.columns:
                        for _, row in df.iterrows():
                            events.append({
                                'Название события': row['Название события'],
                                'Описание': row.get('Описание', '')
                            })
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
            date_prefix = f"телефоны за {self.week_start_date.strftime('%d.%m.%Y')} - {self.week_end_date.strftime('%d.%m.%Y')}"
        else:
            date_prefix = "телефоны"
        default_name = f"{date_prefix}.xlsx"
        output_file = filedialog.asksaveasfilename(
            title="Сохранить телефоны",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not output_file:
            return
        try:
            df_out = pd.DataFrame(phones, columns=['Phone', 'Name'])
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                df_out.to_excel(writer, index=False, sheet_name='Телефоны')
            self.log_message(f"Телефоны сохранены в {output_file}", 'success')
            messagebox.showinfo("Готово", f"Файл сохранён:\n{output_file}")
        except Exception as e:
            self.log_message(f"Ошибка при сохранении телефонов: {e}", 'error')
            messagebox.showerror("Ошибка", str(e))

    # ---------- Выбор недели из Google Календаря ----------
    def choose_week(self):
        if not os.path.exists('credentials.json'):
            messagebox.showwarning(
                "Файл ключа не найден",
                "Отсутствует файл credentials.json, необходимый для доступа к Google Календарю.\n\n"
                "Пожалуйста, получите его в Google Cloud Console:\n"
                "APIs & Services → Credentials → Create OAuth client ID (тип Desktop app)\n"
                "и сохраните скачанный JSON под именем credentials.json в папке с программой.\n\n"
                "Пока вы можете загрузить данные из Excel-файла."
            )
            return

        dialog = tk.Toplevel(self)
        dialog.title("Выберите понедельник нужной недели")
        dialog.geometry("400x360")
        dialog.resizable(False, False)
        dialog.transient(self)

        tk.Label(dialog, text="Выберите дату понедельника:", font=('Segoe UI', 10)).pack(pady=(15, 5))

        from tkcalendar import Calendar
        cal = Calendar(dialog, date_pattern='dd.MM.yyyy', locale='ru_RU', selectmode='day')
        cal.pack(pady=10)

        if self.last_monday_date is not None:
            cal.selection_set(self.last_monday_date)

        def on_ok():
            selected_date = cal.selection_get()
            if selected_date.weekday() != 0:
                monday = selected_date - timedelta(days=selected_date.weekday())
                confirm = messagebox.askyesno("Не понедельник",
                                              f"Вы выбрали {selected_date.strftime('%d.%m.%Y')}, это не понедельник.\n"
                                              f"Взять ближайший понедельник {monday.strftime('%d.%m.%Y')}?")
                if not confirm:
                    return
                selected_date = monday

            today = datetime.now().date()
            if selected_date < today:
                if not messagebox.askyesno("Неделя в прошлом",
                                           f"Вы выбрали неделю, начинающуюся {selected_date.strftime('%d.%m.%Y')}, "
                                           "которая уже прошла.\nПродолжить?"):
                    return

            self.last_monday_date = selected_date
            save_config(last_monday=selected_date)

            dialog.destroy()
            self.load_week_from_google(selected_date)

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="Загрузить", command=on_ok, font=('Segoe UI', 10), width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Отмена", command=dialog.destroy, font=('Segoe UI', 10), width=10).pack(side=tk.LEFT, padx=5)

        dialog.grab_set()
        dialog.wait_window()

    def load_week_from_google(self, monday_date):
        try:
            self.log_message("Загрузка событий из Google Календаря...", 'info')
            events = fetch_google_calendar_events(monday_date)
            if not events:
                self.log_message("На выбранную неделю нет событий.", 'warning')
                messagebox.showinfo("Информация", "Нет событий на выбранную неделю.")
                return
            self.google_data = events
            self.input_file = None
            self.file_path_var.set("")
            self.week_start_date = monday_date
            self.week_end_date = monday_date + timedelta(days=6)
            self.status_text.set(f"Загружена неделя {self.week_start_date.strftime('%d.%m.%Y')} – "
                                 f"{self.week_end_date.strftime('%d.%m.%Y')}. "
                                 "Нажмите «Сформировать план».")
            self.log_text.delete("1.0", tk.END)
            self.log_message(f"События за неделю успешно загружены ({len(events)} записей).", 'success')
        except Exception as e:
            self.log_message(f"Ошибка загрузки: {str(e)}", 'error')
            messagebox.showerror("Ошибка", f"Не удалось загрузить данные:\n{str(e)}")

    def choose_file(self):
        initial_dir = self.last_dir
        filename = filedialog.askopenfilename(
            title="Выберите файл Excel",
            filetypes=[("Excel files", "*.xlsx *.xls")],
            initialdir=initial_dir if initial_dir else None
        )
        if filename:
            self.input_file = filename
            self.file_path_var.set(filename)
            self.google_data = None
            self.last_dir = os.path.dirname(filename)
            save_config(last_dir=self.last_dir)
            self.status_text.set("Файл выбран. Нажмите «Сформировать план».")
            self.log_message(f"Выбран файл: {os.path.basename(filename)}", 'info')

    def generate_plan(self):
        if not self.input_file and not self.google_data:
            self.log_message("Не выбран источник данных!", 'error')
            messagebox.showerror("Ошибка", "Сначала выберите файл или загрузите неделю из календаря.")
            return

        self.log_text.delete("1.0", tk.END)
        try:
            log_cb = lambda msg, tag='info': self.log_message(msg, tag)
            if self.google_data:
                gen = OperationPlanGenerator(events_data=self.google_data, log_callback=log_cb)
            else:
                gen = OperationPlanGenerator(filepath=self.input_file, log_callback=log_cb)

            self.log_message("Обработка событий...", 'info')
            gen.parse_all_events()
            if gen.week_start is None:
                self.log_message("Не удалось определить дату начала недели.", 'error')
                messagebox.showerror("Ошибка", "Не удалось определить дату начала недели.")
                return
            self.week_start_date = gen.week_start
            self.week_end_date = gen.week_start + timedelta(days=6)
            self.log_message(f"Неделя: {self.week_start_date.strftime('%d.%m.%Y')} – {self.week_end_date.strftime('%d.%m.%Y')}", 'info')
        except Exception as e:
            self.log_message(f"Ошибка при обработке данных: {str(e)}", 'error')
            messagebox.showerror("Ошибка", f"Ошибка при обработке данных:\n{str(e)}")
            return

        date_prefix = f"План операций за {self.week_start_date.strftime('%d.%m.%Y')} - {self.week_end_date.strftime('%d.%m.%Y')}"
        default_name = f"{date_prefix}.xlsx"
        output_file = filedialog.asksaveasfilename(
            title="Сохранить план операций",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not output_file:
            self.log_message("Сохранение отменено пользователем.", 'warning')
            return

        self.progress.pack(pady=5)
        self.progress.start()
        self.status_text.set("Обработка данных...")
        self.update()

        try:
            self.log_message("Распределение пациентов...", 'info')
            gen.distribute_patients()

            self.resolve_unknown_diagnoses(gen)

            gen.assign_surgeons()
            gen.sort_patients_in_rooms()
            self.log_message("Генерация Excel-файла...", 'info')
            gen.generate_excel(output_file)
            self.status_text.set(f"План сохранён: {os.path.basename(output_file)}")

            self.last_dir = os.path.dirname(output_file)
            save_config(last_dir=self.last_dir)

            self.log_message("План операций успешно сформирован и сохранён.", 'success')
            if messagebox.askyesno("Готово", "План операций сформирован и сохранён.\n\nОткрыть папку с файлом?"):
                open_folder(os.path.dirname(output_file))
        except Exception as e:
            self.status_text.set("Ошибка!")
            self.log_message(f"Не удалось создать план: {str(e)}", 'error')
            messagebox.showerror("Ошибка", f"Не удалось создать план:\n{str(e)}")
        finally:
            self.progress.stop()
            self.progress.pack_forget()

    def resolve_unknown_diagnoses(self, gen):
        unknown = []
        for day in range(5):
            for room in ["5", "7", "MA"]:
                for p in gen.daily_blocks[day][room]:
                    if p.get('is_unknown_diag'):
                        unknown.append(p)
        if not unknown:
            return

        top = tk.Toplevel(self)
        top.title("Уточнение неизвестных диагнозов")
        top.geometry("900x500")
        top.transient(self)
        top.grab_set()

        frame = ttk.Frame(top, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        columns = ('name', 'raw', 'diag', 'oper')
        tree = ttk.Treeview(frame, columns=columns, show='headings', selectmode='browse')
        tree.heading('name', text='ФИО')
        tree.heading('raw', text='Исходный текст')
        tree.heading('diag', text='Диагноз')
        tree.heading('oper', text='Операция')
        tree.column('name', width=180)
        tree.column('raw', width=250)
        tree.column('diag', width=250)
        tree.column('oper', width=200)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)

        for p in unknown:
            tree.insert('', tk.END, iid=str(id(p)), values=(
                p['name'],
                p.get('diagnosis_raw', ''),
                p.get('diagnosis', 'Диагноз не указан'),
                p.get('operation', 'Операция не указана')
            ))

        def on_double_click(event):
            item = tree.selection()[0]
            if not item:
                return
            p = None
            for cand in unknown:
                if str(id(cand)) == item:
                    p = cand
                    break
            if not p:
                return
            self.edit_unknown_patient(p, tree)

        tree.bind('<Double-1>', on_double_click)

        btn_frame = ttk.Frame(top)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Уточнить выделенного", command=lambda: on_double_click(None)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Закрыть", command=top.destroy).pack(side=tk.LEFT, padx=5)

        self.wait_window(top)

    def edit_unknown_patient(self, patient, tree):
        edit = tk.Toplevel(self)
        edit.title("Редактирование диагноза")
        edit.geometry("500x250")
        edit.transient(self)
        edit.grab_set()

        ttk.Label(edit, text="Ключевая фраза (можно выбрать или ввести свою):").pack(pady=(10,0))
        key_var = tk.StringVar(value=patient.get('diagnosis_raw', ''))
        keys = list(patient_parser.diagnosis_map.keys())
        key_combo = ttk.Combobox(edit, textvariable=key_var, values=keys, state='normal')
        key_combo.pack(fill=tk.X, padx=10, pady=2)

        ttk.Label(edit, text="Диагноз:").pack()
        diag_var = tk.StringVar(value=patient.get('diagnosis', 'Диагноз не указан'))
        diag_vals = [v[0] for v in patient_parser.diagnosis_map.values()]
        diag_combo = ttk.Combobox(edit, textvariable=diag_var, values=diag_vals, state='normal')
        diag_combo.pack(fill=tk.X, padx=10, pady=2)

        ttk.Label(edit, text="Операция:").pack()
        oper_var = tk.StringVar(value=patient.get('operation', 'Операция не указана'))
        oper_vals = [v[1] for v in patient_parser.diagnosis_map.values()]
        oper_combo = ttk.Combobox(edit, textvariable=oper_var, values=oper_vals, state='normal')
        oper_combo.pack(fill=tk.X, padx=10, pady=2)

        def apply():
            key = key_var.get().strip()
            diag = diag_var.get().strip()
            oper = oper_var.get().strip()
            if not key or not diag or not oper:
                messagebox.showerror("Ошибка", "Все поля должны быть заполнены.")
                return
            patient['diagnosis_raw'] = key
            patient['diagnosis'] = diag
            patient['operation'] = oper
            patient['is_unknown_diag'] = False

            patient_parser.save_custom_diagnosis(key, diag, oper)

            if tree:
                for item in tree.get_children():
                    if tree.item(item)['values'][0] == patient['name']:
                        tree.item(item, values=(
                            patient['name'],
                            patient.get('diagnosis_raw', ''),
                            diag,
                            oper
                        ))
                        break
            edit.destroy()

        ttk.Button(edit, text="Применить", command=apply).pack(pady=10)

    # ---------- Настройка хирургов ----------
    def configure_surgeons(self):
        import config_surgeons

        top = tk.Toplevel(self)
        top.title("Настройка хирургов")
        top.geometry("550x550")
        top.transient(self)
        top.grab_set()

        notebook = ttk.Notebook(top)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ----- Вкладка "Общий список" -----
        tab_list = ttk.Frame(notebook)
        notebook.add(tab_list, text="Общий список")

        list_frame = tk.Frame(tab_list)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.surgeons_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=('Segoe UI', 11))
        self.surgeons_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.surgeons_listbox.yview)

        btn_frame_list = tk.Frame(tab_list)
        btn_frame_list.pack(pady=5)
        ttk.Button(btn_frame_list, text="Добавить", command=self.add_surgeon).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_list, text="Удалить", command=self.remove_surgeon).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame_list, text="Переименовать", command=self.rename_surgeon).pack(side=tk.LEFT, padx=5)

        # ----- Вкладка "Расписание" -----
        tab_sched = ttk.Frame(notebook)
        notebook.add(tab_sched, text="Расписание")

        sched_frame = tk.Frame(tab_sched)
        sched_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.schedule_combos = {}
        days = ["Пн", "Вт", "Ср", "Чт", "Пт"]
        ops = ["№5", "№7", "М/А"]

        # Заголовки дней
        tk.Label(sched_frame, text="", width=8).grid(row=0, column=0)
        for col_idx, day in enumerate(days):
            tk.Label(sched_frame, text=day, font=('Segoe UI', 10, 'bold')).grid(row=0, column=col_idx+1, padx=5)

        for row_idx, op in enumerate(ops):
            tk.Label(sched_frame, text=op, font=('Segoe UI', 10, 'bold')).grid(row=row_idx+1, column=0, padx=10, pady=5, sticky='w')
            for col_idx, day in enumerate(days):
                combo = ttk.Combobox(sched_frame, values=self.get_surgeons_list(), width=20)
                combo.grid(row=row_idx+1, column=col_idx+1, padx=5, pady=3)
                self.schedule_combos[(op, day)] = combo

        # ----- Вкладка "Запреты для М/А" -----
        tab_forbid = ttk.Frame(notebook)
        notebook.add(tab_forbid, text="Запреты для М/А")

        forbid_frame = tk.Frame(tab_forbid)
        forbid_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.forbid_listbox = tk.Listbox(forbid_frame, selectmode=tk.MULTIPLE, font=('Segoe UI', 11))
        self.forbid_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        forbid_scroll = tk.Scrollbar(forbid_frame, command=self.forbid_listbox.yview)
        forbid_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.forbid_listbox.config(yscrollcommand=forbid_scroll.set)

        # Кнопка сохранения
        save_btn = ttk.Button(top, text="Сохранить все изменения", command=lambda: self.save_surgeons(top))
        save_btn.pack(pady=10)

        self.refresh_surgeons_ui()

    def get_surgeons_list(self):
        import config_surgeons
        all_names = set(config_surgeons.FORBIDDEN_MA)
        for v in config_surgeons.SURGEON_5.values():
            all_names.add(v)
        all_names.add(config_surgeons.SURGEON_7)
        for v in config_surgeons.SURGEON_MA.values():
            all_names.add(v)
        return sorted(all_names)

    def refresh_surgeons_ui(self):
        import config_surgeons
        self.surgeons_listbox.delete(0, tk.END)
        for name in self.get_surgeons_list():
            self.surgeons_listbox.insert(tk.END, name)

        updated_list = self.get_surgeons_list()
        for combo in self.schedule_combos.values():
            combo['values'] = updated_list

        days = ["Пн", "Вт", "Ср", "Чт", "Пт"]
        for i, day in enumerate(days):
            self.schedule_combos[("№5", day)].set(config_surgeons.SURGEON_5.get(i, ""))
            self.schedule_combos[("№7", day)].set(config_surgeons.SURGEON_7)
            self.schedule_combos[("М/А", day)].set(config_surgeons.SURGEON_MA.get(i, ""))

        self.forbid_listbox.delete(0, tk.END)
        for name in self.get_surgeons_list():
            self.forbid_listbox.insert(tk.END, name)
            if name in config_surgeons.FORBIDDEN_MA:
                idx = self.forbid_listbox.size() - 1
                self.forbid_listbox.selection_set(idx)

    def add_surgeon(self):
        new_name = simpledialog.askstring("Добавить хирурга", "Введите ФИО нового хирурга:")
        if new_name:
            new_name = new_name.strip()
            if new_name and new_name not in self.get_surgeons_list():
                import config_surgeons
                config_surgeons.SURGEON_MA[99] = new_name
                config_surgeons.save_surgeons(config_surgeons.SURGEON_5, config_surgeons.SURGEON_7,
                                             config_surgeons.SURGEON_MA, config_surgeons.FORBIDDEN_MA)
                self.refresh_surgeons_ui()
                self.log_message(f"Хирург '{new_name}' добавлен.", 'success')

    def remove_surgeon(self):
        sel = self.surgeons_listbox.curselection()
        if not sel:
            messagebox.showwarning("Не выбрано", "Выберите хирурга для удаления.")
            return
        name = self.surgeons_listbox.get(sel[0])
        import config_surgeons
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
            config_surgeons.save_surgeons(config_surgeons.SURGEON_5, config_surgeons.SURGEON_7,
                                         config_surgeons.SURGEON_MA, config_surgeons.FORBIDDEN_MA)
            self.refresh_surgeons_ui()
            self.log_message(f"Хирург '{name}' удалён.", 'warning')

    def rename_surgeon(self):
        sel = self.surgeons_listbox.curselection()
        if not sel:
            messagebox.showwarning("Не выбрано", "Выберите хирурга для переименования.")
            return
        old_name = self.surgeons_listbox.get(sel[0])
        new_name = simpledialog.askstring("Переименовать хирурга", f"Новое имя для '{old_name}':")
        if new_name and new_name.strip() != old_name:
            new_name = new_name.strip()
            import config_surgeons
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
                config_surgeons.save_surgeons(config_surgeons.SURGEON_5, config_surgeons.SURGEON_7,
                                             config_surgeons.SURGEON_MA, config_surgeons.FORBIDDEN_MA)
                self.refresh_surgeons_ui()
                self.log_message(f"Хирург '{old_name}' переименован в '{new_name}'.", 'info')

    def save_surgeons(self, dialog):
        import config_surgeons
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
        config_surgeons.SURGEON_5, config_surgeons.SURGEON_7, config_surgeons.SURGEON_MA, config_surgeons.FORBIDDEN_MA = surg_5, surg_7, surg_ma, forbidden
        self.log_message("Расписание хирургов обновлено.", 'success')
        messagebox.showinfo("Готово", "Расписание хирургов сохранено.")
        dialog.destroy()

    # ---------- Переподключение календаря ----------
    def reconnect_google(self):
        if not os.path.exists('credentials.json'):
            messagebox.showwarning("Файл ключа не найден", "Для переподключения нужен credentials.json")
            return
        try:
            reauthorize_google()
            self.log_message("Переавторизация Google Календаря выполнена успешно.", 'success')
            messagebox.showinfo("Готово", "Календарь переподключён. Теперь можно загружать недели.")
        except Exception as e:
            self.log_message(f"Ошибка переавторизации: {e}", 'error')
            messagebox.showerror("Ошибка", str(e))

    # ---------- Экспорт/импорт пользовательских диагнозов ----------
    def export_custom_diag(self):
        custom_file = patient_parser.custom_diag_file
        if not os.path.exists(custom_file):
            messagebox.showinfo("Экспорт", "Файл пользовательских диагнозов не найден.\nНичего не экспортировано.")
            return
        initial = self.last_dir if self.last_dir else "."
        path = filedialog.asksaveasfilename(
            title="Экспорт пользовательских диагнозов",
            initialdir=initial,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="custom_diagnoses.json"
        )
        if path:
            try:
                with open(custom_file, 'r', encoding='utf-8') as src:
                    data = json.load(src)
                with open(path, 'w', encoding='utf-8') as dst:
                    json.dump(data, dst, ensure_ascii=False, indent=2)
                self.log_message(f"Словарь экспортирован в {path}", 'success')
                messagebox.showinfo("Готово", f"Файл сохранён:\n{path}")
            except Exception as e:
                self.log_message(f"Ошибка экспорта: {e}", 'error')
                messagebox.showerror("Ошибка", str(e))

    def import_custom_diag(self):
        initial = self.last_dir if self.last_dir else "."
        path = filedialog.askopenfilename(
            title="Импорт пользовательских диагнозов",
            initialdir=initial,
            filetypes=[("JSON files", "*.json")]
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                new_data = json.load(f)
            if not isinstance(new_data, dict):
                raise ValueError("Файл должен содержать JSON-объект (словарь).")
            for key, value in new_data.items():
                if not isinstance(value, list) or len(value) != 2 or not all(isinstance(v, str) for v in value):
                    raise ValueError(f"Неверный формат значения для ключа '{key}': ожидался список из двух строк.")
            patient_parser.load_custom_diagnoses()
            for key, (diag, op) in new_data.items():
                patient_parser.diagnosis_map[key] = (diag, op)
            patient_parser.save_custom_diagnoses_full()
            patient_parser.sort_keys()
            self.log_message(f"Импортировано ключей: {len(new_data)}. Файл обновлён.", 'success')
            messagebox.showinfo("Готово", f"Успешно импортировано {len(new_data)} записей.")
        except Exception as e:
            self.log_message(f"Ошибка импорта: {e}", 'error')
            messagebox.showerror("Ошибка", str(e))

if __name__ == "__main__":
    app = App()
    app.mainloop()