"""Проверки алгоритма. Запуск:  python -m tests.test_core
(переписывать не обязательно - это моя страховка, что алгоритм работает по README)"""
from trainer.core import Trainer, Settings, DOWN, ZONE, SAW, MANUAL, DELAY, WAIT_GOOD, BACKOFF

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


def test_after_backoff_still_not_good_steps_back_again():
    res, tr = make(21.5)
    tr.enable(0)
    res.vac = VERY_BAD
    tr.tick(0)                      # 21.5 - 3*0.5 = 20.0
    res.u = 21.8                    # (подвинем вручную, чтобы было куда отступать)
    res.vac = GRAY                  # лучше Very Bad, но не Good
    tr.tick(5)
    assert res.u == 21.8 and tr.state == BACKOFF
    tr.tick(10)                     # Timeout прошёл, а Good нет -> ещё 3 шага назад
    assert res.u == 20.3


def test_after_backoff_good_goes_forward():
    res, tr = make(21.5)
    tr.enable(0)
    res.vac = VERY_BAD
    tr.tick(0)
    res.vac = GOOD
    tr.tick(1)
    assert tr.state == DELAY
    run(tr, 2, 7)
    assert res.u == 20.5            # после Response Delay снова шаг вперёд


def test_saw_jumps_to_low():
    res, tr = make(21, sequence=SAW)
    tr.enable(0)
    seen = []
    for t in range(200):
        tr.tick(t)
        seen.append(res.u)
    after_high = [b for a, b in zip(seen, seen[1:]) if a == 22 and b != 22]
    assert after_high and after_high[0] == 20 and tr.state != MANUAL   # с High - сразу в Low


def test_pause_stops_steps_but_not_backoff():
    res, tr = make(21)
    tr.enable(0)
    tr.set_paused(True)
    run(tr, 0, 50)
    assert res.u == 21              # на паузе вперёд не шагаем
    res.vac = VERY_BAD
    tr.tick(50)
    assert res.u == 20              # а отступать - отступаем
    tr.set_paused(False)
    res.vac = GOOD
    run(tr, 51, 60)
    assert res.u > 20


def test_reverse():
    res, tr = make(21)
    tr.enable(0)
    tr.reverse()
    assert tr.s.sequence == DOWN
    run(tr, 0, 100)
    assert res.u == 20 and tr.finished


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


def test_link_error_goes_manual():
    res, tr = make(21)
    tr.enable(0)

    def broken():
        raise IOError("нет связи")
    res.read_vacuum = broken
    tr.tick(1)
    assert tr.state == MANUAL and res.u == 21     # напряжение не тронули


def test_high_limit():
    res, tr = make(21)
    tr.s.high = 31
    assert tr.s.check() != ""


def test_refuse_past_stop():
    res, tr = make(23)
    assert not tr.enable(0)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
