"""Файл настроек training_config.json рядом с программой (рядом с exe, если собрано в exe).
Нет файла - создаём со значениями по умолчанию (как старая программа).
Другой файл можно указать при запуске:  python main.py fake_config.json"""
import json
import os
import sys

# папка программы: рядом с exe (если собрано PyInstaller'ом) или текущая папка
BASE = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
PATH = os.path.join(BASE, "training_config.json")

DEFAULTS = {
    "tick_ms": 1000,        # 1 тик алгоритма = 1 с. Для симулятора можно 200 (в 5 раз быстрее)
    "vac_coeff": 1500.0,    # Торр = ток насоса (А) / vac_coeff
    "r_sh": 3.19e6,         # шунтовое сопротивление, Ом (для U НО)
    "u_otr_max": 6.0,       # отражённая мощность выше этого - красным, кВт
    "history_s": 7200,      # сколько секунд держать на графиках (x_time)
    "data_dir": "data",     # куда писать .dat
    "dark_theme": False,    # тёмная тема (галка в окне «Обзор»)
    "u_max_kv": 30.0,       # предел уставки U (UcavSetpoint 0..30 кВ)
    "i_max_a": 10.0,        # предел уставки I фидера (IfidSetpoint 0..10 А)
    "tango_host": "",       # например "host:10000"; пусто - берётся из переменной TANGO_HOST
    "vac_is_current": False,  # True, если cav/Vac отдаёт ток насоса (А), а не Торр
    # type: "sim" - встроенный симулятор, "tango" - резонатор через Tango.
    # prefix: начало имени устройств, prefix/mod, prefix/cav, prefix/sspa (у резонаторов отличается цифрами)
    # nodb: true - устройство без базы Tango (фейковый сервер fake_server/fake_rf.py)
    # settings: настройки окна (Low, High, пороги...) - программа сама сохраняет их сюда
    "resonators": [
        {"name": "Резонатор 1", "type": "sim", "prefix": "rf2/1e2"},
        {"name": "Резонатор 2", "type": "sim", "prefix": "rf3/1e3"},
        {"name": "Резонатор 3", "type": "sim", "prefix": "rf4/1e4"},
    ],
}


def load(path=None):
    """Возвращает (config, сообщение). path - другой файл настроек (необязательно)."""
    global PATH
    if path:
        PATH = os.path.abspath(path)
    if os.path.exists(PATH):
        with open(PATH, encoding="utf-8") as f:
            config = {**DEFAULTS, **json.load(f)}      # новые параметры подтянутся из DEFAULTS
        message = f"Настройки прочитаны из {PATH}"
    else:
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, indent=4, ensure_ascii=False)
        config = json.loads(json.dumps(DEFAULTS))      # копия, чтобы не портить DEFAULTS
        message = f"Файл {PATH} не найден - создан с настройками по умолчанию"
    config["data_dir"] = os.path.join(os.path.dirname(PATH), config["data_dir"])   # data - рядом с настройками
    return config, message


def save(config):
    data = dict(config)
    data["data_dir"] = os.path.relpath(config["data_dir"], os.path.dirname(PATH))   # хранить коротко
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
