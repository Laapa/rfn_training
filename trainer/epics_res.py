"""Резонатор через EPICS (Channel Access, библиотека pyepics). Снаружи - как TangoResonator и SimResonator.

В EPICS нет «устройств с атрибутами и командами», есть только PV (process variable) - переменные с именами.
Поэтому:
  - атрибут Tango  mod/Ucav        -> PV  <prefix>:MOD:Ucav
  - команда Tango  mod/ModOn()     -> запись 1 в PV  <prefix>:MOD:ModOn
  - State Tango (лампы Вкл/Авария) -> PV <prefix>:MOD:RfOn и <prefix>:MOD:Fault (0/1)

Настоящих имён PV стенда мы пока не знаем - поэтому имена по шаблону, а любое можно заменить в config:
    {"type": "epics", "prefix": "RF2", "pv": {"Ucav": "RF2:CAV:Voltage", "Fault": null}}
null - такой PV на стенде нет: RfOn берётся из «Готовности» (ModSt), Fault считается 0.

Где искать IOC - "epics_ca_addr_list" в config (EPICS_CA_ADDR_LIST), см. main.py.
"""
import threading

import epics
import epics.ca

# У каждого резонатора свой поток-работник (trainer/worker.py). Библиотека CA падает (программа молча
# закрывается), если несколько потоков одновременно впервые подключаются к EPICS. Поэтому:
#   - EPICS инициализируем один раз, в главном потоке, при создании первого резонатора;
#   - новые подключения к PV создаём по очереди (CREATE_LOCK). Чтение/запись уже подключённых - параллельно.
CREATE_LOCK = threading.Lock()

# какой PV в каком «устройстве» (средняя часть имени по шаблону)
DEVICE = {
    "ModSt": "MOD", "ModU": "MOD", "ModI": "MOD", "Ucav": "MOD", "Ifid": "MOD",
    "UcavSetpoint": "MOD", "IfidSetpoint": "MOD", "ModOn": "MOD", "ModOff": "MOD", "RstAll": "MOD",
    "RfOn": "MOD", "Fault": "MOD",
    "Vac": "CAV",
    "SspaPforw": "SSPA", "SspaPrefl": "SSPA",
}


def pv_names(prefix, overrides=None):
    """Полные имена PV: по шаблону <prefix>:<устройство>:<имя> + замены из config."""
    names = {key: f"{prefix}:{dev}:{key}" for key, dev in DEVICE.items()}
    names.update(overrides or {})
    return names


class EpicsResonator:
    def __init__(self, prefix="", vac_coeff=1500.0, vac_is_current=False, timeout_s=1.0, pv=None):
        self.names = pv_names(prefix, pv)
        self.vac_coeff = vac_coeff
        self.vac_is_current = vac_is_current    # True, если Vac отдаёт ток насоса (А), а не Торр
        self.timeout = timeout_s
        self.pvs = {}                           # подключаемся при первом обращении (как в TangoResonator)
        self.connected = True
        if epics.ca.libca is None:              # один раз на программу (повторный вызов пересоздал бы контекст)
            epics.ca.initialize_libca()         # в главном потоке, до запуска работников

    def _pv(self, key):
        if key not in self.pvs:
            with CREATE_LOCK:                   # по очереди, см. CREATE_LOCK
                epics.ca.use_initial_context()  # этот поток - в общий контекст EPICS главного потока
                # auto_monitor=False: читаем свежее значение каждый раз (как в Tango), без подписки
                self.pvs[key] = epics.PV(self.names[key], auto_monitor=False, connection_timeout=self.timeout)
        return self.pvs[key]

    def _get(self, key):
        """Прочитать PV. pyepics при обрыве не бросает ошибку, а молча отдаёт None - превращаем в IOError,
        иначе алгоритм получил бы None вместо вакуума."""
        value = self._pv(key).get(timeout=self.timeout, use_monitor=False)
        if value is None:
            self.connected = False
            raise IOError(f"нет ответа от PV {self.names[key]}")
        self.connected = True
        return value

    def _put(self, key, value):
        """Записать в PV и дождаться подтверждения от IOC."""
        pv = self._pv(key)
        if not pv.wait_for_connection(timeout=self.timeout) or pv.put(value, wait=True, timeout=self.timeout) is None:
            self.connected = False
            raise IOError(f"не записалось в PV {self.names[key]}")
        self.connected = True

    def _has(self, key):
        return self.names.get(key) is not None

    # --- то, чем пользуется алгоритм
    def read_vacuum(self):
        """Вакуум в Торр."""
        v = float(self._get("Vac"))
        return v / self.vac_coeff if self.vac_is_current else v

    def read_ready(self):
        """«Готовность» модулятора (ModSt)."""
        return bool(self._get("ModSt"))

    def read_setpoint(self):
        return float(self._get("UcavSetpoint"))

    def set_voltage(self, kv):
        self._put("UcavSetpoint", float(kv))

    def read_current(self):
        return float(self._get("IfidSetpoint"))

    def set_current(self, a):
        self._put("IfidSetpoint", float(a))

    # --- то, что показывает окно
    def read_measurements(self):
        ready = bool(self._get("ModSt"))
        vac = self.read_vacuum()
        return {
            "rf_on": bool(self._get("RfOn")) if self._has("RfOn") else ready,   # лампа «Вкл»
            "fault": bool(self._get("Fault")) if self._has("Fault") else False,  # для лампы «Авария»
            "u": float(self._get("Ucav")), "i": float(self._get("Ifid")),
            "p_fwd": float(self._get("SspaPforw")), "p_ref": float(self._get("SspaPrefl")),
            "pump_a": vac * self.vac_coeff,       # ток насоса, А
            "ready": ready, "agc_u": bool(self._get("ModU")), "agc_i": bool(self._get("ModI")),
        }

    # --- кнопки: команда = записать 1 в PV
    def reset_all(self):
        self._put("RstAll", 1)

    def mod_on(self):
        self._put("ModOn", 1)

    def mod_off(self):
        self._put("ModOff", 1)
