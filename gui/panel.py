"""Вкладка одного резонатора: тренировка, пороги вакуума, ручное управление, графики."""
import math
import time

import pyqtgraph as pg
from PyQt5 import QtWidgets

from trainer.core import UP, DOWN, ZONE, MANUAL

HISTORY = 3600   # сколько последних точек держать на графиках

STATE_TEXT = {
    "MANUAL": "Ручной режим",
    "WAIT_GOOD": "Ждём Good",
    "DELAY": "Отсчёт Response Delay",
    "BACKOFF": "Very Bad, ждём Timeout",
}


def vac_color(vac, s):
    """Цвет вакуума, как в старой программе."""
    if vac >= s.very_bad:
        return "magenta"
    if vac >= s.bad:
        return "red"
    if vac <= s.good:
        return "green"
    return "orange"


class ResonatorPanel(QtWidgets.QWidget):
    def __init__(self, name, trainer):
        super().__init__()
        self.name = name
        self.tr = trainer
        self.tr.log = self.add_log
        self.now = 0
        self.t, self.u, self.vac = [], [], []

        # ---------- Тренировка ----------
        self.auto = QtWidgets.QCheckBox()
        self.auto.clicked.connect(self.on_auto)       # clicked - только от пользователя
        self.mode = QtWidgets.QLabel("MANUAL")
        self.mode.setStyleSheet("font-weight: bold")
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.auto)
        row.addWidget(self.mode)
        row.addStretch()

        self.seq = QtWidgets.QComboBox()
        self.seq.addItems([UP, DOWN, ZONE])
        self.seq.setCurrentText(trainer.s.sequence)
        self.seq.currentTextChanged.connect(self.on_sequence)

        self.start_lbl = QtWidgets.QLabel()
        self.stop_lbl = QtWidgets.QLabel()
        self.state_lbl = QtWidgets.QLabel()

        f = QtWidgets.QFormLayout()
        f.addRow("AUTO / MANUAL", row)
        f.addRow("Step KV", self.field("step"))
        f.addRow("Low KV", self.field("low"))
        f.addRow("High KV", self.field("high"))
        f.addRow("Sequence", self.seq)
        f.addRow("Start", self.start_lbl)
        f.addRow("Stop", self.stop_lbl)
        f.addRow("Response Delay, с", self.field("response_delay"))
        f.addRow("Timeout, с", self.field("timeout"))
        f.addRow("Состояние", self.state_lbl)
        box_train = QtWidgets.QGroupBox("Тренировка")
        box_train.setLayout(f)

        # ---------- Вакуум ----------
        self.vac_lbl = QtWidgets.QLabel()
        self.vac_lbl.setStyleSheet("font-size: 18px")
        f = QtWidgets.QFormLayout()
        f.addRow("Сейчас, Торр", self.vac_lbl)
        f.addRow("Good", self.field("good"))
        f.addRow("Bad", self.field("bad"))
        f.addRow("Very Bad", self.field("very_bad"))
        box_vac = QtWidgets.QGroupBox("Вакуум")
        box_vac.setLayout(f)

        # ---------- Ручное управление ----------
        self.u_lbl = QtWidgets.QLabel()
        self.u_lbl.setStyleSheet("font-size: 18px")
        self.u_set = QtWidgets.QDoubleSpinBox()
        self.u_set.setRange(0, 100)
        self.u_set.setDecimals(2)
        self.u_set.setSingleStep(0.1)
        self.u_set.setSuffix(" кВ")
        self.u_set.setKeyboardTracking(False)   # применять по Enter/стрелкам, а не на каждую цифру
        self.u_set.setValue(trainer.res.read_setpoint())
        self.u_set.valueChanged.connect(self.on_manual)
        f = QtWidgets.QFormLayout()
        f.addRow("U уставка сейчас", self.u_lbl)
        f.addRow("Задать U", self.u_set)
        self.box_manual = QtWidgets.QGroupBox("Ручное управление")
        self.box_manual.setLayout(f)

        # ---------- Журнал ----------
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1000)

        left = QtWidgets.QVBoxLayout()
        for w in (box_train, box_vac, self.box_manual, self.log_view):
            left.addWidget(w)
        left_w = QtWidgets.QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(360)

        # ---------- Графики ----------
        self.plot_u = pg.PlotWidget(title="U уставка (кВ) от времени (с)")
        self.curve_u = self.plot_u.plot(pen="y")
        self.plot_vac = pg.PlotWidget(title="Вакуум (Торр) от времени (с)")
        self.plot_vac.setLogMode(y=True)
        self.curve_vac = self.plot_vac.plot(pen="c")
        self.lines = {}   # линии порогов на графике вакуума
        for attr, color in (("good", "g"), ("bad", "r"), ("very_bad", "m")):
            self.lines[attr] = pg.InfiniteLine(angle=0, pen=pg.mkPen(color, style=2))
            self.plot_vac.addItem(self.lines[attr])
        self.plot_vu = pg.PlotWidget(title="Вакуум (Торр) от U (кВ)")
        self.plot_vu.setLogMode(y=True)
        self.curve_vu = self.plot_vu.plot(pen=None, symbol="o", symbolSize=3,
                                          symbolPen=None, symbolBrush="c")
        for p in (self.plot_u, self.plot_vac, self.plot_vu):
            p.showGrid(x=True, y=True)
        self.plot_vac.setXLink(self.plot_u)   # общая ось времени

        right = QtWidgets.QVBoxLayout()
        for p in (self.plot_u, self.plot_vac, self.plot_vu):
            right.addWidget(p)

        main = QtWidgets.QHBoxLayout(self)
        main.addWidget(left_w)
        main.addLayout(right)

    # ------------------------------------------------------------------

    def field(self, attr):
        """Поле ввода настройки. Значение применяется по Enter (как в README)."""
        edit = QtWidgets.QLineEdit(f"{getattr(self.tr.s, attr):g}")

        def apply():
            old = getattr(self.tr.s, attr)
            try:
                setattr(self.tr.s, attr, float(edit.text().replace(",", ".")))
            except ValueError:
                edit.setText(f"{old:g}")
                return
            error = self.tr.s.check()
            if error:
                setattr(self.tr.s, attr, old)   # не применяем
                self.add_log(error)
            else:
                self.add_log(f"{attr} = {getattr(self.tr.s, attr):g}")
            edit.setText(f"{getattr(self.tr.s, attr):g}")

        edit.returnPressed.connect(apply)
        return edit

    def add_log(self, msg):
        self.log_view.appendPlainText(f"{time.strftime('%H:%M:%S')}  {msg}")

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

    def update_view(self, now):
        """Вызывается главным окном после каждого tick()."""
        self.now = now
        tr = self.tr
        u = tr.res.read_setpoint()
        auto = tr.state != MANUAL

        if not auto and self.auto.isChecked():   # программа сама сняла галку (п.5)
            self.auto.setChecked(False)
            if tr.finished:
                QtWidgets.QApplication.beep()    # TODO: фанфары
        if not auto:
            tr.sync_direction(u)                 # чтобы Start/Stop показывали правду

        self.mode.setText("AUTO" if auto else "MANUAL")
        self.mode.setStyleSheet("font-weight: bold; color: " + ("green" if auto else "gray"))
        self.box_manual.setEnabled(not auto)
        self.start_lbl.setText(f"{tr.start:g} кВ")
        self.stop_lbl.setText(f"{tr.stop:g} кВ")
        self.state_lbl.setText(STATE_TEXT[tr.state])
        self.u_lbl.setText(f"{u:.2f} кВ")
        self.vac_lbl.setText(f"{tr.vacuum:.1e}")
        self.vac_lbl.setStyleSheet(f"font-size: 18px; color: {vac_color(tr.vacuum, tr.s)}")
        if auto:   # в AUTO поле ручной уставки просто следует за алгоритмом
            self.u_set.blockSignals(True)
            self.u_set.setValue(u)
            self.u_set.blockSignals(False)

        self.t.append(now)
        self.u.append(u)
        self.vac.append(tr.vacuum)
        self.t, self.u, self.vac = self.t[-HISTORY:], self.u[-HISTORY:], self.vac[-HISTORY:]
        self.curve_u.setData(self.t, self.u)
        self.curve_vac.setData(self.t, self.vac)
        self.curve_vu.setData(self.u, self.vac)
        for attr, line in self.lines.items():
            line.setValue(math.log10(getattr(tr.s, attr)))   # в лог-режиме ось = log10
