"""Фейковый стенд для проверки программы без железа.

Поднимает device-серверы <prefix>/mod, <prefix>/cav, <prefix>/sspa с ТЕМИ ЖЕ именами атрибутов
и команд, что на стенде, и простой «физикой» внутри. Работает без базы Tango, настоящие
устройства в вашей базе не трогает.

Запуск (в отдельном окне, держать открытым):
    python fake_server/fake_rf.py              3 резонатора, порт 45450
    python fake_server/fake_rf.py 2 45460      2 резонатора, порт 45460
Потом программа:
    python main.py fake_config.json            (fake_config.json создаёт этот скрипт)

Что умеет «стенд»:
  - U резонатора плавно (2 кВ/с) выходит на уставку UcavSetpoint; ВЧ выключен - U = 0
  - выше «натренированного» напряжения случаются пробои: вакуум скачет и откачивается,
    резонатор понемногу тренируется (порог растёт)
  - вакуум хуже TRIP_TORR -> блокировка: ВЧ выключается, ModSt = False.
    Снять: команда RstAll (кнопка «Сброс»), потом ModOn («Вкл МОД»)
  - cav/Spike() - устроить пробой вручную (для проверки)
"""
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from tango import AttrWriteType                                   # noqa: E402
from tango.server import Device, attribute, command               # noqa: E402
from tango.test_context import MultiDeviceTestContext             # noqa: E402

from trainer.sim import SimResonator                              # noqa: E402

TRIP_TORR = 3e-8      # вакуум хуже этого - срабатывает блокировка
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
        p.sim.vacuum += 5e-8          # хуже TRIP_TORR - сработает блокировка


class Sspa(Device):
    SspaPforw = attribute(dtype=float, unit="kW", fget=lambda self: plant(self).powers()[0])
    SspaPrefl = attribute(dtype=float, unit="kW", fget=lambda self: plant(self).powers()[1])


def main(count=3, port=45450, config_name="fake_config.json"):
    prefixes = [f"rf{k + 2}/1e{k + 2}" for k in range(count)]
    for k, p in enumerate(prefixes):       # rf2 «чистый» до 8 кВ, rf3 - до 11, rf4 - до 14 ...
        PLANTS[p] = Plant(k)
    devices = [{"class": cls, "devices": [{"name": f"{p}/{d}"} for p in prefixes]}
               for cls, d in ((Mod, "mod"), (Cav, "cav"), (Sspa, "sspa"))]
    try:
        context = MultiDeviceTestContext(devices, host="127.0.0.1", port=port, process=False)
        context.__enter__()
    except RuntimeError:
        sys.exit(f"Не удалось запустить стенд: порт {port} занят? Закрой другой fake_rf.py "
                 f"или укажи другой порт: python fake_server/fake_rf.py 3 45460")
    try:
        config = {
            "tick_ms": 1000,
            "data_dir": "data_fake",
            "resonators": [{"name": f"Фейк {p}", "type": "tango", "nodb": True,
                            "prefix": f"tango://127.0.0.1:{port}/{p}"} for p in prefixes],
        }
        if not os.path.exists(config_name):        # не затираем, если там уже сохранены настройки
            with open(config_name, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print(f"Создан {config_name}")
        print(f"Фейковый стенд работает на порту {port}: " + ", ".join(prefixes))
        print(f"Запусти программу:  python main.py {config_name}")
        print("Остановить стенд: Ctrl+C (так же можно проверить обрыв связи)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Стенд остановлен")
    finally:
        context.__exit__(None, None, None)


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:3]))
