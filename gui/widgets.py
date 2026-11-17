"""Элементы интерфейса из старой программы в современном виде:
лампочка, тумблер, поле со стрелками, ползунок «Точно / Грубо»."""
import math

from PyQt5 import QtWidgets, QtCore, QtGui

from gui.style import LAMP, C

MONO = QtGui.QFont("Consolas", 11)


class Lamp(QtWidgets.QLabel):
    """Лампочка: цветной кружок с мягким ободком. set("green" / "red" / "gray" / "blue")."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(18, 18)
        self.set("gray")

    def set(self, name):
        c = QtGui.QColor(LAMP[name])
        ring = QtGui.QColor(c)
        ring.setAlpha(90)
        self.setStyleSheet(f"background: {c.name()}; border-radius: 9px;"
                           f"border: 3px solid rgba({ring.red()},{ring.green()},{ring.blue()},90);")


class Toggle(QtWidgets.QCheckBox):
    """Тумблер AUTO / MANUAL (вместо картинки из старой программы)."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(72, 38)
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def hitButton(self, pos):          # нажимать можно в любом месте тумблера
        return self.contentsRect().contains(pos)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(C["green"] if self.isChecked() else C["gray"]))
        p.drawRoundedRect(0, 0, 72, 38, 19, 19)
        p.setBrush(QtGui.QColor("white"))
        p.drawEllipse(38 if self.isChecked() else 4, 4, 30, 30)


def value_box(width=80):
    """Поле только для чтения - так в старой программе показывались измерения."""
    box = QtWidgets.QLineEdit()
    box.setReadOnly(True)
    box.setFixedWidth(width)
    box.setFont(MONO)
    return box


class StepField(QtWidgets.QWidget):
    """Поле [−] значение [+] (как TaurusValueSpinBox на эскизе).
    Enter или −/+ -> on_change(новое значение); если on_change вернул False - значение откатывается.
    log_step=True - шаг «по второй значащей цифре» (для вакуума: 2.0e-09 -> 2.1e-09)."""
    def __init__(self, value, unit, on_change, step=1.0, fmt="{:g}", log_step=False, width=80):
        super().__init__()
        self.on_change, self.step, self.fmt, self.log_step = on_change, step, fmt, log_step
        self.edit = QtWidgets.QLineEdit()
        self.edit.setFixedWidth(width)
        self.edit.setFont(MONO)
        self.edit.setAlignment(QtCore.Qt.AlignRight)
        self.edit.returnPressed.connect(self.from_text)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        for sign, text in ((-1, "−"), (+1, "+")):
            b = QtWidgets.QPushButton(text)
            b.setFixedSize(26, 24)
            b.setStyleSheet("padding: 0px; font-weight: bold;")
            b.setAutoRepeat(True)                    # зажал - листает
            b.clicked.connect(lambda _, k=sign: self.nudge(k))
            lay.addWidget(b)
            if sign < 0:
                lay.addWidget(self.edit)
        if unit:
            lay.addWidget(QtWidgets.QLabel(unit))
        self.set_value(value)

    def set_value(self, value):      # показать значение, ничего не применяя
        self.value = value
        self.edit.setText(self.fmt.format(value))

    def nudge(self, sign):
        if self.log_step:
            step = 10 ** (math.floor(math.log10(self.value)) - 1) if self.value > 0 else 1e-10
        else:
            step = self.step
        self.apply(self.value + sign * step)

    def from_text(self):
        try:
            self.apply(float(self.edit.text().replace(",", ".")))
        except ValueError:
            self.set_value(self.value)

    def apply(self, value):
        value = float(f"{max(value, 0.0):.6g}")      # без хвостов вида 0.30000000000000004
        if self.on_change(value) is False:
            self.set_value(self.value)               # не приняли - вернуть старое
        else:
            self.set_value(value)


def method_icon(kind, w=44, h=20):
    """Картинка метода тренировки (как на эскизе): вверх, вниз, туда-обратно, пила."""
    shapes = {"up": [(0, 1), (1, 0)], "down": [(0, 0), (1, 1)],
              "zone": [(0, 1), (0.5, 0), (1, 1)],
              "saw": [(0, 1), (0.45, 0), (0.45, 1), (0.9, 0), (0.9, 1)]}
    pix = QtGui.QPixmap(w, h)
    pix.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pix)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setPen(QtGui.QPen(QtGui.QColor(C["accent"]), 2))
    pts = [QtCore.QPointF(2 + x * (w - 4), 2 + y * (h - 4)) for x, y in shapes[kind]]
    p.drawPolyline(QtGui.QPolygonF(pts))
    p.end()
    return QtGui.QIcon(pix)
