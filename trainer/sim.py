"""Симулятор резонатора, чтобы отлаживать всё без железа.

Модель: выше «натренированного» напряжения иногда случаются пробои
(выброс газа), выброс постепенно откачивается, а сам уровень
натренированности медленно растёт. Каждый read_vacuum() = 1 секунда.

Так же должен выглядеть и настоящий резонатор (Tango):
    read_vacuum(), read_setpoint(), set_voltage(kv), read_current(), set_current(a)
"""
import random


class SimResonator:
    def __init__(self, base=1e-9, conditioned=25.0, seed=None):
        self.setpoint = 0.0              # кВ
        self.current = 0.0               # уставка тока фидера, А
        self.base = base                 # чистый вакуум, Торр
        self.vacuum = base
        self.conditioned = conditioned   # до скольких кВ резонатор уже «чистый»
        self.rnd = random.Random(seed)

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
