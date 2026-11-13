"""Окно одного резонатора = вкладка «Главная» старой программы (у каждого резонатора своя).
Те же группы, те же рамки, лампочки, стрелки и тумблер - только сложено вертикально,
чтобы два окна помещались на одном мониторе:

    Графики (U и вакуум)
    Данные | Вакуум + Ручное управление | лампочки
    Автоматическое управление | тумблер AUTO/MANUAL
    часы, I насоса / U, Новая сессия, Сброс ГЕН/ББ, Вкл/Выкл МОД
"""
import math
import os
import time
from datetime import datetime

import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui

from gui import style
from gui.style import icon
from gui.vac_u import VacAxis, VacUWindow
from gui.widgets import Lamp, Toggle, ArrowField, PrecisionSlider, value_box, MONO
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
# пороги вакуума: как в старой программе - BACK оранжевый, STOP красный, GOOD зелёный
THRESHOLDS = (("very_bad", "orange"), ("bad", "red"), ("good", "green"))


def vac_color(vac, s):
    """Цвет значения вакуума, как в старой программе ("" - обычный цвет текста)."""
    if vac >= s.very_bad:
        return "magenta"
    if vac >= s.bad:
        return "red"
    if vac <= s.good:
        return "green"
    return ""


def show(box, text, color=""):
    box.setText(text)
    box.setStyleSheet(f"color: {color}" if color else "")


