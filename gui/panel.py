"""Окно одного резонатора = вкладка «Главная» старой программы, у каждого резонатора своя.

Сверху вниз: шапка (тумблер AUTO, лампочки, часы) -> плитки с измерениями ->
графики -> карточки управления -> нижняя панель (файл, Новая сессия, кнопки ГЕН/ББ/МОД).
"""
import math
import os
import time
from datetime import datetime

import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore

from gui import style
from gui.widgets import Card, Tile, Lamp, Toggle
from trainer.core import UP, DOWN, ZONE, SAW, MANUAL
from trainer.datafile import DataFile
from trainer.sim import u_from_power

STATE_TEXT = {
    "MANUAL": "Ручной режим",
    "WAIT_GOOD": "Ждём Good",
    "DELAY": "Отсчёт Response Delay",
    "BACKOFF": "Отступили, ждём Good / Timeout",
}
DAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
STEPS = {"Точно": 0.01, "Средне": 0.1, "Грубо": 1.0}   # шаг стрелок (умножается на масштаб поля)


def vac_color(vac, s):
    """Цвет вакуума, как в старой программе."""
    if vac >= s.very_bad:
        return style.MAGENTA
    if vac >= s.bad:
        return style.RED
    if vac <= s.good:
        return style.GREEN
    return style.ORANGE


