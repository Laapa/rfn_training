"""Алгоритм автоматической тренировки одного резонатора.

Не зависит ни от Qt, ни от Tango. Работает с любым объектом, у которого есть:
    read_vacuum()   -> вакуум (чем больше число, тем хуже)
    read_setpoint() -> текущая уставка напряжения, кВ
    set_voltage(kv) -> выставить уставку, кВ
tick(now) нужно вызывать примерно раз в секунду (now - время в секундах).
"""
from dataclasses import dataclass

UP, DOWN, ZONE = "Processing UP", "Processing DOWN", "ZONE"

# Состояния автомата
MANUAL = "MANUAL"        # тренировка выключена
WAIT_GOOD = "WAIT_GOOD"  # ждём, пока вакуум станет Good
DELAY = "DELAY"          # вакуум Good, отсчитываем Response Delay
BACKOFF = "BACKOFF"      # был Very Bad: отступили назад, ждём Timeout


@dataclass
class Settings:
    low: float = 20.0             # Low KV
    high: float = 50.0            # High KV
    step: float = 0.5             # Step KV
    sequence: str = UP
    response_delay: float = 10.0  # с
    timeout: float = 30.0         # с
    good: float = 2e-9
    bad: float = 5e-9
    very_bad: float = 1e-8
    back_steps: int = 3


class Trainer:
    def __init__(self, resonator, settings, log=print):
        self.res = resonator
        self.s = settings
        self.log = log
        self.state = MANUAL
        self.direction = +1     # +1 вверх, -1 вниз
        self.t_mark = 0.0       # когда начали отсчёт Response Delay / Timeout
        self.finished = False   # дошли до Stop (повод для фанфар)

    # Start и Stop не вводятся, а вычисляются из Low/High и направления
    @property
    def start(self):
        return self.s.low if self.direction > 0 else self.s.high

    @property
    def stop(self):
        return self.s.high if self.direction > 0 else self.s.low

    def enable(self, now):
        """Поставили галку AUTO. Возвращает False, если начать нельзя."""
        s = self.s
        if not (s.step > 0 and s.low < s.high and s.good < s.bad < s.very_bad):
            self.log("Неверные настройки, тренировка не запущена")
            return False
        u = self.res.read_setpoint()
        self._sync_direction(u)
        if (u - self.stop) * self.direction >= 0:
            self.log(f"Уставка {u:.2f} кВ уже на Stop или за ним, тренировка не запущена")
            return False
        self.finished = False
        self.state = WAIT_GOOD
        self.log(f"AUTO: {s.sequence}, Start {self.start} кВ, Stop {self.stop} кВ")
        return True

    def disable(self):
        """Сняли галку (или программа сама сняла)."""
        self.state = MANUAL
        self.log("MANUAL")

    def tick(self, now):
        if self.state == MANUAL:
            return
        s = self.s
        vac = self.res.read_vacuum()

        # п.3-4: Very Bad в любой момент -> шаги назад, повтор не чаще раза в Timeout
        if vac >= s.very_bad:
            if self.state != BACKOFF or now - self.t_mark >= s.timeout:
                self._step_back()
                self.state = BACKOFF
                self.t_mark = now
            return

        if self.state == BACKOFF:   # п.4: вакуум улучшился -> обратно к п.1
            self.state = WAIT_GOOD

        if self.state == WAIT_GOOD:  # п.1: ждём именно Good
            if vac <= s.good:
                self.state = DELAY
                self.t_mark = now
            return

        # DELAY, п.2: отсчитываем Response Delay; если стало Bad - отсчёт сначала
        if vac >= s.bad:
            self.state = WAIT_GOOD
        elif now - self.t_mark >= s.response_delay:
            self._step_forward()

    # ---------------------------------------------------------------------

    def _sync_direction(self, u):
        if self.s.sequence == UP:
            self.direction = +1
        elif self.s.sequence == DOWN:
            self.direction = -1
        elif self.state == MANUAL:  # ZONE при запуске: едем туда, где есть куда ехать
            self.direction = +1 if u < self.s.high else -1

    def _step_forward(self):
        u = self.res.read_setpoint()
        self._sync_direction(u)     # Sequence могли поменять на ходу
        if (u - self.stop) * self.direction < 0:   # до Stop ещё не дошли
            new = u + self.direction * self.s.step
            if (new - self.stop) * self.direction > 0:
                new = self.stop     # не перескакиваем Stop
            self.res.set_voltage(new)
            self.log(f"Шаг -> {new:.2f} кВ")
            u = new
        self.state = WAIT_GOOD
        if (u - self.stop) * self.direction >= 0:  # дошли до Stop (или Low/High поменяли на ходу)
            if self.s.sequence == ZONE:
                self.direction = -self.direction   # п.6
                self.log(f"ZONE: разворот, теперь Stop {self.stop} кВ")
            else:
                self.finished = True               # п.5
                self.log("Дошли до Stop")
                self.disable()

    def _step_back(self):
        u = self.res.read_setpoint()
        new = u - self.direction * self.s.step * self.s.back_steps
        # дальше Start не отступаем (а если уже за Start - стоим на месте)
        if self.direction > 0:
            new = max(new, min(self.start, u))
        else:
            new = min(new, max(self.start, u))
        if new != u:
            self.res.set_voltage(new)
            self.log(f"Very Bad: назад -> {new:.2f} кВ")
        else:
            self.log("Very Bad: уже на Start, ждём")
