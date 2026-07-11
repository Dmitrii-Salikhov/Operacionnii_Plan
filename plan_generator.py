from app_gui import App
from updater import check_for_updates, read_current_version

if __name__ == "__main__":
    # Автоматическая проверка обновлений (без лишних окон, если версия актуальна)
    current_ver = read_current_version()
    check_for_updates(current_ver, silent_if_updated=True)

    # Запускаем основное приложение
    app = App()
    app.mainloop()