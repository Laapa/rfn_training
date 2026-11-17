"""Фейковый стенд для проверки программы без железа.

Поднимает СВОЮ маленькую базу Tango (SQLite, файл в fake_server/db_data) и в ней устройства
<prefix>/mod, <prefix>/cav, <prefix>/sspa с ТЕМИ ЖЕ именами атрибутов и команд, что на стенде,
и простой «физикой» внутри. Программа и Taurus видят их по обычным именам через TANGO_HOST,
как на настоящем стенде. Вашу настоящую базу Tango не трогает.

Нужен PyTango 10 (в 9.5.1 встроенная база сломана) - отдельное окружение, см. start_fake.bat.

Запуск (в отдельном окне, держать открытым):
    python fake_server/fake_rf.py              3 резонатора, база на порту 10123
    python fake_server/fake_rf.py 2 10200      2 резонатора, база на порту 10200
Потом программа:
    python main.py fake_config.json            (fake_config.json создаёт/обновляет этот скрипт)

Что умеет «стенд»:
  - U резонатора плавно (2 кВ/с) выходит на уставку UcavSetpoint; ВЧ выключен - U = 0
  - выше «натренированного» напряжения случаются пробои: вакуум скачет и откачивается,
    резонатор понемногу тренируется (порог растёт)
  - вакуум хуже TRIP_TORR -> блокировка: ВЧ выключается, ModSt = False.
    Снять: команда RstAll (кнопка «Сброс»), потом ModOn («Вкл МОД») - когда вакуум откачается
    (пока он хуже TRIP_TORR, блокировка сработает снова, как на настоящем стенде)
  - cav/Spike() - устроить пробой вручную (для проверки)
"""
import json
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

try:
    import tango                                                  # noqa: E402
except ImportError:
    sys.exit("Нет PyTango. Фейковый стенд запускается через fake_server\\start_fake.bat (окружение .venv_fake)")
if int(tango.__version__.split(".")[0]) < 10:
    sys.exit(f"Здесь PyTango {tango.__version__}, а фейку нужен PyTango 10 (в 9.x сломана встроенная база).\n"
             "Запускай fake_server\\start_fake.bat - он сам сделает окружение .venv_fake")
from tango import AttrWriteType                                   # noqa: E402
from tango.server import Device, attribute, command, run          # noqa: E402

from trainer.sim import SimResonator                              # noqa: E402

TRIP_TORR = 1e-7      # вакуум хуже этого - срабатывает блокировка
SLEW_KV_S = 2.0       # скорость выхода U на уставку, кВ/с
PLANTS = {}           # prefix -> Plant (один «резонатор» стенда)


class Plant:
    def __init__(self, k):
        self.sim = SimResonator(conditioned=8 + 3 * k, spark_rate=0.05)   # вакуум, пробои, тренировка
        self.u_set = 0.0       # UcavSetpoint
        self.i_set = 0.0       # IfidSetpoint
        self.u = 0.0           # реальное U на резонаторе
        self.on = True         # ВЧ включен
        self.tripped = False   # сработала блокировка
        self.t = time.time()
        self.lock = threading.Lock()

    def update(self):
        """Догнать физику до текущего момента (шагами по 1 с)."""
        with self.lock:
            steps = int(time.time() - self.t)
            self.t += steps
            for _ in range(min(steps, 120)):
                target = self.u_set if self.on else 0.0
                self.u += max(-SLEW_KV_S, min(SLEW_KV_S, target - self.u))
                self.sim.setpoint = self.u          # пробои зависят от реального U
                if self.sim.read_vacuum() > TRIP_TORR and self.on:
                    self.on, self.tripped = False, True
                    print(f"  блокировка: вакуум {self.sim.vacuum:.1e} Торр, ВЧ выключен")

    def powers(self):
        p_cav = (self.u * 1e3) ** 2 / (2 * self.sim.r_sh) / 1e3   # кВт в стенках
        p_ref = 0.15 * p_cav + (0.05 if self.on else 0.0)
        return p_cav + p_ref, p_ref


def plant(device):
    """Plant по имени устройства: rf2/1e2/mod -> rf2/1e2."""
    prefix = device.get_name().rsplit("/", 1)[0]
    p = PLANTS.setdefault(prefix, Plant(len(PLANTS)))
    p.update()
    return p


