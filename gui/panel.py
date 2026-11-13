"""Окно одного резонатора: графики сверху, все поля ввода под ними
(узкое окно, чтобы на мониторе помещалось два резонатора рядом)."""
import math
import time

import pyqtgraph as pg
from PyQt5 import QtWidgets

from trainer.core import UP, DOWN, ZONE, SAW, MANUAL

HISTORY = 3600   # сколько последних точек держать на графиках

STATE_TEXT = {
    "MANUAL": "Ручной режим",
    "WAIT_GOOD": "Ждём Good",
    "DELAY": "Отсчёт Response Delay",
    "BACKOFF": "Отступили, ждём Good / Timeout",
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


def spin(value, maximum, suffix, handler):
    """Поле с числом и стрелками. Применяется по Enter/стрелкам, а не на каждую цифру."""
    box = QtWidgets.QDoubleSpinBox()
    box.setRange(0, maximum)
    box.setDecimals(2)
    box.setSingleStep(0.1)
    box.setSuffix(suffix)
    box.setKeyboardTracking(False)
    box.setValue(value)                  # сначала значение, потом обработчик
    box.valueChanged.connect(handler)
    return box


class ResonatorPanel(QtWidgets.QWidget):
    def __init__(self, name, trainer):
        super().__init__()
        self.setWindowTitle(name)
        self.name = name
        self.tr = trainer
        self.tr.log = self.add_log
        self.now = 0
        self.t, self.u, self.vac = [], [], []

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

        # ---------- Тренировка ----------
        self.auto = QtWidgets.QCheckBox()
        self.auto.clicked.connect(self.on_auto)       # clicked - только от пользователя
        self.mode = QtWidgets.QLabel("MANUAL")
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.auto)
        row.addWidget(self.mode)
        row.addStretch()

        self.seq = QtWidgets.QComboBox()
        self.seq.addItems([UP, DOWN, ZONE, SAW])
        self.seq.setCurrentText(trainer.s.sequence)
        self.seq.currentTextChanged.connect(self.on_sequence)

        self.start_stop = QtWidgets.QLabel()
        self.state_lbl = QtWidgets.QLabel()

        f = QtWidgets.QFormLayout()
        f.addRow("AUTO / MANUAL", row)
        f.addRow("Sequence", self.seq)
        f.addRow("Step KV", self.field("step"))
        f.addRow("Low KV", self.field("low"))
        f.addRow("High KV", self.field("high"))
        f.addRow("Start → Stop", self.start_stop)
        f.addRow("Response Delay, с", self.field("response_delay"))
        f.addRow("Timeout, с", self.field("timeout"))
        f.addRow("Состояние", self.state_lbl)
        box_train = QtWidgets.QGroupBox("Тренировка")
        box_train.setLayout(f)

        # ---------- Вакуум ----------
        self.vac_lbl = QtWidgets.QLabel()
        f = QtWidgets.QFormLayout()
        f.addRow("Сейчас, Торр", self.vac_lbl)
        f.addRow("Good", self.field("good"))
        f.addRow("Bad", self.field("bad"))
        f.addRow("Very Bad", self.field("very_bad"))
        box_vac = QtWidgets.QGroupBox("Вакуум")
        box_vac.setLayout(f)

        # ---------- Ток фидера (общий для ручного и AUTO) ----------
        self.i_set = spin(trainer.res.read_current(), 50, " А", self.on_current)
        f = QtWidgets.QFormLayout()
        f.addRow("I фидера", self.i_set)
        box_cur = QtWidgets.QGroupBox("Ток фидера")
        box_cur.setLayout(f)

        # ---------- Ручное управление напряжением ----------
        self.u_lbl = QtWidgets.QLabel()
        self.u_set = spin(trainer.res.read_setpoint(), 100, " кВ", self.on_manual)
        f = QtWidgets.QFormLayout()
        f.addRow("U сейчас", self.u_lbl)
        f.addRow("Задать U", self.u_set)
        self.box_manual = QtWidgets.QGroupBox("Ручное управление U")
        self.box_manual.setLayout(f)

        # ---------- Последнее сообщение (ошибки ввода, шаги алгоритма) ----------
        self.msg = QtWidgets.QLabel()

        # ---------- Раскладка: графики сверху, поля снизу ----------
        middle = QtWidgets.QVBoxLayout()
        for w in (box_vac, box_cur, self.box_manual):
            middle.addWidget(w)
        middle.addStretch()

        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(box_train)
        bottom.addLayout(middle)
        bottom.addStretch()

        main = QtWidgets.QVBoxLayout(self)
        for p in (self.plot_u, self.plot_vac, self.plot_vu):
            main.addWidget(p, stretch=1)
        main.addLayout(bottom)
        main.addWidget(self.msg)

    # ------------------------------------------------------------------

    def field(self, attr):
        """Поле ввода настройки. Значение применяется по Enter (как в README)."""
        edit = QtWidgets.QLineEdit(f"{getattr(self.tr.s, attr):g}")
        edit.setFixedWidth(90)

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
        self.msg.setText(f"{time.strftime('%H:%M:%S')}  {msg}")

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
        self.start_stop.setText(f"{tr.start:g} → {tr.stop:g} кВ")
        self.state_lbl.setText(STATE_TEXT[tr.state])
        self.u_lbl.setText(f"{u:.2f} кВ")
        self.vac_lbl.setText(f"{tr.vacuum:.1e}")
        self.vac_lbl.setStyleSheet(f"font-weight: bold; color: {vac_color(tr.vacuum, tr.s)}")
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
