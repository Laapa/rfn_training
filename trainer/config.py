"""Файл настроек training_config.json рядом с программой.
Нет файла - создаём со значениями по умолчанию (как старая программа)."""
import json
import os

PATH = "training_config.json"

DEFAULTS = {
    "tick_ms": 1000,        # 1 тик алгоритма = 1 с. Для симулятора можно 200 (в 5 раз быстрее)
    "vac_coeff": 1500.0,    # Торр = ток насоса (А) / vac_coeff
    "r_sh": 3.19e6,         # шунтовое сопротивление, Ом (для U НО)
    "u_otr_max": 6.0,       # отражённая мощность выше этого - красным, кВт
    "history_s": 7200,      # сколько секунд держать на графиках (x_time)
    "data_dir": "data",     # куда писать .dat
    "resonators": [         # type: "sim" сейчас, "tango" - когда будут атрибуты
        {"name": "Резонатор 1", "type": "sim"},
        {"name": "Резонатор 2", "type": "sim"},
        {"name": "Резонатор 3", "type": "sim"},
    ],
}


def load():
    """Возвращает (config, сообщение)."""
    if not os.path.exists(PATH):
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, indent=4, ensure_ascii=False)
        return dict(DEFAULTS), f"Файл {PATH} не найден - создан с настройками по умолчанию"
    with open(PATH, encoding="utf-8") as f:
        config = json.load(f)
    return {**DEFAULTS, **config}, f"Настройки прочитаны из {PATH}"
