import json
import os

SURGEON_CONFIG_FILE = "surgeons.json"

# Значения по умолчанию
DEFAULT_SURGEON_5 = {
    0: "Баганов Д.Г.", 1: "Гасанов М.Т.", 2: "Карибова С.О.",
    3: "Салихов Д.А.", 4: "Гасанов М.Т."
}
DEFAULT_SURGEON_7 = "Доронина Н.С."
DEFAULT_SURGEON_MA = {
    0: "Карибова С.О.", 1: "Баганов Д.Г.", 2: "Гасанов М.Т.",
    3: "Карибова С.О.", 4: "Баганов Д.Г."
}
DEFAULT_FORBIDDEN_MA = ["Салихов Д.А.", "Доронина Н.С."]

def load_surgeons():
    """Загружает расписание хирургов из JSON или возвращает умолчания."""
    if os.path.exists(SURGEON_CONFIG_FILE):
        with open(SURGEON_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        surg5 = {int(k): v for k, v in data.get("SURGEON_5", {}).items()}
        surg7 = data.get("SURGEON_7", DEFAULT_SURGEON_7)
        surgMA = {int(k): v for k, v in data.get("SURGEON_MA", {}).items()}
        forbidden = data.get("FORBIDDEN_MA", DEFAULT_FORBIDDEN_MA)
        return surg5, surg7, surgMA, forbidden
    else:
        save_surgeons(DEFAULT_SURGEON_5, DEFAULT_SURGEON_7, DEFAULT_SURGEON_MA, DEFAULT_FORBIDDEN_MA)
        return DEFAULT_SURGEON_5, DEFAULT_SURGEON_7, DEFAULT_SURGEON_MA, DEFAULT_FORBIDDEN_MA

def save_surgeons(surgeon_5, surgeon_7, surgeon_ma, forbidden_ma):
    """Сохраняет расписание в JSON."""
    data = {
        "SURGEON_5": {str(k): v for k, v in surgeon_5.items()},
        "SURGEON_7": surgeon_7,
        "SURGEON_MA": {str(k): v for k, v in surgeon_ma.items()},
        "FORBIDDEN_MA": forbidden_ma
    }
    with open(SURGEON_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Глобальные переменные, используемые в plan_core
SURGEON_5, SURGEON_7, SURGEON_MA, FORBIDDEN_MA = load_surgeons()