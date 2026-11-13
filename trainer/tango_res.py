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
    def __init__(self, prefix="", vac_coeff=1500.0, vac_is_current=False, timeout_ms=1000, devices=None):
        """devices - явные адреса {"mod": ..., "cav": ..., "sspa": ...} (для тестов);
        обычно не нужен: адреса строятся из prefix."""
        devices = devices or {d: f"{prefix}/{d}" for d in ("mod", "cav", "sspa")}
        self.vac_coeff = vac_coeff
        self.vac_is_current = vac_is_current    # True, если Vac отдаёт ток насоса (А), а не Торр
        self.mod = tango.DeviceProxy(devices["mod"])
        self.cav = tango.DeviceProxy(devices["cav"])
        self.sspa = tango.DeviceProxy(devices["sspa"])
        for d in (self.mod, self.cav, self.sspa):
            d.set_timeout_millis(timeout_ms)    # зависшее устройство не должно вешать программу надолго
        self.connected = True

    def _call(self, func, *args):
        """Любое обращение к Tango: запоминаем, есть ли связь (для лампочки/сообщений)."""
        try:
            result = func(*args)
            self.connected = True
            return result
        except tango.DevFailed as e:
            self.connected = False
            text = e.args[0].desc.strip().splitlines()[0] if e.args else str(e)   # первая строка
            raise IOError(text) from None

    # --- то, чем пользуется алгоритм
    def read_vacuum(self):
        """Вакуум в Торр."""
        v = self._call(self.cav.read_attribute, "Vac").value
        return v / self.vac_coeff if self.vac_is_current else v

    def read_setpoint(self):
        return self._call(self.mod.read_attribute, "UcavSetpoint").value

    def set_voltage(self, kv):
        self._call(self.mod.write_attribute, "UcavSetpoint", float(kv))

    def read_current(self):
        return self._call(self.mod.read_attribute, "IfidSetpoint").value

    def set_current(self, a):
        self._call(self.mod.write_attribute, "IfidSetpoint", float(a))

    # --- то, что показывает окно
    def read_measurements(self):
        st, au, ai, u, i = (a.value for a in self._call(
            self.mod.read_attributes, ["ModSt", "ModU", "ModI", "Ucav", "Ifid"]))
        p_fwd, p_ref = (a.value for a in self._call(
            self.sspa.read_attributes, ["SspaPforw", "SspaPrefl"]))
        vac = self.read_vacuum()
        return {
            "u": u, "i": i, "p_fwd": p_fwd, "p_ref": p_ref,
            "pump_a": vac * self.vac_coeff,       # ток насоса, А
            "ready": st, "agc_u": au, "agc_i": ai,
        }

    # --- кнопки
    def reset_all(self):
        self._call(self.mod.command_inout, "RstAll")

    def mod_on(self):
        self._call(self.mod.command_inout, "ModOn")

    def mod_off(self):
        self._call(self.mod.command_inout, "ModOff")
