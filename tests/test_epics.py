"""Проверка EpicsResonator на фейковом EPICS-стенде (fake_server/fake_epics.py, IOC на caproto).
Нужны pyepics и caproto. Запуск:  python -m tests.test_epics
(фейк поднимается на отдельном порту 5099 и только на 127.0.0.1 - сеть и настоящие IOC не задевает)"""
import os
import subprocess
import sys
import tempfile
import time

PORT = "5099"
os.environ.update(EPICS_CA_ADDR_LIST="127.0.0.1", EPICS_CA_AUTO_ADDR_LIST="NO",
                  EPICS_CA_SERVER_PORT=PORT, EPICS_CAS_SERVER_PORT=PORT)

from trainer.core import Trainer, Settings, MANUAL          # noqa: E402
from trainer.epics_res import EpicsResonator, pv_names       # noqa: E402

FAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fake_server", "fake_epics.py")


def main():
    assert pv_names("RF2")["Vac"] == "RF2:CAV:Vac"
    assert pv_names("RF2", {"Vac": "X:Y"})["Vac"] == "X:Y"
    print("ok имена PV по шаблону и замены из config")

    ioc = subprocess.Popen([sys.executable, FAKE, "1"], cwd=tempfile.mkdtemp(),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        res = EpicsResonator("RF2")
        for _ in range(40):                  # ждём, пока IOC поднимется
            try:
                res.read_vacuum()
                break
            except IOError:
                time.sleep(0.5)
        time.sleep(1)                        # первый скан физики
        m = res.read_measurements()
        assert m["ready"] and m["rf_on"] and not m["fault"] and m["agc_u"] and not m["agc_i"], m
        assert 0 < res.read_vacuum() < 1e-8
        print("ok чтение PV:", m)

        res.set_current(2.5)
        assert res.read_current() == 2.5
        res.mod_off()
        time.sleep(1)
        assert not res.read_ready()
        res.mod_on()
        time.sleep(1)
        assert res.read_ready()
        res.reset_all()
        print("ok запись уставок и команды ModOn/ModOff/RstAll")

        tr = Trainer(res, Settings(low=0, high=1, step=0.5, response_delay=1), log=print)
        assert tr.enable(0)
        for t in range(10):
            tr.tick(t)
        assert res.read_setpoint() == 1 and tr.finished
        print("ok тренировка 0 -> 1 кВ через EPICS")

        res.set_voltage(0.5)
        assert tr.enable(100)
    finally:
        ioc.kill()
        ioc.wait()
    time.sleep(1)
    tr.tick(101)
    assert tr.state == MANUAL and not res.connected
    print("ok обрыв связи -> MANUAL")

    dead = EpicsResonator("NOPE")            # стенда нет: создать можно, чтение - понятная ошибка
    try:
        dead.read_vacuum()
        raise AssertionError("должна быть ошибка связи")
    except IOError as e:
        print("ok нет стенда:", e)


if __name__ == "__main__":
    main()
