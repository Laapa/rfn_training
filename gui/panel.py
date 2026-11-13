"""Окно одного резонатора = вкладка «Главная» старой программы (у каждого резонатора своя).
Те же группы, те же рамки, лампочки, стрелки и тумблер - только сложено вертикально,
чтобы два окна помещались на одном мониторе:

    Графики (U и вакуум)
    Данные | Вакуум + Ручное управление | лампочки
    Автоматическое управление | тумблер AUTO/MANUAL
    часы, Новая сессия, Сброс, Вкл/Выкл МОД
"""
import dataclasses
import math
import os
import re
import time
from datetime import datetime

import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui

from gui import style
from gui.sound import fanfare
from gui.vac_u import VacAxis, VacUWindow
from gui.viewer import FileViewer
from gui.widgets import Lamp, Toggle, ArrowField, PrecisionSlider, value_box, MONO
from trainer import config as config_file
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
    box.setStyleSheet(f"color: {style.color(color)}" if color else "")


class ResonatorPanel(QtWidgets.QWidget):
    def __init__(self, name, trainer, config, item=None):
        """item - запись этого резонатора в training_config.json (туда сохраняются настройки окна)."""
        super().__init__()
        self.setWindowTitle(name)
        self.name = name
        self.tr = trainer
        self.tr.log = self.add_log
        self.cfg = config
        self.item = item if item is not None else {}
        self.now = 0
        self.u_text = "—"                  # последняя прочитанная уставка U (для «Обзора»)
        self.t, self.u_hist, self.u_set_hist, self.vac_hist = [], [], [], []
        folder = re.sub(r'[\\/:*?"<>|]', "_", name)     # имя папки без запрещённых в Windows символов
        self.file = DataFile(os.path.join(config["data_dir"], folder))
        self.vac_u = VacUWindow(name)
        s, res = trainer.s, trainer.res

        # ========================= Графики (главное - им всё свободное место) =========================
        self.plot_u = pg.PlotWidget(background=style.PLOT_BG, axisItems={"bottom": pg.DateAxisItem()})
        self.plot_u.setTitle("Voltage (kV)", color="y", size="10pt")
        self.plot_u.addLegend(offset=(10, 5))
        self.curve_u = self.plot_u.plot(pen=pg.mkPen((255, 0, 0)), name="U резонатора")
        self.curve_u_set = self.plot_u.plot(pen=pg.mkPen("y", style=QtCore.Qt.DashLine), name="уставка")
        self.plot_vac = pg.PlotWidget(background=style.PLOT_BG,
                                      axisItems={"bottom": pg.DateAxisItem(), "left": VacAxis("left")})
        self.plot_vac.setTitle("Vacuum (torr)", color="y", size="10pt")
        self.plot_vac.setLogMode(y=True)
        self.curve_vac = self.plot_vac.plot(pen=pg.mkPen((255, 0, 0)))
        self.lines = {}   # пороги пунктиром тех же цветов
        for attr, color in THRESHOLDS:
            self.lines[attr] = pg.InfiniteLine(angle=0, pen=pg.mkPen(style.color(color), width=2,
                                                                      style=QtCore.Qt.DashLine))
            self.plot_vac.addItem(self.lines[attr])
        for p in (self.plot_u, self.plot_vac):
            p.showGrid(x=True, y=True, alpha=0.2)
            p.setClipToView(True)
            p.setDownsampling(auto=True)
            p.setMinimumHeight(80)
        self.plot_vac.setXLink(self.plot_u)

        # над графиками: крупные I насоса / U / U НО (были внизу старой «Главной») и кнопки
        self.foot = {"pump": value_box(), "u": value_box(), "u_no": value_box()}
        top = QtWidgets.QHBoxLayout()
        for key, text, unit in (("pump", "I насоса", "A"), ("u", "U резонатора", "кВ"),
                                ("u_no", "U рез НО", "кВ")):
            top.addWidget(QtWidgets.QLabel(text))
            top.addWidget(self.foot[key])
            top.addWidget(QtWidgets.QLabel(unit))
            top.addSpacing(8)
        top.addStretch()
        self.units = QtWidgets.QPushButton("A")        # как в старой программе: A <-> торр
        self.units.setToolTip("Показывать вакуум в торрах или ток насоса в амперах")
        self.units.clicked.connect(self.on_units)
        btn_vu = QtWidgets.QPushButton("Вакуум от U ↗")
        btn_vu.clicked.connect(lambda: (self.vac_u.show(), self.vac_u.raise_()))
        top.addWidget(self.units)
        top.addWidget(btn_vu)
        box_plots = QtWidgets.QGroupBox("Графики")
        style.group(box_plots, "darkblue")
        lay = QtWidgets.QVBoxLayout(box_plots)
        lay.setSpacing(4)
        lay.addLayout(top)
        lay.addWidget(self.plot_u)
        lay.addWidget(self.plot_vac)

        # ========================= Данные (две колонки) =========================
        self.data = {}
        rows = (("u", "U резонатора", "кВ"), ("i", "I фидера", "A"), ("vac", "Вакуум", "Торр"),
                ("pump", "I насоса", "A"), ("p_fwd", "Падающая", "кВт"), ("p_ref", "Отраженная", "кВт"),
                ("u_no", "U резонатора НО", "кВ"))
        grid = QtWidgets.QGridLayout()
        for k, (key, text, unit) in enumerate(rows):
            r, c = k % 4, (k // 4) * 3
            self.data[key] = value_box()
            grid.addWidget(QtWidgets.QLabel(text), r, c)
            grid.addWidget(self.data[key], r, c + 1)
            grid.addWidget(QtWidgets.QLabel(unit), r, c + 2)
        grid.setColumnMinimumWidth(3, 0)
        box_data = QtWidgets.QGroupBox("Данные")
        style.group(box_data, "cyan")
        box_data.setLayout(grid)

        # ========================= Вакуум (пороги) =========================
        grid = QtWidgets.QGridLayout()
        self.thr = {}
        for r, (attr, color) in enumerate(THRESHOLDS):
            amps, torr = QtWidgets.QLineEdit(), QtWidgets.QLineEdit()
            for e in (amps, torr):
                e.setFixedWidth(80)
                e.setFont(MONO)
                e.setStyleSheet(f"color: {style.color(color)}")
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

        # ========================= Лампочки =========================
        self.lamp_ready, self.lamp_agc_u, self.lamp_agc_i = Lamp(), Lamp(), Lamp()
        lamps = QtWidgets.QGridLayout()
        for r, (lamp, text) in enumerate(((self.lamp_ready, "Готовность"),
                                          (self.lamp_agc_u, "АРУ: U"), (self.lamp_agc_i, "АРУ: I"))):
            lamps.addWidget(lamp, r, 0)
            lamps.addWidget(QtWidgets.QLabel(text), r, 1)

        # ========================= Автоматическое управление =========================
        self.slider_auto = PrecisionSlider(["0.1", "1", "10"], [(0.1, 1, 10)])
        self.seq = QtWidgets.QComboBox()
        self.seq.addItems([UP, DOWN, ZONE, SAW])
        self.seq.setCurrentText(s.sequence)
        self.seq.setFixedWidth(150)
        self.seq.currentTextChanged.connect(self.on_sequence)
        self.high = ArrowField(s.high, "кВ", lambda v: self.set_param("high", v), self.slider_auto.step)
        self.low = ArrowField(s.low, "кВ", lambda v: self.set_param("low", v), self.slider_auto.step)

        grid = QtWidgets.QGridLayout()
        grid.setVerticalSpacing(4)
        for r, (text, w) in enumerate((("Sequence", self.seq), ("U MAX", self.high), ("U MIN", self.low))):
            grid.addWidget(QtWidgets.QLabel(text), r, 0)
            grid.addWidget(w, r, 1)
        for r, (text, attr, unit) in enumerate((("Шаг", "step", "кВ"),
                                                 ("Response Delay", "response_delay", "с"),
                                                 ("Timeout", "timeout", "с"))):
            grid.addWidget(QtWidgets.QLabel(text), r, 2)
            grid.addWidget(self.enter_field(attr), r, 3)
            grid.addWidget(QtWidgets.QLabel(unit), r, 4)
        grid.addWidget(self.slider_auto, 0, 5, 3, 1)

        # нижняя строка: Start ● Stop Reverse | стрелки направления, Start → Stop, состояние
        self.btn_start = QtWidgets.QPushButton("Start")
        self.btn_stop = QtWidgets.QPushButton("Stop")
        self.btn_rev = QtWidgets.QPushButton("Reverse")
        self.lamp_auto = Lamp()
        self.btn_start.clicked.connect(lambda: self.tr.set_paused(False))
        self.btn_stop.clicked.connect(lambda: self.tr.set_paused(True))
        self.btn_rev.clicked.connect(self.tr.reverse)
        self.arrow_up, self.arrow_down = QtWidgets.QLabel("▲"), QtWidgets.QLabel("▼")   # направление
        self.state_lbl = QtWidgets.QLabel()
        self.state_lbl.setWordWrap(True)          # длинный текст переносится, а не распирает группу
        self.state_lbl.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        bottom = QtWidgets.QHBoxLayout()
        for w in (self.btn_start, self.lamp_auto, self.btn_stop, self.btn_rev):
            bottom.addWidget(w)
        bottom.addSpacing(10)
        bottom.addWidget(self.arrow_up)
        bottom.addWidget(self.arrow_down)
        bottom.addWidget(self.state_lbl, stretch=1)

        self.box_auto = QtWidgets.QGroupBox("Автоматическое управление")
        style.group(self.box_auto, "gray")
        self.shown_auto = False                       # какой режим сейчас нарисован (рамки)
        auto_lay = QtWidgets.QVBoxLayout(self.box_auto)
        auto_lay.setSpacing(4)
        auto_lay.addLayout(grid)
        auto_lay.addLayout(bottom)

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
        style.group(self.box_manual, "red", True)     # MANUAL - активна, красная рамка
        self.box_manual.setLayout(grid)

        # ========================= Тумблер AUTO / MANUAL =========================
        self.toggle = Toggle()
        self.toggle.clicked.connect(self.on_auto)      # clicked - только от пользователя
        self.mode = QtWidgets.QLabel("MANUAL")
        self.mode.setAlignment(QtCore.Qt.AlignCenter)
        self.mode.setStyleSheet("font-weight: bold; font-size: 11pt")
        # лампочки и под ними тумблер - одной колонкой справа от «Вакуума»
        side = QtWidgets.QVBoxLayout()
        side.addLayout(lamps)
        side.addWidget(self.toggle, alignment=QtCore.Qt.AlignCenter)
        side.addWidget(self.mode)
        side.addStretch()

        # ========================= Две плотные строки управления =========================
        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(box_data)
        row1.addWidget(box_vac)
        row1.addLayout(side)
        row1.addStretch(1)
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(self.box_auto)
        row2.addWidget(self.box_manual)
        row2.addStretch(1)
        controls = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(controls)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addLayout(row1)
        lay.addLayout(row2)
        self.controls = controls
        scroll = QtWidgets.QScrollArea()          # на маленьком экране - прокрутка
        scroll.setWidget(controls)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll = scroll                       # высоту подгоняет fit_controls()

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)   # границу можно тянуть мышью
        self.splitter.addWidget(box_plots)
        self.splitter.addWidget(scroll)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        # ========================= Нижняя строка =========================
        self.clock = QtWidgets.QLineEdit()
        self.clock.setReadOnly(True)
        self.clock.setFont(QtGui.QFont("Consolas", 11))
        self.clock.setFixedWidth(self.clock.fontMetrics().horizontalAdvance(
            "2026-11-13 00:00:00 воскресенье") + 20)
        new_session = QtWidgets.QPushButton("Новая сессия")
        new_session.clicked.connect(self.on_new_session)
        view_btn = QtWidgets.QPushButton("Открыть запись…")       # посмотреть сохранённые .dat
        view_btn.clicked.connect(self.on_view)
        foot = QtWidgets.QHBoxLayout()
        foot.addWidget(self.clock)
        foot.addWidget(new_session)
        foot.addWidget(view_btn)
        foot.addStretch(1)
        for text, command in (("Сброс", res.reset_all),          # RstAll - сброс всех блокировок
                              ("Вкл МОД", res.mod_on), ("Выкл МОД", res.mod_off)):
            b = QtWidgets.QPushButton(text)
            b.clicked.connect(lambda _, t=text, c=command: self.command(t, c))
            foot.addWidget(b)

        self.status = QtWidgets.QLabel()          # строка внизу: запись в файл и сообщения
        self.status.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(8, 6, 8, 4)
        main.setSpacing(4)
        main.addWidget(self.splitter, stretch=1)
        main.addLayout(foot)
        main.addWidget(self.status)
        self.file_msg = f"Начата запись в файл {self.short_name()}"
        self.status.setText(self.file_msg)

    def fit_controls(self):
        """Графики в приоритете: поля управления занимают не больше 45% высоты окна.
        Если им этого мало (маленькое окно) - появляется прокрутка."""
        need = min(self.controls.sizeHint().height() + 4, int(self.height() * 0.45))
        if self.scroll.minimumHeight() != need:
            self.scroll.setMinimumHeight(need)
            total = sum(self.splitter.sizes())
            self.splitter.setSizes([total - need, need])   # всё остальное - графикам

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_controls()

    # ------------------------------------------------------------------ обработчики

    def add_log(self, msg):
        self.status.setText(f"{self.file_msg}    |    {time.strftime('%H:%M:%S')}  {msg}")
        self.file.log(msg)                         # вся история - в журнал рядом с .dat

    def short_name(self):
        """Имя файла данных для строки статуса: папка резонатора / файл (без длинного пути)."""
        folder, name = os.path.split(self.file.name)
        return os.path.join(os.path.basename(folder), name)

    def save_settings(self):
        """Настройки окна (Low, High, Step, пороги...) - в training_config.json, чтобы пережить перезапуск."""
        s = dataclasses.asdict(self.tr.s)
        s.pop("u_limit")                           # предел берётся из общего config
        self.item["settings"] = s
        try:
            config_file.save(self.cfg)
        except OSError as e:
            self.add_log(f"Не удалось сохранить настройки: {e}")

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
        self.save_settings()
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
        self.save_settings()

    def on_manual_u(self, value):
        if self.tr.state != MANUAL or value > self.tr.s.u_limit:
            return False
        self.tr.res.set_voltage(value)
        self.add_log(f"Вручную: U = {value:.2f} кВ")

    def on_manual_i(self, value):
        if value > self.cfg["i_max_a"]:
            return False
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
        self.file_msg = f"Начата запись в файл {self.short_name()}"
        self.status.setText(self.file_msg)

    def on_view(self):
        """Окно просмотра: сразу открываем текущую запись, другую можно выбрать кнопкой."""
        self.viewer = FileViewer(os.path.dirname(self.file.name))
        self.viewer.open_file(self.file.name)
        self.viewer.show()

    def command(self, text, func):
        try:
            func()
            self.add_log(f"Команда: {text}")
        except Exception as e:
            self.add_log(f"Команда {text} не прошла: {e}")

    # ------------------------------------------------------------------ раз в тик

    def update_view(self, now):
        """Вызывается главным окном после каждого tick()."""
        self.now = now
        tr, s, res = self.tr, self.tr.s, self.tr.res
        try:
            m = res.read_measurements()
            u_set = res.read_setpoint()
        except Exception as e:                     # нет связи: гасим лампочки, ничего не пишем
            for lamp in (self.lamp_ready, self.lamp_agc_u, self.lamp_agc_i):
                lamp.set("gray")
            for box in list(self.data.values()) + list(self.foot.values()):
                show(box, "—")
            self.add_log(f"Нет связи с устройством: {e}")
            self.u_text = "нет связи"
            return
        self.u_text = f"{u_set:.2f}"
        vac = tr.vacuum
        auto = tr.state != MANUAL
        u_no = u_from_power(m["p_fwd"], m["p_ref"], self.cfg["r_sh"])

        if not auto and self.toggle.isChecked():   # программа сама сняла тумблер (дошли до Stop)
            self.toggle.setChecked(False)
            if tr.finished:
                fanfare(self.cfg["data_dir"])       # дошли до Stop - фанфары (README, п.5)
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
        show(d["u_no"], f"{u_no:.1f}")
        show(self.foot["pump"], f"{m['pump_a']:.1e}", vac_color(vac, s))
        show(self.foot["u"], f"{m['u']:.1f}")
        show(self.foot["u_no"], f"{u_no:.1f}")
        t = datetime.now()
        self.clock.setText(t.strftime("%Y-%m-%d %H:%M:%S ") + DAYS[t.weekday()])

        # --- лампочки
        self.lamp_ready.set("green" if m["ready"] else "red")
        self.lamp_agc_u.set("green" if m["agc_u"] else "gray")
        self.lamp_agc_i.set("green" if m["agc_i"] else "gray")
        self.lamp_auto.set("green" if auto and not (tr.paused or tr.not_ready) else "red")

        # --- автоматика и ручное: активная группа - красная рамка, как было
        if auto != self.shown_auto:               # перекрашиваем рамки только при смене режима
            style.group(self.box_auto, "red" if auto else "gray", auto)
            style.group(self.box_manual, "gray" if auto else "red", not auto)
            self.shown_auto = auto
        self.mode.setText("AUTO" if auto else "MANUAL")
        for b in (self.btn_start, self.btn_stop, self.btn_rev):
            b.setEnabled(auto)
        self.u_field.setEnabled(not auto)          # в AUTO напряжение ведёт алгоритм
        current = res.read_current()
        # поля уставок показывают то, что реально стоит в устройстве (пока в них не печатают)
        if not self.u_field.edit.hasFocus():
            self.u_field.set_value(u_set)
        if not self.i_field.edit.hasFocus():
            self.i_field.set_value(current)
        going_up = auto and tr.direction > 0
        going_down = auto and tr.direction < 0
        for arrow, on in ((self.arrow_up, going_up), (self.arrow_down, going_down)):
            arrow.setStyleSheet(f"font-size: 14pt; color: {style.C['green'] if on else style.C['gray']}")
        self.state_lbl.setText(f"{tr.start:g} → {tr.stop:g} кВ · "
                               + ("Пауза · " if auto and tr.paused else "")
                               + ("Нет готовности, ждём · " if auto and tr.not_ready else "")
                               + STATE_TEXT[tr.state])
        if self.seq.currentText() != s.sequence:   # Reverse мог поменять UP <-> DOWN
            self.seq.blockSignals(True)
            self.seq.setCurrentText(s.sequence)
            self.seq.blockSignals(False)

        self.fit_controls()

        # --- запись в файл
        self.file.write(m, vac, u_set, current, "AUTO" if auto else "MANUAL")

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
