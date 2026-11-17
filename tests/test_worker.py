"""Проверки потока-работника: окно не ждёт устройство. Запуск:  python -m tests.test_worker"""
import time

from trainer.core import Trainer, Settings, MANUAL
from trainer.sim import SimResonator
from trainer.worker import Worker


class SlowResonator(SimResonator):
    """Как стенд, который перестал отвечать: каждый вызов висит, потом ошибка."""
    hang = False

    def read_measurements(self):
        if self.hang:
            time.sleep(2)
            raise IOError("TRANSIENT_ConnectFailed")
        return super().read_measurements()


def main():
    res = SlowResonator(seed=1)
    res.set_voltage(10)
    tr = Trainer(res, Settings(low=10, high=12), log=lambda m: None)
    w = Worker(tr, 100)
    w.start()
    time.sleep(0.5)
    assert w.snapshot and w.snapshot.m and not w.snapshot.error
    print("ok снимок значений")

    w.do(res.set_current, 3.0)              # действие от кнопки
    time.sleep(0.3)
    assert res.current == 3.0 and not w.busy()
    print("ok действие выполнено в потоке")

    w.do(lambda: tr.enable(w.now()))
    time.sleep(0.3)
    assert tr.state != MANUAL
    print("ok AUTO включается через поток")

    res.hang = True                         # стенд «умер»
    t = time.monotonic()
    w.do(res.mod_off)                       # окно ставит действие в очередь и сразу свободно
    assert time.monotonic() - t < 0.05
    time.sleep(2.5)
    assert w.snapshot.error == "TRANSIENT_ConnectFailed"
    assert time.monotonic() - w.snapshot.stamp < 3
    print("ok стенд не отвечает - окно не ждёт, в снимке ошибка")


if __name__ == "__main__":
    main()
