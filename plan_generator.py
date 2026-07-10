from app_gui import App
from updater import check_for_updates, read_current_version

if __name__ == "__main__":
    # Проверяем обновления перед запуском GUI
    current_ver = read_current_version()
    check_for_updates(current_ver)

    # Запускаем основное приложение
    app = App()
    app.mainloop()