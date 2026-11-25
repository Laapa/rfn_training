"""Фейковый EPICS-стенд: IOC на caproto (чистый Python, ставится одной командой, работает на Windows).

Те же резонаторы и та же «физика», что у Tango-фейка (fake_server/plant.py), только по EPICS:
PV <prefix>:MOD:Ucav, <prefix>:CAV:Vac, ... (имена - как в trainer/epics_res.py по шаблону).
Команда = записать 1: <prefix>:MOD:ModOn, ModOff, RstAll; <prefix>:CAV:Spike - пробой вручную.

Запуск (в отдельном окне, держать открытым):
    python fake_server/fake_epics.py           3 резонатора RF2, RF3, RF4
    python fake_server/fake_epics.py 1         1 резонатор
Потом программа:
    python main.py fake_epics_config.json      (этот файл создаёт/обновляет скрипт)
IOC слушает только 127.0.0.1 - настоящие IOC в сети не задевает и сам в сеть не виден.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("EPICS_CAS_INTF_ADDR_LIST", "127.0.0.1")    # только этот компьютер

from caproto.server import PVGroup, pvproperty, run              # noqa: E402

from fake_server.plant import Plant                               # noqa: E402

CONFIG = "fake_epics_config.json"


class FakeResonator(PVGroup):
    """PV одного резонатора. Имена - без prefix (его добавляет caproto: RF2: + MOD:Ucav)."""
    ModSt = pvproperty(value=0, name="MOD:ModSt", read_only=True)       # «Готовность»
    ModU = pvproperty(value=1, name="MOD:ModU", read_only=True)         # АРУ по U работает
    ModI = pvproperty(value=0, name="MOD:ModI", read_only=True)
    RfOn = pvproperty(value=0, name="MOD:RfOn", read_only=True)         # лампа «Вкл»
    Fault = pvproperty(value=0, name="MOD:Fault", read_only=True)       # блокировка -> «Авария»
    Ucav = pvproperty(value=0.0, name="MOD:Ucav", read_only=True, units="kV")
    Ifid = pvproperty(value=0.0, name="MOD:Ifid", read_only=True, units="A")
    UcavSetpoint = pvproperty(value=0.0, name="MOD:UcavSetpoint", units="kV",
                              lower_ctrl_limit=0.0, upper_ctrl_limit=30.0)
    IfidSetpoint = pvproperty(value=0.0, name="MOD:IfidSetpoint", units="A",
                              lower_ctrl_limit=0.0, upper_ctrl_limit=10.0)
    ModOn = pvproperty(value=0, name="MOD:ModOn")
    ModOff = pvproperty(value=0, name="MOD:ModOff")
    RstAll = pvproperty(value=0, name="MOD:RstAll")
    Vac = pvproperty(value=1e-9, name="CAV:Vac", read_only=True, units="Torr", precision=2)
    Spike = pvproperty(value=0, name="CAV:Spike")
    SspaPforw = pvproperty(value=0.0, name="SSPA:SspaPforw", read_only=True, units="kW")
    SspaPrefl = pvproperty(value=0.0, name="SSPA:SspaPrefl", read_only=True, units="kW")

    def __init__(self, k, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plant = Plant(k)

    # раз в полсекунды: догнать физику и выставить все показания
    @ModSt.scan(period=0.5)
    async def ModSt(self, instance, async_lib):
        p = self.plant
        p.update()
        p_fwd, p_ref = p.powers()
        await instance.write(int(p.ready()))
        await self.RfOn.write(int(p.on))
        await self.Fault.write(int(p.tripped))
        await self.Ucav.write(p.u)
        await self.Ifid.write(p.i_set if p.on else 0.0)
        await self.Vac.write(p.sim.vacuum)
        await self.SspaPforw.write(p_fwd)
        await self.SspaPrefl.write(p_ref)

    # уставки - прямо в «физику»
    @UcavSetpoint.putter
    async def UcavSetpoint(self, instance, value):
        self.plant.u_set = min(max(value, 0.0), 30.0)
        return self.plant.u_set

    @IfidSetpoint.putter
    async def IfidSetpoint(self, instance, value):
        self.plant.i_set = min(max(value, 0.0), 10.0)
        return self.plant.i_set

    # команды: записали 1 - выполнили, PV снова 0
    @ModOn.putter
    async def ModOn(self, instance, value):
        if value:
            self.plant.mod_on()
        return 0

    @ModOff.putter
    async def ModOff(self, instance, value):
        if value:
            self.plant.mod_off()
        return 0

    @RstAll.putter
    async def RstAll(self, instance, value):
        if value:
            self.plant.rst_all()
        return 0

    @Spike.putter
    async def Spike(self, instance, value):
        if value:
            self.plant.spike()
        return 0


def write_config(prefixes):
    """fake_epics_config.json для программы. Если уже есть - обновляем адреса, настройки окон не трогаем."""
    config = {"tick_ms": 1000, "data_dir": "data_fake_epics"}
    if os.path.exists(CONFIG):
        with open(CONFIG, encoding="utf-8") as f:
            config = json.load(f)
    old = {r.get("prefix"): r for r in config.get("resonators", [])}
    config["epics_ca_addr_list"] = "127.0.0.1"
    config["resonators"] = []
    for p in prefixes:
        item = old.get(p, {"name": f"EPICS-фейк {p}"})
        item.update({"type": "epics", "prefix": p})
        config["resonators"].append(item)
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def main(count=3):
    prefixes = [f"RF{k + 2}" for k in range(count)]
    pvdb = {}
    for k, p in enumerate(prefixes):          # RF2 «чистый» до 8 кВ, RF3 - до 11, RF4 - до 14 ...
        pvdb.update(FakeResonator(k, prefix=p + ":").pvdb)
    write_config(prefixes)
    print(f"Фейковый EPICS-стенд: {len(pvdb)} PV, резонаторы " + ", ".join(prefixes) + " (только 127.0.0.1)")
    print(f"Запусти программу:  python main.py {CONFIG}")
    print("Пробой вручную:     python fake_server/spike_epics.py RF2")
    print("Остановить: Ctrl+C")
    run(pvdb, interfaces=["127.0.0.1"])


if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:2]))
