"""Симулятор резонатора, чтобы отлаживать всё без железа.

Модель: выше «натренированного» напряжения иногда случаются пробои
(выброс газа), выброс постепенно откачивается, а сам уровень
натренированности медленно растёт. Каждый read_vacuum() = 1 секунда.

Так же должен выглядеть и настоящий резонатор (Tango):
    read_vacuum()        -> Торр (по нему работает алгоритм)
    read_setpoint()      -> уставка U, кВ          set_voltage(kv)
    read_current()       -> уставка I фидера, А    set_current(a)
    read_measurements()  -> словарь измерений (см. ниже)
    reset_gen(), reset_bb(), mod_on(), mod_off()   - кнопки
    connected            -> есть ли связь с устройством
"""
import math
import random


class SimResonator:
    def __init__(self, base=1e-9, conditioned=25.0, seed=None, vac_coeff=1500.0, r_sh=3.19e6):
        self.setpoint = 0.0              # кВ
        self.current = 0.0               # уставка тока фидера, А
        self.base = base                 # чистый вакуум, Торр
        self.vacuum = base
        self.conditioned = conditioned   # до скольких кВ резонатор уже «чистый»
        self.rnd = random.Random(seed)
        self.vac_coeff = vac_coeff
        self.r_sh = r_sh
        self.modulator = True
        self.connected = True

    def set_voltage(self, kv):
        self.setpoint = kv

    def read_setpoint(self):
        return self.setpoint

    def set_current(self, a):
        self.current = a

    def read_current(self):
        return self.current

    def read_vacuum(self):
        self.vacuum = self.base + (self.vacuum - self.base) * 0.9   # откачка
        over = self.setpoint - self.conditioned
        if over > 0:
            if self.rnd.random() < 0.02 * over:                     # пробой
                self.vacuum += self.base * self.rnd.uniform(2, 20)
            self.conditioned += 0.002 * over                        # тренируется
        return self.vacuum

    def read_measurements(self):
        """Что показывает блок «Данные» и лампочки."""
        noise = lambda x: x * (1 + self.rnd.gauss(0, 0.01))
        u = noise(self.setpoint) if self.modulator else 0.0
        p_cav = (u * 1e3) ** 2 / (2 * self.r_sh) / 1e3              # кВт в стенках
        p_ref = noise(0.15 * p_cav + 0.05)
        return {
            "u": u,                                   # U резонатора (измеренное), кВ
            "i": noise(self.current),                 # I фидера (измеренный), А
            "p_fwd": p_cav + p_ref,                   # падающая, кВт
            "p_ref": p_ref,                           # отражённая, кВт
            "phase": 30 + self.rnd.gauss(0, 0.5),     # фазометр, градусы
            "pump_a": self.vacuum * self.vac_coeff,   # ток насоса, А
            "ready": self.modulator,                  # лампочка «Готовность»
            "agc_u": True,                            # лампочки АРУ U / I
            "agc_i": False,
        }

    # Кнопки нижней панели
    def reset_gen(self):
        pass

    def reset_bb(self):
        pass

    def mod_on(self):
        self.modulator = True

    def mod_off(self):
        self.modulator = False


def u_from_power(p_fwd, p_ref, r_sh):
    """U резонатора НО, кВ = sqrt(2 * (Pпад - Pотр) * R_sh), мощности в кВт."""
    return math.sqrt(2 * abs(p_fwd - p_ref) * 1e3 * r_sh) / 1e3
