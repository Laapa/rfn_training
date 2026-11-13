"""Окно «Просмотр записи»: открыть сохранённый .dat и посмотреть графики (как «Смотрелки» в старой программе).
Три графика по времени, у каждого своя величина; рядом - журнал событий этой сессии (.log)."""
import os
from datetime import datetime

import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui

from gui import style
from gui.vac_u import VacAxis

# колонки .dat после даты и времени (см. trainer/datafile.py); log - рисовать в лог-шкале
COLUMNS = [("u", "U резонатора, кВ", False), ("i", "I фидера, А", False),
           ("pump", "I насоса, А", True), ("vac", "Вакуум, Торр", True),
           ("p_fwd", "Падающая, кВт", False), ("p_ref", "Отражённая, кВт", False),
           ("u_set", "U уставка, кВ", False), ("i_set", "I уставка, А", False)]
DEFAULT = ["u", "vac", "p_ref"]       # что показать на трёх графиках сразу после открытия


def read_dat(path):
    """Прочитать .dat -> (время [с], {колонка: [значения]}, режим [AUTO/MANUAL]). Кривые строки пропускаем."""
    t, data, mode = [], {key: [] for key, _, _ in COLUMNS}, []
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 1 + len(COLUMNS):
                continue
            try:
                stamp = datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S").timestamp()
                values = [float(v) for v in parts[1:1 + len(COLUMNS)]]
            except ValueError:
                continue
            t.append(stamp)
            for (key, _, _), v in zip(COLUMNS, values):
                data[key].append(v)
            mode.append(parts[1 + len(COLUMNS)] if len(parts) > 1 + len(COLUMNS) else "")
    return t, data, mode


class FileViewer(QtWidgets.QWidget):
    def __init__(self, folder):
        super().__init__()
        self.setWindowTitle("Просмотр записи")
        self.resize(1200, 800)
        self.folder = folder
        self.t, self.data = [], {}

        open_btn = QtWidgets.QPushButton("Открыть файл…")
        open_btn.clicked.connect(self.choose)
        self.info = QtWidgets.QLabel("Файл не выбран")
        top = QtWidgets.QHBoxLayout()
        top.addWidget(open_btn)
        top.addWidget(self.info, stretch=1)

        # три графика, у каждого - выбор величины
        self.plots, self.combos, self.curves = [], [], []
        plots_box = QtWidgets.QVBoxLayout()
        for k in range(3):
            combo = QtWidgets.QComboBox()
            for key, text, _ in COLUMNS:
                combo.addItem(text, key)
            combo.setCurrentIndex([c[0] for c in COLUMNS].index(DEFAULT[k]))
            combo.currentIndexChanged.connect(lambda _, n=k: self.draw(n))
            plot = pg.PlotWidget(background=style.PLOT_BG,
                                 axisItems={"bottom": pg.DateAxisItem(), "left": VacAxis("left")})
            plot.showGrid(x=True, y=True, alpha=0.2)
            plot.setClipToView(True)
            plot.setDownsampling(auto=True)
            if self.plots:
                plot.setXLink(self.plots[0])          # зум по времени - на всех графиках сразу
            self.curves.append(plot.plot(pen=pg.mkPen((255, 0, 0))))
            row = QtWidgets.QHBoxLayout()
            row.addWidget(QtWidgets.QLabel(f"График {k + 1}:"))
            row.addWidget(combo)
            row.addStretch()
            plots_box.addLayout(row)
            plots_box.addWidget(plot, stretch=1)
            self.plots.append(plot)
            self.combos.append(combo)

        self.log_view = QtWidgets.QPlainTextEdit()      # журнал событий сессии
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.log_view.setFont(QtGui.QFont("Consolas", 9))
        self.log_view.cursorPositionChanged.connect(self.mark_event)   # щелчок по строке
        self.markers = []                               # вертикальные линии «момент события»
        for plot in self.plots:
            line = pg.InfiniteLine(angle=90, pen=pg.mkPen("c", width=1.5))
            line.hide()
            plot.addItem(line)
            self.markers.append(line)
        log_box = QtWidgets.QGroupBox("Журнал событий (щёлкни по строке)")
        log_box.setMinimumWidth(380)
        style.group(log_box, "cyan")
        QtWidgets.QVBoxLayout(log_box).addWidget(self.log_view)

        left = QtWidgets.QWidget()
        left.setLayout(plots_box)
        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(log_box)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 1)

        main = QtWidgets.QVBoxLayout(self)
        main.addLayout(top)
        main.addWidget(split, stretch=1)

    def choose(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Открыть запись", self.folder, "Записи тренировки (*.dat);;Все файлы (*)")
        if path:
            self.open_file(path)

    def open_file(self, path):
        try:
            self.t, self.data, mode = read_dat(path)
        except OSError as e:
            self.info.setText(f"Не удалось открыть: {e}")
            return
        self.folder = os.path.dirname(path)
        if self.t:
            start = datetime.fromtimestamp(self.t[0]).strftime("%Y-%m-%d %H:%M:%S")
            minutes = (self.t[-1] - self.t[0]) / 60
            self.info.setText(f"{os.path.basename(path)}  ·  {len(self.t)} строк  ·  "
                              f"с {start}, {minutes:.0f} мин  ·  в AUTO {mode.count('AUTO')} с")
        else:
            self.info.setText(f"{os.path.basename(path)}: данных нет")
        log_path = path[:-4] + ".log"
        if os.path.exists(log_path):
            with open(log_path, encoding="utf-8") as f:
                self.log_view.setPlainText(f.read())
        else:
            self.log_view.setPlainText("(журнала для этой записи нет)")
        for n in range(3):
            self.draw(n)
        self.plots[0].autoRange()

    def draw(self, n):
        key = self.combos[n].currentData()
        log = dict((k, lg) for k, _, lg in COLUMNS)[key]
        plot = self.plots[n]
        plot.setLogMode(y=log)
        y = self.data.get(key, [])
        if log:                                  # в лог-шкале нули и минусы не рисуются
            pairs = [(t, v) for t, v in zip(self.t, y) if v > 0]
            self.curves[n].setData([p[0] for p in pairs], [p[1] for p in pairs])
        else:
            self.curves[n].setData(self.t, y)
        plot.enableAutoRange(axis="y")

    def mark_event(self):
        """Щелчок по строке журнала - вертикальная линия на всех графиках в этот момент."""
        line = self.log_view.textCursor().block().text()
        try:
            t = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            return
        for marker in self.markers:
            marker.setValue(t)
            marker.show()
