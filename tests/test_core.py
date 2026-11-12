"""Проверки алгоритма. Запуск:  python -m tests.test_core
(переписывать не обязательно - это моя страховка, что алгоритм работает по README)"""
from trainer.core import Trainer, Settings, UP, DOWN, ZONE, MANUAL, DELAY, WAIT_GOOD

GOOD, GRAY, BAD, VERY_BAD = 1e-9, 3e-9, 6e-9, 2e-8


class FakeResonator:
    def __init__(self, u):
        self.u = u
        self.vac = GOOD

    def read_vacuum(self):
        return self.vac

    def read_setpoint(self):
        return self.u

    def set_voltage(self, kv):
        self.u = kv


def make(u, **kw):
    s = Settings(low=20, high=22, step=0.5, response_delay=5, timeout=10, **kw)
    res = FakeResonator(u)
    tr = Trainer(res, s, log=lambda m: None)
    return res, tr


def run(tr, t0, t1):
    for t in range(t0, t1):
        tr.tick(t)


def test_up_reaches_stop():
    res, tr = make(20)
    assert tr.enable(0)
    run(tr, 0, 200)
    assert res.u == 22 and tr.state == MANUAL and tr.finished


def test_gray_zone_waits_for_good():
    res, tr = make(20)
    tr.enable(0)
    res.vac = GRAY
    run(tr, 0, 100)
    assert res.u == 20 and tr.state == WAIT_GOOD


def test_bad_resets_delay():
    res, tr = make(20)
    tr.enable(0)
    tr.tick(0)
    assert tr.state == DELAY
    res.vac = BAD
    tr.tick(3)
    assert tr.state == WAIT_GOOD and res.u == 20


def test_very_bad_three_steps_back_then_timeout():
    res, tr = make(21.5)
    tr.enable(0)
    res.vac = VERY_BAD
    tr.tick(0)
    assert res.u == 20.0            # 21.5 - 3*0.5
    res.u = 21.8
    tr.tick(5)
    assert res.u == 21.8            # Timeout ещё не прошёл
    tr.tick(10)
    assert res.u == 20.3


def test_very_bad_not_below_start():
    res, tr = make(20.5)
    tr.enable(0)
    res.vac = VERY_BAD
    run(tr, 0, 100)
    assert res.u == 20


def test_down():
    res, tr = make(22, sequence=DOWN)
    tr.enable(0)
    run(tr, 0, 200)
    assert res.u == 20 and tr.finished


def test_zone_reverses():
    res, tr = make(21, sequence=ZONE)
    tr.enable(0)
    seen = set()
    for t in range(500):
        tr.tick(t)
        seen.add(res.u)
    assert 20 in seen and 22 in seen and tr.state != MANUAL


def test_refuse_past_stop():
    res, tr = make(23)
    assert not tr.enable(0)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
