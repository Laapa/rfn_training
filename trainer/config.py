"""Файлы настроек рядом с программой (рядом с exe, если собрано в exe):
    tango_config.json  - стенд через Tango      } при запуске программа спрашивает,
    epics_config.json  - стенд через EPICS (CA) } какой из них взять (main.py)
Нет файла - создаём со значениями по умолчанию и резонаторами нужного типа.
Другой файл можно указать при запуске (тогда без вопроса):  python main.py fake_config.json"""
import json
import os
import sys

# папка программы: рядом с exe (если собрано PyInstaller'ом) или текущая папка
BASE = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
PATH = os.path.join(BASE, "training_config.json")
STACK_FILES = {"tango": "tango_config.json", "epics": "epics_config.json"}   # выбор при запуске

DEFAULTS = {
    "tick_ms": 1000,        # 1 тик алгоритма = 1 с. Для симулятора можно 200 (в 5 раз быстрее)
    "vac_coeff": 1500.0,    # Торр = ток насоса (А) / vac_coeff
    "r_sh": 3.19e6,         # шунтовое сопротивление, Ом (для U НО)
    "u_otr_max": 6.0,       # отражённая мощность выше этого - красным, кВт
    "history_s": 7200,      # сколько секунд держать на графиках (x_time)
    "data_dir": "data",     # куда писать .dat
    "u_max_kv": 30.0,       # предел уставки U (UcavSetpoint 0..30 кВ)
    "i_max_a": 10.0,        # предел уставки I фидера (IfidSetpoint 0..10 А)
    "tango_host": "",       # например "host:10000"; пусто - берётся из переменной TANGO_HOST
    # EPICS: где искать IOC, например "10.0.0.5 10.0.0.6"; пусто - из переменной EPICS_CA_ADDR_LIST
    # (или широковещательный поиск в своей подсети)
    "epics_ca_addr_list": "",
    "vac_is_current": False,  # True, если cav/Vac отдаёт ток насоса (А), а не Торр
    # type: "sim" - встроенный симулятор, "tango" - резонатор через Tango, "epics" - через EPICS.
    # Для epics: prefix - начало имён PV (RF2 -> RF2:MOD:Ucav ...), "pv": {...} - заменить отдельные имена
    # prefix: начало имени устройств, prefix/mod, prefix/cav, prefix/sspa (у резонаторов отличается цифрами)
    # nodb: true - устройство без базы Tango (фейковый сервер fake_server/fake_rf.py)
    # settings: настройки окна (Low, High, пороги...) - программа сама сохраняет их сюда
    "resonators": [],       # см. RESONATORS
}

# резонаторы в новом файле настроек - по типу (префиксы rf3/rf4 и имена PV - пока догадка, поправить в файле)
RESONATORS = {
    "sim": [{"name": f"Резонатор {k}", "type": "sim"} for k in (2, 3, 4)],
    "tango": [{"name": f"Резонатор {k}", "type": "tango", "prefix": f"rf{k}/1e{k}"} for k in (2, 3, 4)],
    "epics": [{"name": f"Резонатор {k}", "type": "epics", "prefix": f"RF{k}"} for k in (2, 3, 4)],
}


def load(path=None, kind="sim"):
    """Возвращает (config, сообщение). path - другой файл настроек (необязательно);
    kind - какие резонаторы записать, если файла ещё нет: "sim", "tango" или "epics"."""
    global PATH
    if path:
        PATH = os.path.abspath(path)
    if os.path.exists(PATH):
        with open(PATH, encoding="utf-8") as f:
            config = {**DEFAULTS, **json.load(f)}      # новые параметры подтянутся из DEFAULTS
        message = f"Настройки прочитаны из {PATH}"
    else:
        config = json.loads(json.dumps({**DEFAULTS, "resonators": RESONATORS[kind]}))   # копия
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        message = f"Файл {PATH} не найден - создан с настройками по умолчанию"
    config["data_dir"] = os.path.join(os.path.dirname(PATH), config["data_dir"])   # data - рядом с настройками
    return config, message


def save(config):
    data = dict(config)
    try:
        data["data_dir"] = os.path.relpath(config["data_dir"], os.path.dirname(PATH))   # хранить коротко
    except ValueError:      # Windows: папка данных на другом диске (D:\ а config на C:\) - храним полный путь
        pass
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