class Mod(Device):
    def dev_state(self):
        """Состояние устройства: ON - ВЧ включено, FAULT - сработала блокировка, OFF - выключено."""
        p = plant(self)
        if p.tripped:
            return tango.DevState.FAULT
        return tango.DevState.ON if p.on else tango.DevState.OFF

    ModSt = attribute(dtype=bool, fget=lambda self: plant(self).on and not plant(self).tripped)
    ModU = attribute(dtype=bool, fget=lambda self: True)       # АРУ работает по U
    ModI = attribute(dtype=bool, fget=lambda self: False)
    Ucav = attribute(dtype=float, unit="kV", fget=lambda self: plant(self).u)
    Ifid = attribute(dtype=float, unit="A",
                     fget=lambda self: plant(self).i_set if plant(self).on else 0.0)
    UcavSetpoint = attribute(dtype=float, unit="kV", access=AttrWriteType.READ_WRITE,
                             min_value=0, max_value=30,
                             fget=lambda self: plant(self).u_set,
                             fset=lambda self, v: setattr(plant(self), "u_set", v))
    IfidSetpoint = attribute(dtype=float, unit="A", access=AttrWriteType.READ_WRITE,
                             min_value=0, max_value=10,
                             fget=lambda self: plant(self).i_set,
                             fset=lambda self, v: setattr(plant(self), "i_set", v))

    @command
    def ModOn(self):
        p = plant(self)
        if not p.tripped:
            p.on = True

    @command
    def ModOff(self):
        plant(self).on = False

    @command
    def RstAll(self):
        plant(self).tripped = False


class Cav(Device):
    Vac = attribute(dtype=float, unit="Torr", fget=lambda self: plant(self).sim.vacuum)

    @command
    def Spike(self):
        """Пробой вручную: вакуум резко хуже."""
        p = plant(self)
        p.sim.vacuum += 1.5e-7          # хуже TRIP_TORR - сработает блокировка


class Sspa(Device):
    SspaPforw = attribute(dtype=float, unit="kW", fget=lambda self: plant(self).powers()[0])
    SspaPrefl = attribute(dtype=float, unit="kW", fget=lambda self: plant(self).powers()[1])


HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = "FakeRF/fake"                         # имя сервера в базе


def start_database(port):
    """Запустить свою базу Tango (SQLite) отдельным процессом и дождаться, пока ответит."""
    folder = os.path.join(HERE, "db_data")
    os.makedirs(folder, exist_ok=True)
    log = open(os.path.join(folder, "database.log"), "w")
    proc = subprocess.Popen([sys.executable, "-m", "tango.databaseds.database", "--port", str(port), "2"],
                            cwd=folder, env=dict(os.environ), stdout=log, stderr=subprocess.STDOUT)
    for _ in range(120):
        if proc.poll() is not None:
            sys.exit(f"База Tango не запустилась, подробности: {folder}\\database.log\n"
                     f"(порт {port} занят? другой порт: python fake_server/fake_rf.py 3 10200)")
        try:
            tango.Database()
            return proc
        except tango.DevFailed:
            time.sleep(0.5)
    proc.kill()
    sys.exit("База Tango не отвечает 60 с")


def register(prefixes):
    """Прописать устройства фейка в базе (повторно - не страшно)."""
    db = tango.Database()
    for cls, d in (("Mod", "mod"), ("Cav", "cav"), ("Sspa", "sspa")):
        for p in prefixes:
            info = tango.DbDevInfo()
            info.name, info._class, info.server = f"{p}/{d}", cls, SERVER
            db.add_device(info)


def write_config(config_name, port, prefixes):
    """fake_config.json для программы. Если уже есть - обновляем адреса, настройки окон не трогаем."""
    config = {"tick_ms": 1000, "data_dir": "data_fake"}
    if os.path.exists(config_name):
        with open(config_name, encoding="utf-8") as f:
            config = json.load(f)
    # старые записи по короткому префиксу rf2/1e2 (чтобы сохранить настройки окон)
    old = {"/".join(r["prefix"].split("/")[-2:]): r for r in config.get("resonators", []) if r.get("prefix")}
    config["tango_host"] = f"127.0.0.1:{port}"
    config["resonators"] = []
    for p in prefixes:
        item = old.get(p, {"name": f"Фейк {p}"})
        item.update({"type": "tango", "prefix": p})
        item.pop("nodb", None)
        config["resonators"].append(item)
    with open(config_name, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def main(count=3, port=10123, config_name="fake_config.json"):
    prefixes = [f"rf{k + 2}/1e{k + 2}" for k in range(count)]
    for k, p in enumerate(prefixes):       # rf2 «чистый» до 8 кВ, rf3 - до 11, rf4 - до 14 ...
        PLANTS[p] = Plant(k)

    os.environ["TANGO_HOST"] = f"127.0.0.1:{port}"     # всё дальше - через нашу базу
    database = start_database(port)
    try:
        register(prefixes)
        write_config(config_name, port, prefixes)

        def ready():
            print(f"Фейковый стенд работает: база Tango 127.0.0.1:{port}, устройства " + ", ".join(prefixes))
            print(f"Запусти программу:  python main.py {config_name}")
            print(f"Jive/Taurus тоже увидят его с TANGO_HOST=127.0.0.1:{port}")
            print("Остановить стенд: Ctrl+C (так же можно проверить обрыв связи)")

        run((Mod, Cav, Sspa), args=["FakeRF", "fake"], post_init_callback=ready)
    finally:
        database.terminate()                           # базу - вместе со стендом


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:3]))