class ResonatorPanel(QtWidgets.QWidget):
    def __init__(self, name, trainer, config):
        super().__init__()
        self.setWindowTitle(name)
        self.name = name
        self.tr = trainer
        self.tr.log = self.add_log
        self.cfg = config
        self.now = 0
        self.t, self.u_hist, self.u_set_hist, self.vac_hist = [], [], [], []
        self.file = DataFile(os.path.join(config["data_dir"], name))
        self.vac_u = VacUWindow(name)
        s, res = trainer.s, trainer.res

        # ========================= Графики =========================
        self.plot_u = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
        self.plot_u.setTitle("Voltage (kV)", color="y", size="12pt")
        self.plot_u.addLegend(offset=(10, 5))
        self.curve_u = self.plot_u.plot(pen=pg.mkPen((255, 0, 0)), name="U резонатора")
        self.curve_u_set = self.plot_u.plot(pen=pg.mkPen("y", style=QtCore.Qt.DashLine), name="уставка")
        self.plot_vac = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem(), "left": VacAxis("left")})
        self.plot_vac.setTitle("Vacuum (torr)", color="y", size="12pt")
        self.plot_vac.setLogMode(y=True)
        self.curve_vac = self.plot_vac.plot(pen=pg.mkPen((255, 0, 0)))
        self.lines = {}   # пороги пунктиром тех же цветов
        for attr, color in THRESHOLDS:
            self.lines[attr] = pg.InfiniteLine(angle=0, pen=pg.mkPen(color, style=QtCore.Qt.DashLine))
            self.plot_vac.addItem(self.lines[attr])
        for p in (self.plot_u, self.plot_vac):
            p.showGrid(x=True, y=True)
            p.setClipToView(True)
            p.setDownsampling(auto=True)
            p.setMinimumHeight(90)
        self.plot_vac.setXLink(self.plot_u)

        self.units = QtWidgets.QPushButton("A")        # как в старой программе: A <-> торр
        self.units.setFixedWidth(60)
        self.units.clicked.connect(self.on_units)
        btn_vu = QtWidgets.QPushButton("Вакуум от U ↗")
        btn_vu.clicked.connect(lambda: (self.vac_u.show(), self.vac_u.raise_()))
        top = QtWidgets.QHBoxLayout()
        top.addStretch()
        top.addWidget(QtWidgets.QLabel("Вакуум в:"))
        top.addWidget(self.units)
        top.addWidget(btn_vu)
        box_plots = QtWidgets.QGroupBox("Графики")
        style.group(box_plots, "darkblue")
        lay = QtWidgets.QVBoxLayout(box_plots)
        lay.addLayout(top)
        lay.addWidget(self.plot_u)
        lay.addWidget(self.plot_vac)

        # ========================= Данные =========================
        self.data = {}
        rows = (("u", "U резонатора", "кВ"), ("i", "I фидера", "A"), ("vac", "Вакуум", "Торр"),
                ("pump", "I насоса", "A"), ("p_fwd", "Падающая", "кВт"), ("p_ref", "Отраженная", "кВт"),
                ("phase", "Фазометр", "грд"), ("u_no", "U резонатора НО", "кВ"))
        grid = QtWidgets.QGridLayout()
        for r, (key, text, unit) in enumerate(rows):
            self.data[key] = value_box()
            grid.addWidget(QtWidgets.QLabel(text), r, 0)
            grid.addWidget(self.data[key], r, 1)
            grid.addWidget(QtWidgets.QLabel(unit), r, 2)
        box_data = QtWidgets.QGroupBox("Данные")
        style.group(box_data, "cyan")
        box_data.setLayout(grid)

        # ========================= Вакуум (пороги) =========================
        grid = QtWidgets.QGridLayout()
        self.thr = {}
        for r, (attr, color) in enumerate(THRESHOLDS):
            amps, torr = QtWidgets.QLineEdit(), QtWidgets.QLineEdit()
            for e in (amps, torr):
                e.setFixedWidth(90)
                e.setFont(MONO)
                e.setStyleSheet(f"color: {color}")
            amps.returnPressed.connect(lambda a=attr: self.set_threshold(a, True))
            torr.returnPressed.connect(lambda a=attr: self.set_threshold(a, False))
            self.thr[attr] = (amps, torr)
            grid.addWidget(amps, r, 0)
            grid.addWidget(QtWidgets.QLabel("A"), r, 1)
            grid.addWidget(torr, r, 3)
            grid.addWidget(QtWidgets.QLabel("Торр"), r, 4)
        btn_set = QtWidgets.QPushButton("set")     # применить все три поля в амперах
        btn_set.clicked.connect(lambda: [self.set_threshold(a, True) for a, _ in THRESHOLDS])
        grid.addWidget(btn_set, 1, 2)
        self.show_thresholds()
        box_vac = QtWidgets.QGroupBox("Вакуум")
        style.group(box_vac, "green")
        box_vac.setLayout(grid)

        # ========================= Ручное управление =========================
        self.slider_manual = PrecisionSlider(["0.1/0.01", "1/0.1", "10/1"],
                                             [(0.1, 1, 10), (0.01, 0.1, 1)])   # шаги для U (кВ) и I (А)
        self.u_field = ArrowField(res.read_setpoint(), "кВ", self.on_manual_u,
                                  lambda: self.slider_manual.step(0))
        self.i_field = ArrowField(res.read_current(), "А", self.on_manual_i,
                                  lambda: self.slider_manual.step(1))
        grid = QtWidgets.QGridLayout()
        grid.addWidget(QtWidgets.QLabel("U резонатора"), 0, 0)
        grid.addWidget(self.u_field, 0, 1)
        grid.addWidget(QtWidgets.QLabel("I фидера"), 1, 0)
        grid.addWidget(self.i_field, 1, 1)
        grid.addWidget(self.slider_manual, 0, 2, 2, 1)
        self.box_manual = QtWidgets.QGroupBox("Ручное управление")
        style.group(self.box_manual, "red", 5)        # MANUAL - активна, красная рамка
        self.box_manual.setLayout(grid)

        # ========================= Лампочки =========================
        self.lamp_link, self.lamp_ready, self.lamp_agc_u, self.lamp_agc_i = Lamp(), Lamp(), Lamp(), Lamp()
        lamps = QtWidgets.QGridLayout()
        for r, (lamp, text) in enumerate(((self.lamp_link, "Связь"), (self.lamp_ready, "Готовность"),
                                          (self.lamp_agc_u, "АРУ: U"), (self.lamp_agc_i, "АРУ: I"))):
            lamps.addWidget(lamp, r, 0)
            lamps.addWidget(QtWidgets.QLabel(text), r, 1)
        lamps.setRowStretch(4, 1)

        # ========================= Автоматическое управление =========================
        self.btn_start = QtWidgets.QPushButton("Start")
        self.btn_stop = QtWidgets.QPushButton("Stop")
        self.btn_rev = QtWidgets.QPushButton("Reverse")
        self.lamp_auto = Lamp()
        self.btn_start.clicked.connect(lambda: self.tr.set_paused(False))
        self.btn_stop.clicked.connect(lambda: self.tr.set_paused(True))
        self.btn_rev.clicked.connect(self.tr.reverse)
        col1 = QtWidgets.QVBoxLayout()
        col1.addWidget(self.btn_start)
        col1.addWidget(self.lamp_auto, alignment=QtCore.Qt.AlignCenter)
        col1.addWidget(self.btn_stop)
        col1.addWidget(self.btn_rev)

        self.arrow_up, self.arrow_down = QtWidgets.QLabel(), QtWidgets.QLabel()   # стрелки направления
        col2 = QtWidgets.QVBoxLayout()
        col2.addWidget(self.arrow_up)
        col2.addWidget(self.arrow_down)

        self.slider_auto = PrecisionSlider(["0.1", "1", "10"], [(0.1, 1, 10)])
        self.seq = QtWidgets.QComboBox()
        self.seq.addItems([UP, DOWN, ZONE, SAW])
        self.seq.setCurrentText(s.sequence)
        self.seq.currentTextChanged.connect(self.on_sequence)
        self.high = ArrowField(s.high, "кВ", lambda v: self.set_param("high", v), self.slider_auto.step)
        self.low = ArrowField(s.low, "кВ", lambda v: self.set_param("low", v), self.slider_auto.step)
        self.start_stop = QtWidgets.QLabel()
        col3 = QtWidgets.QGridLayout()
        for r, (text, w) in enumerate((("Sequence", self.seq), ("U MAX", self.high),
                                        ("U MIN", self.low), ("Start → Stop", self.start_stop))):
            col3.addWidget(QtWidgets.QLabel(text), r, 0)
            col3.addWidget(w, r, 1)

        col5 = QtWidgets.QGridLayout()
        for r, (text, attr, unit) in enumerate((("Шаг", "step", "кВ"),
                                                 ("Response Delay", "response_delay", "с"),
                                                 ("Timeout", "timeout", "с"))):
            col5.addWidget(QtWidgets.QLabel(text), r, 0)
            col5.addWidget(self.enter_field(attr), r, 1)
            col5.addWidget(QtWidgets.QLabel(unit), r, 2)
        self.state_lbl = QtWidgets.QLabel()
        self.state_lbl.setWordWrap(True)
        col5.addWidget(self.state_lbl, 3, 0, 1, 3)

        auto_lay = QtWidgets.QHBoxLayout()
        for c in (col1, col2, col3):
            auto_lay.addLayout(c)
        auto_lay.addWidget(self.slider_auto)
        auto_lay.addLayout(col5)
        self.box_auto = QtWidgets.QGroupBox("Автоматическое управление")
        style.group(self.box_auto, "gray", 5)
        self.box_auto.setLayout(auto_lay)

        self.toggle = Toggle()
        self.toggle.clicked.connect(self.on_auto)      # clicked - только от пользователя
        self.mode = QtWidgets.QLabel("MANUAL")
        self.mode.setAlignment(QtCore.Qt.AlignCenter)
        self.mode.setStyleSheet("font-weight: bold; font-size: 12pt")
        toggle_col = QtWidgets.QVBoxLayout()
        toggle_col.addStretch()
        toggle_col.addWidget(self.toggle, alignment=QtCore.Qt.AlignCenter)
        toggle_col.addWidget(self.mode)
        toggle_col.addStretch()

        # ========================= Сборка средней части =========================
        mid_col = QtWidgets.QVBoxLayout()
        mid_col.addWidget(box_vac)
        mid_col.addWidget(self.box_manual)
        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(box_data)
        row1.addLayout(mid_col)
        row1.addLayout(lamps)
        row1.addStretch(1)
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(self.box_auto)
        row2.addLayout(toggle_col)
        row2.addStretch(1)
        controls = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(controls)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(row1)
        lay.addLayout(row2)
        self.controls = controls
        scroll = QtWidgets.QScrollArea()          # на маленьком экране - прокрутка
        scroll.setWidget(controls)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        # Поля всегда видны целиком; только на совсем маленьком экране - прокрутка
        screen_h = QtWidgets.QApplication.primaryScreen().availableGeometry().height()
        scroll.setMinimumHeight(min(controls.sizeHint().height() + 12, screen_h - 450))

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)   # границу можно тянуть мышью
        self.splitter.addWidget(box_plots)
        self.splitter.addWidget(scroll)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        # ========================= Нижняя панель =========================
        self.clock = QtWidgets.QLineEdit()
        self.clock.setReadOnly(True)
        self.clock.setFont(QtGui.QFont("Consolas", 13))
        self.clock.setFixedWidth(330)
        self.foot = {"pump": value_box(), "u": value_box(), "u_no": value_box()}
        vals = QtWidgets.QGridLayout()
        for r, (key, text, unit) in enumerate((("pump", "I насоса", "A"), ("u", "U резонатора", "кВ"),
                                                ("u_no", "U рез НО", "кВ"))):
            vals.addWidget(QtWidgets.QLabel(text), r, 0)
            vals.addWidget(self.foot[key], r, 1)
            vals.addWidget(QtWidgets.QLabel(unit), r, 2)
        new_session = QtWidgets.QPushButton("Новая сессия")
        new_session.setMinimumHeight(40)
        new_session.clicked.connect(self.on_new_session)
        buttons = QtWidgets.QGridLayout()
        for k, (text, command) in enumerate((("Сброс ГЕН", res.reset_gen), ("Сброс ББ", res.reset_bb),
                                             ("Вкл МОД", res.mod_on), ("Выкл МОД", res.mod_off))):
            b = QtWidgets.QPushButton(text)
            b.clicked.connect(lambda _, t=text, c=command: self.command(t, c))
            buttons.addWidget(b, k // 2, k % 2)
        foot = QtWidgets.QHBoxLayout()
        foot.addWidget(self.clock)
        foot.addStretch(1)
        foot.addLayout(vals)
        foot.addWidget(new_session)
        foot.addLayout(buttons)

        self.status = QtWidgets.QLabel()          # строка внизу: запись в файл и сообщения
        self.status.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        main = QtWidgets.QVBoxLayout(self)
        main.addWidget(self.splitter, stretch=1)
        main.addLayout(foot)
        main.addWidget(self.status)
        self.file_msg = f"Начата запись в файл {self.file.name}"
        self.status.setText(self.file_msg)

    # ------------------------------------------------------------------ обработчики

    def add_log(self, msg):
        self.status.setText(f"{self.file_msg}    |    {time.strftime('%H:%M:%S')}  {msg}")

    def enter_field(self, attr):
        """Поле настройки автоматики. Применяется по Enter (как в README)."""
        edit = QtWidgets.QLineEdit(f"{getattr(self.tr.s, attr):g}")
        edit.setFixedWidth(70)
        edit.setFont(MONO)

        def apply():
            try:
                ok = self.set_param(attr, float(edit.text().replace(",", ".")))
            except ValueError:
                ok = False
            if ok is False:
                edit.setText(f"{getattr(self.tr.s, attr):g}")
        edit.returnPressed.connect(apply)
        return edit

    def set_param(self, attr, value):
        """Изменить настройку. Ерунду не принимаем (возвращаем False)."""
        old = getattr(self.tr.s, attr)
        setattr(self.tr.s, attr, value)
        error = self.tr.s.check()
        if error:
            setattr(self.tr.s, attr, old)
            self.add_log(error)
            return False
        self.add_log(f"{attr} = {value:g}")
        return True

    def set_threshold(self, attr, in_amps):
        """Порог введён в амперах или в торрах - второе поле пересчитывается само."""
        amps, torr = self.thr[attr]
        try:
            value = float((amps if in_amps else torr).text().replace(",", "."))
            if in_amps:
                value /= self.cfg["vac_coeff"]
            self.set_param(attr, value)
        except ValueError:
            pass
        self.show_thresholds()

    def show_thresholds(self):
        for attr, (amps, torr) in self.thr.items():
            v = getattr(self.tr.s, attr)
            amps.setText(f"{v * self.cfg['vac_coeff']:.1e}")
            torr.setText(f"{v:.1e}")

    def on_auto(self, checked):
        if checked:
            if not self.tr.enable(self.now):
                self.toggle.setChecked(False)
        else:
            self.tr.disable()

    def on_sequence(self, text):
        self.tr.s.sequence = text
        self.add_log(f"Sequence = {text}")

    def on_manual_u(self, value):
        if self.tr.state != MANUAL:
            return False
        self.tr.res.set_voltage(value)
        self.add_log(f"Вручную: U = {value:.2f} кВ")

    def on_manual_i(self, value):
        self.tr.res.set_current(value)          # ток фидера - и в ручном, и в AUTO
        self.add_log(f"I фидера = {value:.2f} А")

    def on_units(self):
        self.units.setText("торр" if self.units.text() == "A" else "A")
        self.plot_vac.setTitle("Ipump (A)" if self.units.text() == "торр" else "Vacuum (torr)",
                               color="y", size="12pt")

    def on_new_session(self):
        """Новый файл данных + очистить графики (как в старой программе)."""
        self.file.new_session()
        self.t, self.u_hist, self.u_set_hist, self.vac_hist = [], [], [], []
        self.vac_u.clear()
        self.file_msg = f"Начата запись в файл {self.file.name}"
        self.status.setText(self.file_msg)

    def command(self, text, func):
        func()
        self.add_log(f"Команда: {text}")

    # ------------------------------------------------------------------ раз в тик

    def update_view(self, now):
        """Вызывается главным окном после каждого tick()."""
        self.now = now
        tr, s, res = self.tr, self.tr.s, self.tr.res
        m = res.read_measurements()
        u_set = res.read_setpoint()
        vac = tr.vacuum
        auto = tr.state != MANUAL
        u_no = u_from_power(m["p_fwd"], m["p_ref"], self.cfg["r_sh"])

        if not auto and self.toggle.isChecked():   # программа сама сняла тумблер (дошли до Stop)
            self.toggle.setChecked(False)
            if tr.finished:
                QtWidgets.QApplication.beep()      # TODO: фанфары
        if not auto:
            tr.sync_direction(u_set)               # чтобы Start/Stop показывали правду

        # --- Данные (цвета как в старой программе)
        d = self.data
        show(d["u"], f"{m['u']:.1f}")
        show(d["i"], f"{m['i']:.1f}")
        show(d["vac"], f"{vac:.1e}", vac_color(vac, s))
        show(d["pump"], f"{m['pump_a']:.1e}", vac_color(vac, s))
        show(d["p_fwd"], f"{m['p_fwd']:.2f}")
        show(d["p_ref"], f"{m['p_ref']:.2f}", "red" if m["p_ref"] > self.cfg["u_otr_max"] else "")
        show(d["phase"], f"{m['phase']:.2f}")
        show(d["u_no"], f"{u_no:.1f}")
        show(self.foot["pump"], f"{m['pump_a']:.1e}", vac_color(vac, s))
        show(self.foot["u"], f"{m['u']:.1f}")
        show(self.foot["u_no"], f"{u_no:.1f}")
        t = datetime.now()
        self.clock.setText(t.strftime("%Y-%m-%d %H:%M:%S ") + DAYS[t.weekday()])

        # --- лампочки
        self.lamp_link.set("green" if res.connected else "blue")
        self.lamp_ready.set("green" if m["ready"] else "red")
        self.lamp_agc_u.set("green" if m["agc_u"] else "gray")
        self.lamp_agc_i.set("green" if m["agc_i"] else "gray")
        self.lamp_auto.set("green" if auto and not tr.paused else "red")

        # --- автоматика и ручное: активная группа - красная рамка, как было
        style.group(self.box_auto, "red" if auto else "gray", 5)
        style.group(self.box_manual, "gray" if auto else "red", 5)
        self.mode.setText("AUTO" if auto else "MANUAL")
        for b in (self.btn_start, self.btn_stop, self.btn_rev):
            b.setEnabled(auto)
        self.u_field.setEnabled(not auto)          # в AUTO напряжение ведёт алгоритм
        if auto:
            self.u_field.set_value(u_set)
        going_up = auto and tr.direction > 0
        going_down = auto and tr.direction < 0
        self.arrow_up.setPixmap(QtGui.QPixmap(icon("arrow_up_10.png" if going_up else "arrow_up_gray_10.png")))
        self.arrow_down.setPixmap(QtGui.QPixmap(icon("arrow_down_10.png" if going_down else "arrow_down_gray_10.png")))
        self.start_stop.setText(f"{tr.start:g} → {tr.stop:g} кВ")
        self.state_lbl.setText(("Пауза · " if auto and tr.paused else "") + STATE_TEXT[tr.state])
        if self.seq.currentText() != s.sequence:   # Reverse мог поменять UP <-> DOWN
            self.seq.blockSignals(True)
            self.seq.setCurrentText(s.sequence)
            self.seq.blockSignals(False)

        # --- запись в файл
        self.file.write(m, vac, u_set, res.read_current(), "AUTO" if auto else "MANUAL")

        # --- графики (ось X - реальное время)
        n = self.cfg["history_s"]
        self.t = (self.t + [time.time()])[-n:]
        self.u_hist = (self.u_hist + [m["u"]])[-n:]
        self.u_set_hist = (self.u_set_hist + [u_set])[-n:]
        self.vac_hist = (self.vac_hist + [vac])[-n:]
        k = self.cfg["vac_coeff"] if self.units.text() == "торр" else 1.0
        self.curve_u.setData(self.t, self.u_hist)
        self.curve_u_set.setData(self.t, self.u_set_hist)
        self.curve_vac.setData(self.t, [v * k for v in self.vac_hist])
        for attr, line in self.lines.items():
            line.setValue(math.log10(getattr(s, attr) * k))   # в лог-режиме ось = log10
        self.vac_u.add(u_set, vac, n)
