"""Элементы интерфейса из старой программы: лампочка, тумблер, поле со стрелками, ползунок."""
from PyQt5 import QtWidgets, QtCore, QtGui

from gui.style import icon

MONO = QtGui.QFont("Consolas", 11)


class Lamp(QtWidgets.QLabel):
    """Лампочка - те же картинки, что в старой программе."""
    def __init__(self, size=24):
        super().__init__()
        self.size = size
        self.set("gray")

    def set(self, color):            # "green", "red", "blue", "gray"
        pix = QtGui.QPixmap(icon(f"{color}-led-on.png"))
        self.setPixmap(pix.scaled(self.size, self.size, QtCore.Qt.KeepAspectRatio,
                                  QtCore.Qt.SmoothTransformation))


class Toggle(QtWidgets.QCheckBox):
    """Большой тумблер AUTO / MANUAL - та же картинка и та же логика, что в старой программе."""
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"""
            QCheckBox::indicator {{ width: 80px; height: 80px; }}
            QCheckBox::indicator:unchecked {{ image: url({icon('switch_on_min.png')}); }}
            QCheckBox::indicator:checked {{ image: url({icon('switch_off_min.png')}); }}
        """.replace("\\", "/"))
        self.setCursor(QtCore.Qt.PointingHandCursor)


def value_box(width=90):
    """Поле только для чтения - так в старой программе показывались измерения."""
    box = QtWidgets.QLineEdit()
    box.setReadOnly(True)
    box.setFixedWidth(width)
    box.setFont(MONO)
    return box


class ArrowField(QtWidgets.QWidget):
    """Поле ввода со стрелками ⇧ ⇩ справа, как в старой программе.
    Enter или стрелка -> on_change(новое значение). Если on_change вернул False - значение откатывается.
    Шаг стрелок берётся из step() (обычно - из ползунка Точно/Грубо)."""
    def __init__(self, value, unit, on_change, step, fmt="{:.2f}", width=80):
        super().__init__()
        self.on_change, self.step, self.fmt = on_change, step, fmt
        self.edit = QtWidgets.QLineEdit()
        self.edit.setFixedWidth(width)
        self.edit.setFont(MONO)
        self.edit.returnPressed.connect(self.from_text)
        up = QtWidgets.QPushButton("⇧")
        down = QtWidgets.QPushButton("⇩")
        for b in (up, down):
            b.setFixedSize(26, 15)
            b.setStyleSheet("padding: 0px; font-size: 9pt;")
        up.clicked.connect(lambda: self.apply(self.value + self.step()))
        down.clicked.connect(lambda: self.apply(self.value - self.step()))
        arrows = QtWidgets.QVBoxLayout()
        arrows.setSpacing(0)
        arrows.addWidget(up)
        arrows.addWidget(down)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
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
        self.slider.setFixedHeight(70)
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
