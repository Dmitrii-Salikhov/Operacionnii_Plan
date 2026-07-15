import re
from typing import List, Tuple, Dict, Any

from room_rules import is_service_event


def extract_phones_from_events(events: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """
    Извлекает номера телефонов и фамилии из списка событий.
    Возвращает список кортежей (phone, surname).
    """
    phone_name_list = []
    for ev in events:
        title = str(ev.get('Название события', '')).strip()
        desc = str(ev.get('Описание', '')).strip()
        full_text = f"{title} {desc}".strip()
        if not full_text:
            continue

        # Пропускаем служебные записи
        if is_service_event(full_text):
            continue

        # Извлекаем первый 11-значный номер, начинающийся с 7 или 8
        phone_match = re.search(r'[78]\d{10}', full_text)
        if not phone_match:
            continue
        phone = phone_match.group(0)
        if phone.startswith('8'):
            phone = '7' + phone[1:]

        # Фамилия – первое слово перед номером телефона (или первое слово в строке)
        before_phone = full_text[:phone_match.start()].strip()
        # Ищем фамилию (начинается с заглавной русской/английской буквы, может содержать дефис)
        name_match = re.search(r'[А-ЯЁA-Z][а-яёa-z\-]+', before_phone)
        if name_match:
            surname = name_match.group(0)
        else:
            words = before_phone.split()
            if words:
                surname = re.sub(r'[,.!?;:\s]+$', '', words[0])
            else:
                continue
        phone_name_list.append((phone, surname))
    return phone_name_list
