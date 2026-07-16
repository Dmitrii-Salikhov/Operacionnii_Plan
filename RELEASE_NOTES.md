## Исправления

- **Календарь / ошибка 404:** шаблонные адреса из `calendars.example.json` (`your-first-calendar@gmail.com` и т.п.) больше не отправляются в Google API.
- Если календари не заданы или указан несуществующий ID — показывается понятное сообщение вместо сырого `HttpError 404`.
- В `calendars.example.json` список `calendar_ids` по умолчанию пустой: нужно указать реальные email/ID в `calendars.json` рядом с программой.

## После установки / обновления

Убедитесь, что рядом с `PlanOperaciy.exe` есть файл `calendars.json` с вашими календарями, например:

```json
{
  "provider": "google",
  "calendar_ids": [
    "your-real-calendar@gmail.com"
  ]
}
```

## Целостность

Проверьте `PlanOperaciy-Windows.zip.sha256` (SHA-256). Клиент обновлений откажется ставить релиз без совпадения контрольной суммы.
