"""Элементы интерфейса из старой программы в современном виде:
лампочка, тумблер, поле со стрелками, ползунок «Точно / Грубо»."""
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


class ArrowField(QtWidgets.QWidget):
    """Поле ввода со стрелками вверх/вниз справа, как в старой программе.
    Enter или стрелка -> on_change(новое значение). Если on_change вернул False - значение откатывается.
    Шаг стрелок берётся из step() (обычно - из ползунка Точно/Грубо)."""
    def __init__(self, value, unit, on_change, step, fmt="{:.2f}", width=80):
        super().__init__()
        self.on_change, self.step, self.fmt = on_change, step, fmt
        self.edit = QtWidgets.QLineEdit()
        self.edit.setFixedWidth(width)
        self.edit.setFont(MONO)
        self.edit.returnPressed.connect(self.from_text)
        up = QtWidgets.QPushButton("▲")
        down = QtWidgets.QPushButton("▼")
        for b in (up, down):
            b.setFixedSize(24, 14)
            b.setStyleSheet("padding: 0px; font-size: 6pt; border-radius: 4px;")
        up.clicked.connect(lambda: self.apply(self.value + self.step()))
        down.clicked.connect(lambda: self.apply(self.value - self.step()))
        arrows = QtWidgets.QVBoxLayout()
        arrows.setSpacing(1)
        arrows.addWidget(up)
        arrows.addWidget(down)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        lay.addWidget(self.edit)
        lay.addLayout(arrows)
        lay.addWidget(QtWidgets.QLabel(unit))
        self.set_value(value)

    def set_value(self, value):      # показать значение, ничего не применяя
        self.value = value
        self.edit.setText(self.fmt.format(value))

    def from_text(self):
        try:
            self.apply(float(self.edit.text().replace(",", ".")))
        except ValueError:
            self.set_value(self.value)

    def apply(self, value):
        value = round(max(value, 0.0), 6)
        if self.on_change(value) is False:
            self.set_value(self.value)   # не приняли - вернуть старое
        else:
            self.set_value(value)


class PrecisionSlider(QtWidgets.QWidget):
    """Ползунок «Точно / Грубо», как в старой программе: 3 положения шага стрелок.
    labels - подписи слева (сверху вниз), steps - шаги для каждого положения."""
    def __init__(self, labels, steps):
        super().__init__()
        self.steps = steps
        self.slider = QtWidgets.QSlider(QtCore.Qt.Vertical)
        self.slider.setRange(0, 2)
        self.slider.setValue(1)
        self.slider.setInvertedAppearance(True)       # верх = точно
        self.slider.setFixedHeight(60)
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setVerticalSpacing(0)
        for r, text in enumerate(labels):
            grid.addWidget(QtWidgets.QLabel(text), r, 0)
        grid.addWidget(self.slider, 0, 1, 3, 1)
        grid.addWidget(QtWidgets.QLabel("Точно"), 0, 2)
        grid.addWidget(QtWidgets.QLabel("Грубо"), 2, 2)

    def step(self, k=0):
        """Шаг для поля k (у ручного управления два поля: U и I со своими шагами)."""
        return self.steps[k][self.slider.value()]
