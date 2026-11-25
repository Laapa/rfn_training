"""«Физика» фейкового стенда - общая для Tango-фейка (fake_rf.py) и EPICS-фейка (fake_epics.py).

Один Plant = один резонатор стенда:
  - U плавно (SLEW_KV_S) выходит на уставку u_set; ВЧ выключен - U = 0
  - выше «натренированного» напряжения - случайные пробои (SimResonator), вакуум откачивается
  - вакуум хуже TRIP_TORR -> блокировка: ВЧ выключен, tripped. Снять: rst_all(), потом mod_on()
"""
import threading
import time

from trainer.sim import SimResonator

TRIP_TORR = 1e-7      # вакуум хуже этого - срабатывает блокировка
SLEW_KV_S = 2.0       # скорость выхода U на уставку, кВ/с


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

    # --- команды (одинаковые у обоих фейков)
    def mod_on(self):
        if not self.tripped:        # пока блокировка не сброшена - не включается
            self.on = True

    def mod_off(self):
        self.on = False

    def rst_all(self):
        self.tripped = False

    def spike(self):
        """Пробой вручную: вакуум резко хуже TRIP_TORR - сработает блокировка."""
        self.sim.vacuum += 1.5e-7

    def ready(self):
        """«Готовность» (ModSt): ВЧ включено и блокировки нет."""
        return self.on and not self.tripped
