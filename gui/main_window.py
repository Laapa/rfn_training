"""Главное окно: вкладка «Обзор» со всеми резонаторами + вкладка на каждый резонатор."""
from PyQt5 import QtWidgets, QtCore, QtGui

from trainer.core import Trainer, Settings
from gui.panel import ResonatorPanel, STATE_TEXT, vac_color

COLUMNS = ["Резонатор", "Режим", "Состояние", "U, кВ", "Вакуум, Торр", "Start → Stop"]


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, resonators, tick_ms):
        """resonators - список пар (имя, объект резонатора)."""
        super().__init__()
        self.setWindowTitle("Тренировка резонаторов")
        self.now = 0   # время алгоритма, с (1 тик = 1 с)

        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        self.table = QtWidgets.QTableWidget(len(resonators), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.cellDoubleClicked.connect(lambda row, col: self.tabs.setCurrentIndex(row + 1))
        self.tabs.addTab(self.table, "Обзор")

        self.panels = []
        for name, res in resonators:
            panel = ResonatorPanel(name, Trainer(res, Settings()))
            self.panels.append(panel)
            self.tabs.addTab(panel, name)

        self.statusBar().showMessage("Двойной клик по строке в «Обзоре» - открыть резонатор")
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(tick_ms)

    def tick(self):
        self.now += 1
        for row, panel in enumerate(self.panels):
            tr = panel.tr
            tr.tick(self.now)
            panel.update_view(self.now)

            auto = tr.state != "MANUAL"
            cells = [panel.name, "AUTO" if auto else "MANUAL", STATE_TEXT[tr.state],
                     f"{tr.res.read_setpoint():.2f}", f"{tr.vacuum:.1e}",
                     f"{tr.start:g} → {tr.stop:g}"]
            for col, text in enumerate(cells):
                self.table.setItem(row, col, QtWidgets.QTableWidgetItem(text))
            self.table.item(row, 1).setForeground(QtGui.QColor("green" if auto else "gray"))
            self.table.item(row, 4).setForeground(QtGui.QColor(vac_color(tr.vacuum, tr.s)))
