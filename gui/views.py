"""Показ значений и ламп: для настоящего резонатора (Tango) - виджеты Taurus, они сами читают
атрибуты; для встроенного симулятора - обычные поля, их заполняет окно раз в тик.
Писать в устройство Taurus-виджеты не умеют - уставки и команды идут только через нашу логику."""
import sys

from PyQt5 import QtWidgets, QtCore

from gui.style import LAMP
from gui.widgets import Lamp, MONO


try:
    import taurus                         # noqa: F401
    TAURUS = True
except ImportError:                       # не установлен - показываем обычными полями, всё работает так же
    TAURUS = False


def taurus_ok(res):
    if not TAURUS or not hasattr(res, "model"):   # у TangoResonator есть имена атрибутов, у симулятора нет
        return False
    if getattr(sys, "frozen", False):     # в exe Taurus не видит свои папки - говорим ему явно
        from taurus import tauruscustomsettings
        tauruscustomsettings.EXTRA_SCHEME_MODULES = ["taurus.core.tango"]
    return True


class ValueView(QtWidgets.QWidget):
    """Значение атрибута. Tango -> TaurusLabel, симулятор -> поле, которое заполняет set()."""
    def __init__(self, res, dev, attr, fmt="{:.2f}"):
        super().__init__()
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.taurus = taurus_ok(res)
        if self.taurus:
            from taurus.qt.qtgui.display import TaurusLabel
            self.box = TaurusLabel()
            self.box.setModel(res.model(dev, attr))
            self.box.setFormat("{0.magnitude:" + fmt[2:])   # только число: единицы подписаны рядом
            self.box.setBgRole(None)
        else:
            self.box = QtWidgets.QLineEdit()
            self.box.setReadOnly(True)
        self.box.setFont(MONO)
        self.box.setFixedWidth(115)
        self.box.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.color("")
        lay.addWidget(self.box)

    def set(self, text):
        if not self.taurus:                 # Taurus обновляет себя сам
            self.box.setText(text)

    def color(self, color):
        css = f"color: {color}; font-weight: bold;" if color else ""
        if getattr(self, "_css", None) != css:          # не дёргать стиль каждую секунду без нужды
            self._css = css
            self.box.setStyleSheet(css)


class LedView(QtWidgets.QWidget):
    """Лампа атрибута. Tango -> TaurusLed (для State - цвет по состоянию), симулятор -> наша лампа."""
    def __init__(self, res, dev, attr):
        super().__init__()
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.taurus = taurus_ok(res)
        if self.taurus:
            from taurus.qt.qtgui.display import TaurusLed
            self.led = TaurusLed()
            self.led.setModel(res.model(dev, attr))
            self.led.setFixedSize(20, 20)
        else:
            self.led = Lamp()
        lay.addWidget(self.led)

    def set(self, color):
        if not self.taurus and color in LAMP:
            self.led.set(color)


def command_button(res, text, command, func, log):
    """Кнопка команды. Tango -> TaurusCommandButton, симулятор -> обычная кнопка. Всё пишется в журнал."""
    if taurus_ok(res):
        from taurus.qt.qtgui.button import TaurusCommandButton
        b = TaurusCommandButton(command=command, text=text)
        b.setModel(res.model("mod"))
        b.commandExecuted.connect(lambda _: log(f"Команда: {text} ({command})"))
        return b
    b = QtWidgets.QPushButton(text)

    def run():
        try:
            func()
            log(f"Команда: {text}")
        except Exception as e:
            log(f"Команда {text} не прошла: {e}")
    b.clicked.connect(run)
    return b
