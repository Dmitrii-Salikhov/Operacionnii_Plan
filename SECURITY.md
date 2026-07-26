# Безопасность

## Автообновление

Релиз содержит `PlanOperaciy-Windows.zip` и `PlanOperaciy-Windows.zip.sha256`.

Перед установкой приложение проверяет TLS, что URL с нашего GitHub-репозитория, и SHA-256.
Установщик — `.cmd` + `tar` (без PowerShell Bypass).

## Локальные секреты

`credentials.json` и `token.pickle` в `.gitignore`. При записи — права только для текущего пользователя.

Не кладите эти файлы в облачные папки синхронизации.
