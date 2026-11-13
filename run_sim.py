"""Прогон тренировки на симуляторе в ускоренном времени, без GUI.

Запуск:  python run_sim.py
"""
from trainer.core import Trainer, Settings, UP
from trainer.sim import SimResonator

res = SimResonator(seed=1)
res.set_voltage(20.0)

settings = Settings(low=20, high=30, step=0.5, sequence=UP,
                    response_delay=5, timeout=20,
                    good=2e-9, bad=5e-9, very_bad=1e-8)

t = 0


def log(msg):
    print(f"{t:6d} с  {res.setpoint:5.1f} кВ  {res.vacuum:8.1e} Торр  {msg}")


trainer = Trainer(res, settings, log)
trainer.enable(t)
for t in range(4 * 3600):     # не больше 4 часов модельного времени
    trainer.tick(t)
    if trainer.state == "MANUAL":
        break

print("Готово, дошли до Stop" if trainer.finished else "Не дошли до Stop")
