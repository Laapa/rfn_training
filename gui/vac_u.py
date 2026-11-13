"""Отдельное окно «Вакуум от напряжения» (открывается кнопкой из окна резонатора)."""
import math

import pyqtgraph as pg
from PyQt5 import QtWidgets


class VacAxis(pg.AxisItem):
    """Ось вакуума в лог-шкале: деления 1-2-5 в каждой декаде, подписи вида 2e-09.
    Стандартная лог-ось pyqtgraph на узком диапазоне лепит подписи друг на друга."""
    def logTickValues(self, minVal, maxVal, size, stdTicks):
        levels = [[], [], []]   # главные: 1 / средние: 2, 5 / мелкие: остальные
        for d in range(math.floor(minVal), math.ceil(maxVal) + 1):
            for m in range(1, 10):
                v = d + math.log10(m)          # в лог-режиме ось хранит log10 значения
                if minVal <= v <= maxVal:
                    levels[0 if m == 1 else 1 if m in (2, 5) else 2].append(v)
        return [(1.0, levels[0]), (0.3, levels[1]), (0.1, levels[2])]

    def tickStrings(self, values, scale, spacing):
        return [f"{10 ** v:.0e}" for v in values]


class VacUWindow(QtWidgets.QWidget):
    def __init__(self, name):
        super().__init__()
        self.setWindowTitle(f"{name} - вакуум от напряжения")
        self.resize(700, 450)
        self.u, self.vac = [], []
        self.plot = pg.PlotWidget(axisItems={"left": VacAxis("left")})
        self.plot.setTitle("Vacuum (torr) vs Voltage (kV)", color="y", size="12pt")
        self.plot.setLogMode(y=True)
        self.plot.showGrid(x=True, y=True)
        self.curve = self.plot.plot(pen=None, symbol="o", symbolSize=3,
                                    symbolPen=None, symbolBrush="y")
        clear = QtWidgets.QPushButton("Очистить график")
        clear.clicked.connect(self.clear)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(self.plot)
        lay.addWidget(clear)

    def add(self, u, vac, limit):
        """Точки копятся всегда, даже когда окно закрыто; рисуем - только если открыто."""
        self.u = (self.u + [u])[-limit:]
        self.vac = (self.vac + [vac])[-limit:]
        if self.isVisible():
            self.curve.setData(self.u, self.vac)

    def clear(self):
        self.u, self.vac = [], []
        self.curve.setData([], [])
