"""Проверка TangoResonator на настоящих (тестовых) Tango device-серверах с теми же
именами атрибутов и команд, что на стенде. Нужен только PyTango, база Tango не нужна.
Запуск:  python -m tests.test_tango
(переписывать не обязательно)"""
from tango import AttrWriteType
from tango.server import Device, attribute, command
from tango.test_context import MultiDeviceTestContext

from trainer.core import Trainer, Settings, MANUAL
from trainer.tango_res import TangoResonator


class Mod(Device):
    ModSt = attribute(dtype=bool, fget=lambda self: self.on)
    ModU = attribute(dtype=bool, fget=lambda self: True)
    ModI = attribute(dtype=bool, fget=lambda self: False)
    Ucav = attribute(dtype=float, fget=lambda self: self.u if self.on else 0.0)
    Ifid = attribute(dtype=float, fget=lambda self: self.i)
    UcavSetpoint = attribute(dtype=float, access=AttrWriteType.READ_WRITE,
                             fget=lambda self: self.u, fset=lambda self, v: setattr(self, "u", v))
    IfidSetpoint = attribute(dtype=float, access=AttrWriteType.READ_WRITE,
                             fget=lambda self: self.i, fset=lambda self, v: setattr(self, "i", v))

    def init_device(self):
        super().init_device()
        self.u, self.i, self.on = 10.0, 0.0, True

    @command
    def ModOn(self):
        self.on = True

    @command
    def ModOff(self):
        self.on = False

    @command
    def RstAll(self):
        pass


class Cav(Device):
    Vac = attribute(dtype=float, fget=lambda self: 1e-9)


class Sspa(Device):
    SspaPforw = attribute(dtype=float, fget=lambda self: 0.5)
    SspaPrefl = attribute(dtype=float, fget=lambda self: 0.1)


DEVICES = [{"class": Mod, "devices": [{"name": "rf2/1e2/mod"}]},
           {"class": Cav, "devices": [{"name": "rf2/1e2/cav"}]},
           {"class": Sspa, "devices": [{"name": "rf2/1e2/sspa"}]}]


def main():
    with MultiDeviceTestContext(DEVICES, process=True) as ctx:
        res = TangoResonator(devices={d: ctx.get_device_access(f"rf2/1e2/{d}") for d in ("mod", "cav", "sspa")})
        m = res.read_measurements()
        assert m["ready"] and m["agc_u"] and not m["agc_i"] and m["u"] == 10.0, m
        assert m["p_fwd"] == 0.5 and m["p_ref"] == 0.1
        print("ok чтение атрибутов:", m)

        res.set_current(2.5)
        assert res.read_current() == 2.5
        res.mod_off()
        assert not res.read_measurements()["ready"]
        res.mod_on()
        res.reset_all()
        print("ok запись уставок и команды ModOn/ModOff/RstAll")

        tr = Trainer(res, Settings(low=10, high=12, step=0.5, response_delay=2), log=print)
        assert tr.enable(0)
        for t in range(40):
            tr.tick(t)
        assert res.read_setpoint() == 12 and tr.finished
        print("ok тренировка 10 -> 12 кВ через Tango")

        res.set_voltage(11.0)
        tr.s.high = 20
        assert tr.enable(100)
    # контекст закрыт - device-серверов больше нет
    tr.tick(101)
    assert tr.state == MANUAL and not res.connected
    print("ok обрыв связи -> MANUAL")


if __name__ == "__main__":
    main()
