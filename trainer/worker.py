"""Всё общение с устройством одного резонатора - в отдельном потоке.

Окно никогда не ждёт Tango: если стенд не отвечает (на Windows подключение к остановленному
устройству висит секунды на КАЖДЫЙ вызов), зависает только этот поток, а окно живёт и показывает
«нет связи». Без Qt - чтобы проверялось обычным тестом.

    worker.do(func, *args)  - выполнить действие с устройством/автоматом (кнопки, уставки) - в этом потоке
    worker.snapshot         - последние прочитанные значения (окно берёт их раз в тик)
    worker.busy()           - есть ещё не выполненные действия (пока есть - окно не трогает галку AUTO)
"""
import queue
import threading
import time
from dataclasses import dataclass


@dataclass
class Snapshot:
    stamp: float          # когда прочитано (time.monotonic)
    m: dict = None        # read_measurements(); None - нет связи
    u_set: float = 0.0    # уставка U, кВ
    current: float = 0.0  # уставка I фидера, А
    error: str = ""       # почему нет связи


class Worker(threading.Thread):
    def __init__(self, trainer, tick_ms):
        super().__init__(daemon=True)            # закрыли программу - поток умирает сам
        self.tr = trainer
        self.period = tick_ms / 1000
        # Время алгоритма, с - по настоящим часам, а не по числу тиков: если тик задержался
        # (Tango долго отвечал), dt и Timeout всё равно отсчитываются честно.
        # tick_ms меньше 1000 ускоряет время (для симулятора): 200 -> в 5 раз быстрее.
        self.speed = 1000 / tick_ms
        self.t0 = time.monotonic()
        self.actions = queue.Queue()
        self.snapshot = None

    def now(self):
        return (time.monotonic() - self.t0) * self.speed

    def do(self, func, *args):
        self.actions.put((func, args))

    def busy(self):
        return self.actions.unfinished_tasks > 0

    def run(self):
        next_tick = time.monotonic()
        while True:
            # действия от кнопок - сразу, не дожидаясь тика
            try:
                func, args = self.actions.get(timeout=max(0.0, next_tick - time.monotonic()))
                try:
                    func(*args)
                except Exception as e:
                    self.tr.log(f"Не выполнено: {e}")
                finally:
                    self.actions.task_done()
                continue
            except queue.Empty:
                pass
            next_tick = max(next_tick + self.period, time.monotonic())   # отстали - не догоняем пачкой
            self.tr.tick(self.now())
            self.snapshot = self.read()

    def read(self):
        res = self.tr.res
        try:
            return Snapshot(time.monotonic(), res.read_measurements(), res.read_setpoint(), res.read_current())
        except Exception as e:
            return Snapshot(time.monotonic(), error=str(e))
