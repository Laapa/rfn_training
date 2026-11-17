"""Настоящий резонатор через Tango. Снаружи выглядит так же, как SimResonator.

Устройства одного резонатора: <prefix>/mod, <prefix>/cav, <prefix>/sspa  (prefix, например, rf2/1e2)
    mod : ModSt, ModU, ModI (bool) - Готовность, АРУ U, АРУ I
          Ucav, Ifid (ro)          - измеренные U резонатора (кВ) и I фидера (А)
          UcavSetpoint, IfidSetpoint (rw) - уставки
          команды ModOn(), ModOff(), RstAll()
    cav : Vac (ro)                 - вакуум
    sspa: SspaPforw, SspaPrefl (ro) - падающая и отражённая мощность, кВт
"""
import tango


class TangoResonator:
    def __init__(self, prefix="", vac_coeff=1500.0, vac_is_current=False, timeout_ms=1000,
                 devices=None, nodb=False):
        """devices - явные адреса {"mod": ..., "cav": ..., "sspa": ...} (для тестов);
        обычно не нужен: адреса строятся из prefix.
        nodb - устройства без базы Tango (фейковый сервер), prefix вида tango://localhost:45450/rf2/1e2"""
        tail = "#dbase=no" if nodb else ""
        devices = devices or {d: f"{prefix}/{d}{tail}" for d in ("mod", "cav", "sspa")}
        self.devices = devices
        self.vac_coeff = vac_coeff
        self.vac_is_current = vac_is_current    # True, если Vac отдаёт ток насоса (А), а не Торр
        self.timeout_ms = timeout_ms
        self.proxies = {}                       # подключаемся при первом обращении (см. _call)
        self.connected = True

    def _call(self, dev, method, *args):
        """Любое обращение к Tango: _call("mod", "read_attribute", "Ucav").
        Подключение к устройству - здесь же, при первой надобности: если стенд (или база Tango)
        недоступен при запуске, программа всё равно откроется и будет пробовать снова каждый тик.
        Запоминаем, есть ли связь (для лампы «Авария» и сообщений)."""
        try:
            proxy = self.proxies.get(dev)
            if proxy is None:
                proxy = tango.DeviceProxy(self.devices[dev])
                proxy.set_timeout_millis(self.timeout_ms)   # зависшее устройство не вешает программу надолго
                self.proxies[dev] = proxy
            result = getattr(proxy, method)(*args)
            self.connected = True
            return result
        except tango.DevFailed as e:
            self.connected = False
            text = e.args[0].desc.strip().splitlines()[0] if e.args else str(e)   # первая строка
            raise IOError(text) from None

    def model(self, dev, attr=None):
        """Полное имя устройства/атрибута для Taurus: model("mod", "Ucav") -> rf2/1e2/mod/Ucav."""
        name = self.devices[dev]
        return f"{name}/{attr}" if attr else name

    # --- то, чем пользуется алгоритм
    def read_vacuum(self):
        """Вакуум в Торр."""
        v = self._call("cav", "read_attribute", "Vac").value
        return v / self.vac_coeff if self.vac_is_current else v

    def read_ready(self):
        """«Готовность» модулятора (mod/ModSt)."""
        return self._call("mod", "read_attribute", "ModSt").value

    def read_setpoint(self):
        return self._call("mod", "read_attribute", "UcavSetpoint").value

    def set_voltage(self, kv):
        self._call("mod", "write_attribute", "UcavSetpoint", float(kv))

    def read_current(self):
        return self._call("mod", "read_attribute", "IfidSetpoint").value

    def set_current(self, a):
        self._call("mod", "write_attribute", "IfidSetpoint", float(a))

    # --- то, что показывает окно
    def read_measurements(self):
        st, au, ai, u, i = (a.value for a in self._call(
            "mod", "read_attributes", ["ModSt", "ModU", "ModI", "Ucav", "Ifid"]))
        p_fwd, p_ref = (a.value for a in self._call(
            "sspa", "read_attributes", ["SspaPforw", "SspaPrefl"]))
        vac = self.read_vacuum()
        state = self._call("mod", "state")
        return {
            "rf_on": state == tango.DevState.ON,                               # лампа «Вкл»
            "fault": state in (tango.DevState.FAULT, tango.DevState.ALARM),     # для лампы «Авария»
            "u": u, "i": i, "p_fwd": p_fwd, "p_ref": p_ref,
            "pump_a": vac * self.vac_coeff,       # ток насоса, А
            "ready": st, "agc_u": au, "agc_i": ai,
        }

    # --- кнопки
    def reset_all(self):
        self._call("mod", "command_inout", "RstAll")

    def mod_on(self):
        self._call("mod", "command_inout", "ModOn")

    def mod_off(self):
        self._call("mod", "command_inout", "ModOff")