class VacAxis(pg.AxisItem):
    """Ось вакуума: деления 1-2-5 в каждой декаде, подписи вида 2e-09.
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


def spin(value, maximum, suffix, handler, decimals=2):
    """Поле с числом и стрелками. Применяется по Enter/стрелкам, а не на каждую цифру."""
    box = QtWidgets.QDoubleSpinBox()
    box.setRange(0, maximum)
    box.setDecimals(decimals)
    box.setSuffix(suffix)
    box.setKeyboardTracking(False)
    box.setFixedWidth(125)
    box.setValue(value)                  # сначала значение, потом обработчик
    box.valueChanged.connect(handler)
    return box


def step_selector(spins):
    """Переключатель «Точно / Средне / Грубо» (ползунок из старой программы).
    spins - список пар (поле, масштаб): шаг стрелок = STEPS[...] * масштаб."""
    row = QtWidgets.QHBoxLayout()
    row.setSpacing(0)
    group = QtWidgets.QButtonGroup(row)

    def choose(name):
        for box, scale in spins:
            box.setSingleStep(STEPS[name] * scale)

    for name in STEPS:
        b = QtWidgets.QPushButton(name)
        b.setObjectName("segment")
        b.setCheckable(True)
        b.clicked.connect(lambda _, n=name: choose(n))
        group.addButton(b)
        row.addWidget(b)
        if name == "Средне":
            b.setChecked(True)
    choose("Средне")
    return row


class ResonatorPanel(QtWidgets.QWidget):
    def __init__(self, name, trainer, config):
        super().__init__()
        self.setWindowTitle(name)
        self.name = name
        self.tr = trainer
        self.tr.log = self.add_log
        self.cfg = config
        self.now = 0
        self.vac_in_amps = False                 # кнопка «Торр / А» на графике вакуума
        self.t, self.u_set_hist, self.u_hist, self.vac_hist = [], [], [], []
        self.file = DataFile(os.path.join(config["data_dir"], name))
        s, res = trainer.s, trainer.res

        # ================= Шапка =================
        title = QtWidgets.QLabel(name)
        title.setObjectName("bigTitle")
        self.auto = Toggle()
        self.auto.clicked.connect(self.on_auto)  # clicked - только от пользователя
        self.mode = QtWidgets.QLabel("MANUAL")
        self.mode.setObjectName("bigTitle")
        self.lamp_link = Lamp("Связь")
        self.lamp_ready = Lamp("Готовность")
        self.lamp_agc_u = Lamp("АРУ U")
        self.lamp_agc_i = Lamp("АРУ I")
        self.lamp_auto = Lamp("Автомат")
        self.clock = QtWidgets.QLabel()
        self.clock.setObjectName("clock")

        head = QtWidgets.QHBoxLayout()
        for w in (title, self.auto, self.mode):
            head.addWidget(w)
        head.addStretch()
        for w in (self.lamp_link, self.lamp_ready, self.lamp_agc_u, self.lamp_agc_i, self.lamp_auto):
            head.addWidget(w)
            head.addSpacing(8)
        head.addWidget(self.clock)

        # ================= Плитки с измерениями (блок «Данные») =================
        self.tiles = {
            "u_set": Tile("U уставка", "кВ"),
            "u": Tile("U резонатора", "кВ"),
            "u_no": Tile("U рез. НО", "кВ"),
            "i": Tile("I фидера", "А"),
            "phase": Tile("Фазометр", "°"),
            "vac": Tile("Вакуум", "Торр"),
            "pump": Tile("I насоса", "А"),
            "p_fwd": Tile("Падающая", "кВт"),
            "p_ref": Tile("Отражённая", "кВт"),
            "start_stop": Tile("Start → Stop", "кВ"),
        }
        tiles = QtWidgets.QGridLayout()
        for k, tile in enumerate(self.tiles.values()):
            tiles.addWidget(tile, k // 5, k % 5)

        # ================= Графики =================
        self.plot_u = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
        self.plot_u.addLegend(offset=(10, 5))
        self.curve_u_set = self.plot_u.plot(pen=pg.mkPen(style.YELLOW, width=2), name="уставка")
        self.curve_u = self.plot_u.plot(pen=pg.mkPen(style.ACCENT, width=1), name="измерено")

        self.plot_vac = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem(), "left": VacAxis("left")})
        self.plot_vac.setLogMode(y=True)
        self.curve_vac = self.plot_vac.plot(pen=pg.mkPen("#56d4dd", width=1.5))
        self.lines = {}   # линии порогов на графике вакуума
        for attr, color in (("good", style.GREEN), ("bad", style.RED), ("very_bad", style.MAGENTA)):
            self.lines[attr] = pg.InfiniteLine(angle=0, pen=pg.mkPen(color, width=1.5,
                                                                      style=QtCore.Qt.DashLine))
            self.plot_vac.addItem(self.lines[attr])
        self.plot_vac.setXLink(self.plot_u)      # общая ось времени

        self.plot_vu = pg.PlotWidget(axisItems={"left": VacAxis("left")})
        self.plot_vu.setLogMode(y=True)
        self.curve_vu = self.plot_vu.plot(pen=None, symbol="o", symbolSize=3,
                                          symbolPen=None, symbolBrush="#56d4dd")

        for p in (self.plot_u, self.plot_vac, self.plot_vu):
            p.showGrid(x=True, y=True, alpha=0.15)
            p.setClipToView(True)
            p.setDownsampling(auto=True)
            p.setMinimumHeight(90)

        units = QtWidgets.QPushButton("Торр")    # кнопка «A / торр» со старой Главной
        units.setFixedWidth(70)
        units.clicked.connect(lambda: self.on_units(units))
        card_u = Card("Напряжение, кВ")
        card_u.body.addWidget(self.plot_u)
        self.card_vac = Card("Вакуум от времени", extra=units)
        self.card_vac.body.addWidget(self.plot_vac)
        card_vu = Card("Вакуум от напряжения")
        card_vu.body.addWidget(self.plot_vu)

        plots = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(plots)
        lay.setContentsMargins(0, 0, 0, 0)
        for c in (card_u, self.card_vac, card_vu):
            lay.addWidget(c)

        # ================= Автоматическое управление =================
        self.seq = QtWidgets.QComboBox()
        self.seq.addItems([UP, DOWN, ZONE, SAW])
        self.seq.setCurrentText(s.sequence)
        self.seq.setFixedWidth(150)
        self.seq.currentTextChanged.connect(self.on_sequence)
        self.low = spin(s.low, 200, " кВ", lambda v: self.set_param("low", v))
        self.high = spin(s.high, 200, " кВ", lambda v: self.set_param("high", v))
        self.step = spin(s.step, 50, " кВ", lambda v: self.set_param("step", v))
        delay = spin(s.response_delay, 3600, " с", lambda v: self.set_param("response_delay", v), 0)
        timeout = spin(s.timeout, 3600, " с", lambda v: self.set_param("timeout", v), 0)
        delay.setSingleStep(1)
        timeout.setSingleStep(1)
        self.state_lbl = QtWidgets.QLabel()

        self.btn_stop = QtWidgets.QPushButton("Stop")      # пауза автомата
        self.btn_start = QtWidgets.QPushButton("Start")    # продолжить
        self.btn_rev = QtWidgets.QPushButton("Reverse")
        self.btn_stop.clicked.connect(lambda: self.tr.set_paused(True))
        self.btn_start.clicked.connect(lambda: self.tr.set_paused(False))
        self.btn_rev.clicked.connect(self.tr.reverse)
        buttons = QtWidgets.QHBoxLayout()
        for b in (self.btn_stop, self.btn_start, self.btn_rev):
            buttons.addWidget(b)

        # поля в две колонки, чтобы карточка была невысокой
        grid = QtWidgets.QGridLayout()
        left_col = (("Sequence", self.seq), ("Low (U MIN)", self.low),
                    ("High (U MAX)", self.high), ("Step", self.step))
        right_col = (("Response Delay", delay), ("Timeout", timeout),
                     ("Шаг стрелок", step_selector([(self.low, 10), (self.high, 10), (self.step, 1)])))
        for col, rows in ((0, left_col), (2, right_col)):
            for r, (text, w) in enumerate(rows):
                grid.addWidget(QtWidgets.QLabel(text), r, col)
                if isinstance(w, QtWidgets.QLayout):
                    grid.addLayout(w, r, col + 1)
                else:
                    grid.addWidget(w, r, col + 1)
        self.state_lbl.setStyleSheet(f"color: {style.YELLOW}; font-weight: 600")
        self.card_auto = Card("Автоматическое управление")
        self.card_auto.body.addLayout(grid)
        self.card_auto.body.addWidget(self.state_lbl)
        self.card_auto.body.addLayout(buttons)

        # ================= Пороги вакуума (в А и в Торр, как было) =================
        grid = QtWidgets.QGridLayout()
        for col, text in ((1, "Ток насоса, А"), (2, "Торр")):
            h = QtWidgets.QLabel(text)
            h.setObjectName("muted")
            grid.addWidget(h, 0, col)
        self.thr_fields = {}
        rows = (("good", "Good", style.GREEN), ("bad", "Bad (стоп)", style.RED),
                ("very_bad", "Very Bad (назад)", style.MAGENTA))
        for r, (attr, text, color) in enumerate(rows, start=1):
            label = QtWidgets.QLabel(text)
            label.setStyleSheet(f"color: {color}; font-weight: 600")
            amps = QtWidgets.QLineEdit()
            torr = QtWidgets.QLineEdit()
            for e in (amps, torr):
                e.setFixedWidth(92)
                e.setStyleSheet(f"color: {color}")
            amps.returnPressed.connect(lambda a=attr, e=amps: self.set_threshold(a, e.text(), True))
            torr.returnPressed.connect(lambda a=attr, e=torr: self.set_threshold(a, e.text(), False))
            self.thr_fields[attr] = (amps, torr)
            grid.addWidget(label, r, 0)
            grid.addWidget(amps, r, 1)
            grid.addWidget(torr, r, 2)
        self.show_thresholds()
        card_thr = Card("Пороги вакуума")
        card_thr.body.addLayout(grid)
        card_thr.body.addStretch()

        # ================= Ручное управление =================
        self.u_set = spin(res.read_setpoint(), 200, " кВ", self.on_manual)
        self.i_set = spin(res.read_current(), 50, " А", self.on_current)
        grid = QtWidgets.QGridLayout()                  # U и I в одну строку - карточка ниже
        grid.addWidget(QtWidgets.QLabel("U рез."), 0, 0)
        grid.addWidget(self.u_set, 0, 1)
        grid.addWidget(QtWidgets.QLabel("I фид."), 0, 2)
        grid.addWidget(self.i_set, 0, 3)
        grid.addWidget(QtWidgets.QLabel("Шаг"), 1, 0)
        grid.addLayout(step_selector([(self.u_set, 10), (self.i_set, 1)]), 1, 1, 1, 3)
        self.card_manual = Card("Ручное управление")
        self.card_manual.body.addLayout(grid)

        # Две колонки: автоматика | пороги + ручное. Не растягиваются, прижаты влево;
        # на маленьком экране - прокрутка
        right = QtWidgets.QWidget()
        col = QtWidgets.QVBoxLayout(right)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(card_thr)
        col.addWidget(self.card_manual)
        fields = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(fields)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.card_auto, alignment=QtCore.Qt.AlignTop)
        lay.addWidget(right, alignment=QtCore.Qt.AlignTop)
        lay.addStretch(1)                 # всё лишнее место - пустоте справа
        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(fields)
        scroll.setWidgetResizable(True)

        self.fields = fields
        self.splitter = splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)   # границу можно тянуть
        splitter.addWidget(plots)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        # ================= Нижняя панель =================
        self.msg = QtWidgets.QLabel()
        self.msg.setObjectName("muted")
        self.file_lbl = QtWidgets.QLabel()
        self.file_lbl.setObjectName("muted")
        new_session = QtWidgets.QPushButton("Новая сессия")
        new_session.clicked.connect(self.on_new_session)
        foot = QtWidgets.QHBoxLayout()
        texts = QtWidgets.QVBoxLayout()
        texts.addWidget(self.msg)
        texts.addWidget(self.file_lbl)
        foot.addLayout(texts)
        foot.addStretch()
        foot.addWidget(new_session)
        foot.addSpacing(16)
        for text, command in (("Сброс ГЕН", res.reset_gen), ("Сброс ББ", res.reset_bb),
                              ("Вкл МОД", res.mod_on), ("Выкл МОД", res.mod_off)):
            b = QtWidgets.QPushButton(text)
            b.setObjectName("danger")
            b.clicked.connect(lambda _, t=text, c=command: self.command(t, c))
            foot.addWidget(b)

        main = QtWidgets.QVBoxLayout(self)
        main.addLayout(head)
        main.addLayout(tiles)
        main.addWidget(splitter, stretch=1)
        main.addLayout(foot)
        self.file_lbl.setText(f"Запись в файл {self.file.name}")

    def showEvent(self, event):
        """При открытии окна поля управления получают ровно свою высоту, остальное - графикам."""
        super().showEvent(event)
        h = self.fields.sizeHint().height() + 2
        self.splitter.setSizes([self.splitter.height() - h, h])

    # ------------------------------------------------------------------ обработчики

    def add_log(self, msg):
        self.msg.setText(f"{time.strftime('%H:%M:%S')}  {msg}")

    def set_param(self, attr, value):
        """Поле автоматики изменено (Enter или стрелки)."""
        old = getattr(self.tr.s, attr)
        setattr(self.tr.s, attr, value)
        error = self.tr.s.check()
        if error:
            setattr(self.tr.s, attr, old)        # не применяем и возвращаем старое
            self.add_log(error)
            box = {"low": self.low, "high": self.high, "step": self.step}.get(attr)
            if box:
                box.blockSignals(True)
                box.setValue(old)
                box.blockSignals(False)

    def set_threshold(self, attr, text, in_amps):
        """Порог введён в амперах или в торрах - второе поле пересчитывается само."""
        try:
            value = float(text.replace(",", "."))
        except ValueError:
            self.show_thresholds()
            return
        if in_amps:
            value /= self.cfg["vac_coeff"]
        old = getattr(self.tr.s, attr)
        setattr(self.tr.s, attr, value)
        error = self.tr.s.check()
        if error:
            setattr(self.tr.s, attr, old)
            self.add_log(error)
        else:
            self.add_log(f"Порог {attr} = {value:.1e} Торр")
        self.show_thresholds()

    def show_thresholds(self):
        for attr, (amps, torr) in self.thr_fields.items():
            v = getattr(self.tr.s, attr)
            amps.setText(f"{v * self.cfg['vac_coeff']:.2e}")
            torr.setText(f"{v:.2e}")

    def on_auto(self, checked):
        if checked:
            if not self.tr.enable(self.now):
                self.auto.setChecked(False)
        else:
            self.tr.disable()

    def on_sequence(self, text):
        self.tr.s.sequence = text
        self.add_log(f"Sequence = {text}")

    def on_manual(self, value):
        if self.tr.state == MANUAL:
            self.tr.res.set_voltage(value)
            self.add_log(f"Вручную: U = {value:.2f} кВ")

    def on_current(self, value):
        self.tr.res.set_current(value)
        self.add_log(f"I фидера = {value:.2f} А")

    def on_units(self, button):
        self.vac_in_amps = not self.vac_in_amps
        button.setText("А" if self.vac_in_amps else "Торр")
        self.card_vac.findChild(QtWidgets.QLabel).setText(
            "Ток насоса от времени" if self.vac_in_amps else "Вакуум от времени")

    def on_new_session(self):
        """Новый файл данных + очистить графики (как в старой программе)."""
        self.file.new_session()
        self.t, self.u_set_hist, self.u_hist, self.vac_hist = [], [], [], []
        self.file_lbl.setText(f"Начата запись в файл {self.file.name}")

    def command(self, text, func):
        func()
        self.add_log(f"Команда: {text}")

    @staticmethod
    def set_border(card, color):
        card.setStyleSheet(f"QFrame#card {{ border: 2px solid {color}; }}")

    # ------------------------------------------------------------------ раз в тик

    def update_view(self, now):
        """Вызывается главным окном после каждого tick()."""
        self.now = now
        tr, s, res = self.tr, self.tr.s, self.tr.res
        m = res.read_measurements()
        u_set = res.read_setpoint()
        vac = tr.vacuum
        auto = tr.state != MANUAL

        if not auto and self.auto.isChecked():   # программа сама сняла галку (дошли до Stop)
            self.auto.setChecked(False)
            if tr.finished:
                QtWidgets.QApplication.beep()    # TODO: фанфары
        if not auto:
            tr.sync_direction(u_set)             # чтобы Start/Stop показывали правду

        # --- шапка
        self.mode.setText("AUTO" if auto else "MANUAL")
        self.mode.setStyleSheet(f"color: {style.GREEN if auto else style.MUTED}")
        d = datetime.now()
        self.clock.setText(d.strftime("%Y-%m-%d  %H:%M:%S  ") + DAYS[d.weekday()])
        self.lamp_link.set(style.GREEN if res.connected else style.RED)
        self.lamp_ready.set(style.GREEN if m["ready"] else style.RED)
        self.lamp_agc_u.set(style.GREEN if m["agc_u"] else style.GRAY)
        self.lamp_agc_i.set(style.GREEN if m["agc_i"] else style.GRAY)
        self.lamp_auto.set(style.YELLOW if auto and tr.paused else style.GREEN if auto else style.RED)

        # --- плитки
        u_no = u_from_power(m["p_fwd"], m["p_ref"], self.cfg["r_sh"])
        t = self.tiles
        t["u_set"].set(f"{u_set:.2f}", style.YELLOW)
        t["u"].set(f"{m['u']:.1f}")
        t["u_no"].set(f"{u_no:.1f}")
        t["i"].set(f"{m['i']:.1f}")
        t["phase"].set(f"{m['phase']:.1f}")
        t["vac"].set(f"{vac:.1e}", vac_color(vac, s))
        t["pump"].set(f"{m['pump_a']:.1e}", vac_color(vac, s))
        t["p_fwd"].set(f"{m['p_fwd']:.2f}")
        t["p_ref"].set(f"{m['p_ref']:.2f}",
                       style.RED if m["p_ref"] > self.cfg["u_otr_max"] else style.TEXT)
        t["start_stop"].set(f"{tr.start:g}→{tr.stop:g}")

        # --- управление
        self.state_lbl.setText("● " + ("Пауза · " if auto and tr.paused else "") + STATE_TEXT[tr.state])
        if self.seq.currentText() != s.sequence:   # Reverse мог поменять UP <-> DOWN
            self.seq.blockSignals(True)
            self.seq.setCurrentText(s.sequence)
            self.seq.blockSignals(False)
        for b in (self.btn_stop, self.btn_start, self.btn_rev):
            b.setEnabled(auto)
        self.u_set.setEnabled(not auto)            # в AUTO напряжение ведёт алгоритм
        self.set_border(self.card_auto, style.GREEN if auto else style.BORDER)
        self.set_border(self.card_manual, style.BORDER if auto else style.ACCENT)
        if auto:   # поле ручной уставки просто следует за алгоритмом
            self.u_set.blockSignals(True)
            self.u_set.setValue(u_set)
            self.u_set.blockSignals(False)

        # --- запись в файл
        self.file.write(m, vac, u_set, res.read_current(), "AUTO" if auto else "MANUAL")

        # --- графики (ось X - реальное время)
        n = self.cfg["history_s"]
        self.t = (self.t + [time.time()])[-n:]
        self.u_set_hist = (self.u_set_hist + [u_set])[-n:]
        self.u_hist = (self.u_hist + [m["u"]])[-n:]
        self.vac_hist = (self.vac_hist + [vac])[-n:]
        k = self.cfg["vac_coeff"] if self.vac_in_amps else 1.0
        self.curve_u_set.setData(self.t, self.u_set_hist)
        self.curve_u.setData(self.t, self.u_hist)
        self.curve_vac.setData(self.t, [v * k for v in self.vac_hist])
        self.curve_vu.setData(self.u_set_hist, self.vac_hist)
        for attr, line in self.lines.items():
            line.setValue(math.log10(getattr(s, attr) * k))   # в лог-режиме ось = log10
