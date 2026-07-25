## Миграция на 2.0 (Electron)

Дистрибутив Windows больше не один PyInstaller-exe «всё в одном», а папка Electron (`PlanOperaciy.exe` + `resources/backend/`).

### Что сохранить при обновлении с 1.x

Положите **рядом с `PlanOperaciy.exe`** (не внутрь `resources/`):

| Файл | Назначение |
|------|------------|
| `calendars.json` | список ID/email календарей |
| `credentials.json` | OAuth client Google |
| `token.pickle` | сохранённый вход Google |
| `surgeons.json` | расписание хирургов |
| `custom_diagnoses.json` | пользовательский словарь |
| `app_config.json` | last_dir / тема / флаги |

Автообновление (zip + SHA-256) **не удаляет** эти файлы: в архив они не входят, `Expand-Archive -Force` их не трогает.

### Первый запуск 2.0 с нуля

1. Распакуйте `PlanOperaciy-Windows.zip`.
2. Запустите `PlanOperaciy.exe`.
3. Мастер предложит создать файлы из примеров → заполните `credentials.json`.
4. «Календари…» → добавьте ID → при необходимости «Переподключить Google».

### Smoke-проверка после сборки

1. Календари настроены, OAuth проходит.
2. Выбрать неделю → в статусе есть счётчики по ID.
3. Сформировать план → Excel открывается, опционально список поступлений.
4. «Обновления» → проверка GitHub (на Windows — «Скачать и установить» при новой версии).
