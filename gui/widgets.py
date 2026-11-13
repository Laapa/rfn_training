"""Маленькие элементы интерфейса: карточка, плитка с числом, лампочка, тумблер."""
from PyQt5 import QtWidgets, QtCore, QtGui

from gui import style


class Card(QtWidgets.QFrame):
    """Карточка с заголовком. Содержимое добавлять в card.body (вертикальная раскладка)."""
    def __init__(self, title="", extra=None):
        super().__init__()
        self.setObjectName("card")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        if title or extra:
            head = QtWidgets.QHBoxLayout()
            label = QtWidgets.QLabel(title)
            label.setObjectName("cardTitle")
            head.addWidget(label)
            head.addStretch()
            if extra:
                head.addWidget(extra)
            lay.addLayout(head)
        self.body = QtWidgets.QVBoxLayout()
        lay.addLayout(self.body)


class Tile(Card):
    """Плитка: подпись сверху, крупное число, единицы."""
    def __init__(self, title, unit):
        super().__init__(title)
        self.layout().setContentsMargins(10, 6, 10, 6)   # плитки компактнее карточек
        row = QtWidgets.QHBoxLayout()
        self.value = QtWidgets.QLabel("—")
        self.value.setObjectName("tileValue")
        self.unit = QtWidgets.QLabel(unit)
        self.unit.setObjectName("muted")
        row.addWidget(self.value)
        row.addWidget(self.unit, alignment=QtCore.Qt.AlignBottom)
        row.addStretch()
        self.body.addLayout(row)

    def set(self, text, color=style.TEXT):
        self.value.setText(text)
        self.value.setStyleSheet(f"color: {color}")


class Lamp(QtWidgets.QWidget):
    """Лампочка с подписью. set(цвет) - зажечь, set(style.GRAY) - погасить."""
    def __init__(self, text):
        super().__init__()
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.dot = QtWidgets.QLabel()
        self.dot.setFixedSize(14, 14)
        label = QtWidgets.QLabel(text)
        label.setObjectName("muted")
        lay.addWidget(self.dot)
        lay.addWidget(label)
        self.set(style.GRAY)

    def set(self, color):
        self.dot.setStyleSheet(f"background: {color}; border-radius: 7px;"
                               f"border: 2px solid {QtGui.QColor(color).lighter(130).name()};")


class Toggle(QtWidgets.QCheckBox):
    """Тумблер вместо галки (как большой переключатель AUTO/MANUAL в старой программе)."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(56, 30)
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def hitButton(self, pos):          # нажимать можно в любом месте тумблера
        return self.contentsRect().contains(pos)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(style.GREEN if self.isChecked() else style.GRAY))
        p.drawRoundedRect(0, 0, 56, 30, 15, 15)
        p.setBrush(QtGui.QColor("white"))
        x = 29 if self.isChecked() else 3
        p.drawEllipse(x, 3, 24, 24)
