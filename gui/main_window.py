"""Главное окно «Обзор»: таблица всех резонаторов.
Галка в первом столбце открывает/закрывает отдельное окно резонатора.
Закрытое окно не останавливает тренировку - она идёт, пока работает программа."""
import time

from PyQt5 import QtWidgets, QtCore, QtGui

from trainer.core import Trainer, Settings, MANUAL
from gui import style
from gui.panel import ResonatorPanel, STATE_TEXT, vac_color
from gui.viewer import FileViewer

def load_settings(saved, u_limit):
    """Настройки резонатора, сохранённые в прошлый раз. Если там ерунда - по умолчанию."""
    known = {k: v for k, v in saved.items() if k in Settings.__dataclass_fields__ and k != "u_limit"}
    try:
        settings = Settings(**known, u_limit=u_limit)
        return Settings(u_limit=u_limit) if settings.check() else settings
    except TypeError:                     # в файле руками написали, например, "abc" вместо числа
        return Settings(u_limit=u_limit)


COLUMNS = ["Резонатор", "Режим", "Состояние", "U, кВ", "Вакуум, Торр", "Start → Stop"]
Qt = QtCore.Qt


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, resonators, config, message=""):
        """resonators - список пар (имя, объект резонатора), config - из training_config.json."""
        super().__init__()
        self.setWindowTitle("Тренировка резонаторов - обзор")
        # Время алгоритма, с - по настоящим часам, а не по числу тиков: если тик задержался
        # (Tango долго отвечал), dt и Timeout всё равно отсчитываются честно.
        # tick_ms меньше 1000 ускоряет время (для симулятора): 200 -> в 5 раз быстрее.
        self.now = 0.0
        self.t0 = time.monotonic()
        self.speed = 1000 / config["tick_ms"]
        self.config = config

        self.table = QtWidgets.QTableWidget(len(resonators), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        central = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(central)
        lay.addWidget(self.table)
        view_btn = QtWidgets.QPushButton("Просмотр записей…")
        view_btn.clicked.connect(self.on_view)
        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(view_btn)
        bottom.addStretch()
        lay.addLayout(bottom)
        self.setCentralWidget(central)

        self.panels = []
        for row, (name, res) in enumerate(resonators):
            item = config["resonators"][row]
            settings = load_settings(item.get("settings", {}), config["u_max_kv"])
            self.panels.append(ResonatorPanel(name, Trainer(res, settings), config, item))
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

    def on_view(self):
        self.viewer = FileViewer(self.config["data_dir"])
        self.viewer.show()
        self.viewer.choose()

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
        self.now = (time.monotonic() - self.t0) * self.speed
        self.table.blockSignals(True)   # чтобы обновление галок не вызывало on_check
        for row, panel in enumerate(self.panels):
            tr = panel.tr
            tr.tick(self.now)
            try:
                panel.update_view(self.now)
            except Exception as e:      # ошибка в одном окне не должна ронять всю программу
                panel.add_log(f"Ошибка обновления: {e}")

            auto = tr.state != MANUAL
            texts = [panel.name, "AUTO" if auto else "MANUAL", STATE_TEXT[tr.state],
                     panel.u_text, f"{tr.vacuum:.1e}",
                     f"{tr.start:g} → {tr.stop:g}"]
            for col, text in enumerate(texts):
                self.table.item(row, col).setText(text)
            self.table.item(row, 0).setCheckState(Qt.Checked if panel.isVisible() else Qt.Unchecked)
            self.table.item(row, 1).setForeground(QtGui.QColor(style.color("green" if auto else "gray")))
            color = vac_color(tr.vacuum, tr.s)
            self.table.item(row, 4).setForeground(QtGui.QColor(style.color(color)) if color
                                                  else self.palette().text())
        self.table.blockSignals(False)

    def closeEvent(self, event):
        """Закрытие обзора = выход из программы (со всеми окнами резонаторов)."""
        if any(p.tr.state != MANUAL for p in self.panels):
            answer = QtWidgets.QMessageBox.question(
                self, "Выход", "Идёт тренировка (AUTO). Всё равно выйти?")
            if answer != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return
        for p in self.panels:                 # Reverse мог поменять Sequence - сохраним всё
            p.save_settings()
        QtWidgets.QApplication.quit()
