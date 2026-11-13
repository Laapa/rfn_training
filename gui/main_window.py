"""Главное окно «Обзор»: таблица всех резонаторов.
Галка в первом столбце открывает/закрывает отдельное окно резонатора.
Закрытое окно не останавливает тренировку - она идёт, пока работает программа."""
from PyQt5 import QtWidgets, QtCore, QtGui

from trainer.core import Trainer, Settings, MANUAL
from gui import style
from gui.panel import ResonatorPanel, STATE_TEXT, vac_color

COLUMNS = ["Резонатор", "Режим", "Состояние", "U, кВ", "Вакуум, Торр", "Start → Stop"]
Qt = QtCore.Qt


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, resonators, config, message=""):
        """resonators - список пар (имя, объект резонатора), config - из training_config.json."""
        super().__init__()
        self.setWindowTitle("Тренировка резонаторов - обзор")
        self.now = 0   # время алгоритма, с (1 тик = 1 с)

        self.table = QtWidgets.QTableWidget(len(resonators), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setShowGrid(False)
        self.setCentralWidget(self.table)

        self.panels = []
        for row, (name, res) in enumerate(resonators):
            self.panels.append(ResonatorPanel(name, Trainer(res, Settings()), config))
            for col in range(len(COLUMNS)):          # ячейки создаём один раз
                self.table.setItem(row, col, QtWidgets.QTableWidgetItem())
            first = self.table.item(row, 0)
            first.setText(name)
            first.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            first.setCheckState(Qt.Unchecked)
        self.table.itemChanged.connect(self.on_check)

        self.statusBar().showMessage(f"{message}.  Поставь галку у резонатора, чтобы открыть его окно")
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(config["tick_ms"])

    def on_check(self, item):
        if item.column() != 0:
            return
        panel = self.panels[item.row()]
        if item.checkState() == Qt.Checked:
            self.place(panel, item.row())
            panel.show()
            panel.raise_()
        else:
            panel.hide()

    def place(self, panel, index):
        """Чётные резонаторы - в левую половину экрана, нечётные - в правую."""
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        half = screen.width() // 2
        panel.resize(half - 20, screen.height() - 60)
        panel.move(screen.x() + (index % 2) * half, screen.y())

    def tick(self):
        self.now += 1
        self.table.blockSignals(True)   # чтобы обновление галок не вызывало on_check
        for row, panel in enumerate(self.panels):
            tr = panel.tr
            tr.tick(self.now)
            panel.update_view(self.now)

            auto = tr.state != MANUAL
            texts = [panel.name, "AUTO" if auto else "MANUAL", STATE_TEXT[tr.state],
                     f"{tr.res.read_setpoint():.2f}", f"{tr.vacuum:.1e}",
                     f"{tr.start:g} → {tr.stop:g}"]
            for col, text in enumerate(texts):
                self.table.item(row, col).setText(text)
            self.table.item(row, 0).setCheckState(Qt.Checked if panel.isVisible() else Qt.Unchecked)
            self.table.item(row, 1).setForeground(QtGui.QColor(style.GREEN if auto else style.MUTED))
            self.table.item(row, 4).setForeground(QtGui.QColor(vac_color(tr.vacuum, tr.s)))
        self.table.blockSignals(False)

    def closeEvent(self, event):
        """Закрытие обзора = выход из программы (со всеми окнами резонаторов)."""
        if any(p.tr.state != MANUAL for p in self.panels):
            answer = QtWidgets.QMessageBox.question(
                self, "Выход", "Идёт тренировка (AUTO). Всё равно выйти?")
            if answer != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return
        QtWidgets.QApplication.quit()
