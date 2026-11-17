"""Окно одного резонатора (раскладка по эскизу научного руководителя):

    лампы: Вкл · RDY · АРУ U · АРУ I · Авария                    кнопки: Вкл · Выкл · Сброс
    значения: Ucav (+ уставка U) · Iфид (+ уставка I) · Pпад · Pотр · Vac
    «Тренировка»: Umax, Umin, dU, dt, Timeout | «Вакуум»: Vac2, Vac1, Vac0, AUTO/MANUAL, Start/Stop/Reverse | «Метод»
    графики: Ucav(t) и Vac(t), кнопка V(U) - вакуум от напряжения в отдельном окне
    строка состояния: что делает автомат, последнее сообщение, часы

Значения и лампы с устройства показывают виджеты Taurus (gui/views.py), только для чтения.
Уставки и команды - через нашу логику, чтобы в AUTO никто не крутил U в обход автомата.
"""
import dataclasses
import math
import os
import re
import time
from datetime import datetime

import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore

from gui import style
from gui.sound import fanfare
from gui.vac_u import VacAxis, VacUWindow
from gui import views
from gui.views import ValueView, LedView, command_button
from gui.widgets import Lamp, Toggle, StepField, method_icon
from trainer import config as config_file
from trainer.core import UP, DOWN, ZONE, SAW, MANUAL
from trainer.datafile import DataFile

STATE_TEXT = {
    "MANUAL": "Ручной режим",
    "WAIT_GOOD": "Ждём Good",
    "DELAY": "Отсчёт dt",
    "BACKOFF": "Отступили, ждём Good / Timeout",
}
DAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
METHODS = ((UP, "up", "Вверх"), (DOWN, "down", "Вниз"),
           (ZONE, "zone", "Zone (туда-обратно)"), (SAW, "saw", "Пила"))
# пороги вакуума: Vac2 - отказ (Very Bad), Vac1 - стоп (Bad), Vac0 - можно шагать (Good)
THRESHOLDS = (("very_bad", "Vac2", "отказ", "orange"), ("bad", "Vac1", "стоп", "red"),
              ("good", "Vac0", "Good", "green"))


def vac_color(vac, s):
    """Цвет значения вакуума ("" - обычный цвет текста)."""
    if vac >= s.very_bad:
        return style.color("magenta")
    if vac >= s.bad:
        return style.color("red")
    if vac <= s.good:
        return style.color("green")
    return ""


def group_box(title, color, layout):
    box = QtWidgets.QGroupBox(title)
    style.group(box, color)
    box.setLayout(layout)
    return box


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
        self.shown_auto = None             # какой режим сейчас нарисован (рамки)
        self.link_ok = True                # была ли связь в прошлый тик (пишем в журнал только перемены)
        self.t, self.u_hist, self.u_set_hist, self.vac_hist = [], [], [], []
        folder = re.sub(r'[\\/:*?"<>|]', "_", name)     # имя папки без запрещённых в Windows символов
        self.file = DataFile(os.path.join(config["data_dir"], folder))
        self.vac_u = VacUWindow(name)
        s, res = trainer.s, trainer.res

        # ========== Лампы и команды ==========
        top = QtWidgets.QHBoxLayout()
        self.leds = {}
        for key, text, attr in (("on", "Вкл", "State"), ("rdy", "RDY", "ModSt"),
                                ("agc_u", "АРУ U", "ModU"), ("agc_i", "АРУ I", "ModI")):
            self.leds[key] = LedView(res, "mod", attr)
            top.addWidget(self.leds[key])
            top.addWidget(QtWidgets.QLabel(text))
            top.addSpacing(10)
        self.alarm = Lamp()             # «Авария» считаем сами: блокировка, нет связи, ошибка автомата
        self.alarm.setToolTip("Авария не горит")
        top.addWidget(self.alarm)
        alarm_lbl = QtWidgets.QLabel("Авария")
        alarm_lbl.setStyleSheet("font-weight: bold")
        top.addWidget(alarm_lbl)
        top.addStretch()
        for text, cmd, func in (("Вкл", "ModOn", res.mod_on), ("Выкл", "ModOff", res.mod_off),
                                ("Сброс", "RstAll", res.reset_all)):
            b = command_button(res, text, cmd, func, self.add_log)
            if cmd == "RstAll":         # «Сброс» гасит и нашу память об ошибке автомата
                b.clicked.connect(lambda: setattr(self.tr, "error", ""))
            top.addWidget(b)

        # ========== Значения (+ уставки U и I под ними) ==========
        self.values = {}
        vals = QtWidgets.QGridLayout()
        vals.setHorizontalSpacing(14)
        for col, (key, text, dev, attr, fmt) in enumerate((
                ("u", "Ucav, кВ", "mod", "Ucav", "{:.2f}"), ("i", "Iфид, А", "mod", "Ifid", "{:.2f}"),
                ("p_fwd", "Pпад, кВт", "sspa", "SspaPforw", "{:.2f}"),
                ("p_ref", "Pотр, кВт", "sspa", "SspaPrefl", "{:.2f}"),
                ("vac", "Vac, Торр", "cav", "Vac", "{:.1e}"))):
            self.values[key] = ValueView(res, dev, attr, fmt)
            vals.addWidget(QtWidgets.QLabel(text), 0, col)
            vals.addWidget(self.values[key], 1, col)
        try:                                        # нет связи при запуске - не страшно, окно всё равно откроется
            u0, i0 = res.read_setpoint(), res.read_current()
        except Exception:
            u0 = i0 = 0.0                           # настоящие значения подставит первый же тик со связью
        self.u_field = StepField(u0, "", self.on_manual_u, step=0.5, fmt="{:.2f}")
        self.i_field = StepField(i0, "", self.on_manual_i, step=0.1, fmt="{:.2f}")
        self.u_field.setToolTip("Уставка U резонатора (ручной режим)")
        self.i_field.setToolTip("Уставка тока фидера - и в ручном, и в AUTO")
        vals.addWidget(QtWidgets.QLabel("уставка U"), 2, 0)
        vals.addWidget(self.u_field, 3, 0)
        vals.addWidget(QtWidgets.QLabel("уставка I"), 2, 1)
        vals.addWidget(self.i_field, 3, 1)
        vals.setColumnStretch(5, 1)                 # лишнее место - справа, а не между значениями
        box_vals = group_box("Значения", "cyan", vals)

        # ========== Тренировка: Umax, Umin, dU, dt, Timeout ==========
        grid = QtWidgets.QGridLayout()
        self.fields = {}
        for r, (attr, text, unit, step, fmt) in enumerate((
                ("high", "Umax", "кВ", 0.5, "{:.2f}"), ("low", "Umin", "кВ", 0.5, "{:.2f}"),
                ("step", "dU (шаг)", "кВ", 0.1, "{:.2f}"), ("response_delay", "dt", "с", 1, "{:g}"),
                ("timeout", "Timeout", "с", 1, "{:g}"))):
            self.fields[attr] = StepField(getattr(s, attr), unit,
                                          lambda v, a=attr: self.set_param(a, v), step=step, fmt=fmt)
            grid.addWidget(QtWidgets.QLabel(text), r, 0)
            grid.addWidget(self.fields[attr], r, 1)
        self.fields["response_delay"].setToolTip("Response Delay: пауза перед шагом при хорошем вакууме")
        self.fields["timeout"].setToolTip("Timeout: сколько ждать Good после отступа, прежде чем отступить ещё")
        self.box_train = group_box("Тренировка", "gray", grid)

        # ========== Вакуум: Vac2, Vac1, Vac0 + тумблер AUTO/MANUAL ==========
        grid = QtWidgets.QGridLayout()
        for r, (attr, text, hint, color) in enumerate(THRESHOLDS):
            label = QtWidgets.QLabel(f"{text} <span style='color:gray'>({hint})</span>")
            self.fields[attr] = StepField(getattr(s, attr), "Торр", lambda v, a=attr: self.set_param(a, v),
                                          fmt="{:.1e}", log_step=True)
            self.fields[attr].edit.setStyleSheet(f"color: {style.color(color)}")
            grid.addWidget(label, r, 0)
            grid.addWidget(self.fields[attr], r, 1)
        self.toggle = Toggle()
        self.toggle.clicked.connect(self.on_auto)          # clicked - только от пользователя
        self.mode = QtWidgets.QLabel("MANUAL")
        self.mode.setStyleSheet("font-weight: bold; font-size: 12pt")
        self.lamp_auto = Lamp()
        self.btn_start = QtWidgets.QPushButton("Start")
        self.btn_stop = QtWidgets.QPushButton("Stop")
        self.btn_rev = QtWidgets.QPushButton("Reverse")
        self.btn_start.clicked.connect(lambda: self.tr.set_paused(False))
        self.btn_stop.clicked.connect(lambda: self.tr.set_paused(True))
        self.btn_rev.clicked.connect(self.tr.reverse)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.toggle)
        row.addWidget(self.mode)
        row.addStretch()
        grid.addLayout(row, 3, 0, 1, 2)
        row = QtWidgets.QHBoxLayout()
        for w in (self.lamp_auto, self.btn_start, self.btn_stop, self.btn_rev):
            row.addWidget(w)
        grid.addLayout(row, 4, 0, 1, 2)
        box_vac = group_box("Вакуум", "green", grid)

        # ========== Метод: один из списка ==========
        lay = QtWidgets.QVBoxLayout()
        self.methods = QtWidgets.QButtonGroup(self)
        self.method_buttons = {}
        for seq, icon, text in METHODS:
            b = QtWidgets.QRadioButton(text)
            b.setIcon(method_icon(icon))
            b.setIconSize(QtCore.QSize(44, 20))
            b.setChecked(s.sequence == seq)
            b.toggled.connect(lambda on, q=seq: on and self.on_sequence(q))
            self.methods.addButton(b)
            self.method_buttons[seq] = b
            lay.addWidget(b)
        lay.addStretch()
        box_method = group_box("Метод", "darkblue", lay)

        controls = QtWidgets.QHBoxLayout()
        for box in (self.box_train, box_vac, box_method):
            controls.addWidget(box, alignment=QtCore.Qt.AlignTop)
        controls.addStretch(1)

        # ========== Графики ==========
        self.plot_u = pg.PlotWidget(background=style.PLOT_BG, axisItems={"bottom": pg.DateAxisItem()})
        self.plot_u.setTitle("Ucav (kV)", color="y", size="10pt")
        self.plot_u.addLegend(offset=(10, 5))
        self.curve_u = self.plot_u.plot(pen=pg.mkPen((255, 0, 0)), name="Ucav")
        self.curve_u_set = self.plot_u.plot(pen=pg.mkPen("y", style=QtCore.Qt.DashLine), name="уставка")
        self.plot_vac = pg.PlotWidget(background=style.PLOT_BG,
                                      axisItems={"bottom": pg.DateAxisItem(), "left": VacAxis("left")})
        self.plot_vac.setTitle("Vac (torr)", color="y", size="10pt")
        self.plot_vac.setLogMode(y=True)
        self.curve_vac = self.plot_vac.plot(pen=pg.mkPen((255, 0, 0)))
        self.lines = {}   # пороги пунктиром тех же цветов
        for attr, _, _, color in THRESHOLDS:
            self.lines[attr] = pg.InfiniteLine(angle=0, pen=pg.mkPen(style.color(color), width=2,
                                                                      style=QtCore.Qt.DashLine))
            self.plot_vac.addItem(self.lines[attr])
        for p in (self.plot_u, self.plot_vac):
            p.showGrid(x=True, y=True, alpha=0.2)
            p.setClipToView(True)
            p.setDownsampling(auto=True)
            p.setMinimumHeight(100)
        self.plot_vac.setXLink(self.plot_u)
        btn_vu = QtWidgets.QPushButton("V(U) ↗")
        btn_vu.setToolTip("Вакуум от напряжения - в отдельном окне")
        btn_vu.clicked.connect(lambda: (self.vac_u.show(), self.vac_u.raise_()))
        plots = QtWidgets.QVBoxLayout()
        head = QtWidgets.QHBoxLayout()
        head.addWidget(btn_vu)
        head.addStretch()
        plots.addLayout(head)
        plots.addWidget(self.plot_u, stretch=1)
        plots.addWidget(self.plot_vac, stretch=1)
        box_plots = group_box("Графики", "darkblue", plots)

        # ========== Строка состояния ==========
        self.state_lbl = QtWidgets.QLabel()
        self.state_lbl.setStyleSheet("font-weight: bold")
        self.msg = QtWidgets.QLabel()
        self.msg.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.clock = QtWidgets.QLabel()
        self.clock.setStyleSheet("font-family: Consolas; font-size: 11pt")
        status = QtWidgets.QHBoxLayout()
        status.addWidget(self.state_lbl)
        status.addSpacing(12)
        status.addWidget(self.msg, stretch=1)
        status.addWidget(self.clock)

        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(8, 6, 8, 4)
        main.setSpacing(6)
        main.addLayout(top)
        main.addWidget(box_vals)
        main.addLayout(controls)
        main.addWidget(box_plots, stretch=1)      # всё свободное место - графикам
        main.addLayout(status)
        self.add_log(f"Запись в файл {self.short_name()}")
        if hasattr(res, "model") and not views.TAURUS:
            self.add_log("Taurus не установлен - значения без Taurus (pip install -r requirements.txt)")

    # ------------------------------------------------------------------ обработчики

    def add_log(self, msg):
        self.msg.setText(f"{time.strftime('%H:%M:%S')}  {msg}")
        self.file.log(msg)                         # вся история - в журнал рядом с .dat

    def short_name(self):
        """Имя файла данных: папка резонатора / файл (без длинного пути)."""
        folder, name = os.path.split(self.file.name)
        return os.path.join(os.path.basename(folder), name)

    def save_settings(self):
        """Настройки окна (Umax, Umin, пороги...) - в training_config.json, чтобы пережить перезапуск."""
        s = dataclasses.asdict(self.tr.s)
        s.pop("u_limit")                           # предел берётся из общего config
        self.item["settings"] = s
        try:
            config_file.save(self.cfg)
        except OSError as e:
            self.add_log(f"Не удалось сохранить настройки: {e}")

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

    def on_auto(self, checked):
        if checked:
            if not self.tr.enable(self.now):
                self.toggle.setChecked(False)
        else:
            self.tr.disable()

    def on_sequence(self, seq):
        if self.tr.s.sequence != seq:
            self.tr.set_sequence(seq)               # направление - сразу
            self.add_log(f"Метод: {seq}")
            self.save_settings()

    def on_manual_u(self, value):
        if self.tr.state != MANUAL or value > self.tr.s.u_limit:
            return False
        try:
            self.tr.res.set_voltage(value)
        except Exception as e:
            self.add_log(f"Уставка U не записалась: {e}")
            return False
        self.add_log(f"Вручную: U = {value:.2f} кВ")

    def on_manual_i(self, value):
        if value > self.cfg["i_max_a"]:
            return False
        try:
            self.tr.res.set_current(value)          # ток фидера - и в ручном, и в AUTO
        except Exception as e:
            self.add_log(f"Уставка I не записалась: {e}")
            return False
        self.add_log(f"I фидера = {value:.2f} А")

    # ------------------------------------------------------------------ раз в тик

    def update_view(self, now):
        """Вызывается главным окном после каждого tick()."""
        self.now = now
        tr, s, res = self.tr, self.tr.s, self.tr.res
        auto = tr.state != MANUAL
        t = datetime.now()
        self.clock.setText(t.strftime("%Y-%m-%d %H:%M:%S ") + DAYS[t.weekday()])
        self.show_mode(auto)
        if not auto and self.toggle.isChecked():   # программа сама сняла тумблер (Stop или обрыв связи)
            self.toggle.setChecked(False)
            if tr.finished:
                fanfare(self.cfg["data_dir"])       # дошли до Stop - фанфары (README, п.5)

        try:
            m = res.read_measurements()
            u_set = res.read_setpoint()
            current = res.read_current()
        except Exception as e:                     # нет связи: авария, прочерки, в файл не пишем
            self.set_alarm(f"Нет связи с устройством: {e}")
            for v in self.values.values():
                v.set("—")
            if self.link_ok:                       # в журнал - только момент обрыва, не каждую секунду
                self.add_log(f"Нет связи с устройством: {e}")
                self.link_ok = False
            self.u_text = "нет связи"
            return
        if not self.link_ok:
            self.add_log("Связь с устройством восстановлена")
            self.link_ok = True
        self.u_text = f"{u_set:.2f}"
        vac = tr.vacuum
        if not auto:
            tr.sync_direction(u_set)               # чтобы Start/Stop показывали правду

        # --- значения (у симулятора; Taurus обновляет себя сам) и цвета
        v = self.values
        v["u"].set(f"{m['u']:.2f}")
        v["i"].set(f"{m['i']:.2f}")
        v["p_fwd"].set(f"{m['p_fwd']:.2f}")
        v["p_ref"].set(f"{m['p_ref']:.2f}")
        v["vac"].set(f"{vac:.1e}")
        v["vac"].color(vac_color(vac, s))
        v["p_ref"].color(style.color("red") if m["p_ref"] > self.cfg["u_otr_max"] else "")

        # --- лампы (у симулятора; Taurus-лампы обновляются сами). «Авария» - всегда наша
        self.leds["on"].set("green" if m["rf_on"] else "gray")
        self.leds["rdy"].set("green" if m["ready"] else "red")
        self.leds["agc_u"].set("green" if m["agc_u"] else "gray")
        self.leds["agc_i"].set("green" if m["agc_i"] else "gray")
        self.set_alarm("Сработала блокировка (State FAULT/ALARM)" if m["fault"] else tr.error)

        # --- поля уставок показывают то, что реально стоит в устройстве (пока в них не печатают)
        if not self.u_field.edit.hasFocus():
            self.u_field.set_value(u_set)
        if not self.i_field.edit.hasFocus():
            self.i_field.set_value(current)
        b = self.method_buttons.get(s.sequence)    # Reverse мог поменять UP <-> DOWN
        if b and not b.isChecked():
            b.blockSignals(True)
            b.setChecked(True)
            b.blockSignals(False)
        self.state_lbl.setText(("▲ " if tr.direction > 0 else "▼ ") + f"{tr.start:g} → {tr.stop:g} кВ · "
                               + ("Пауза · " if auto and tr.paused else "")
                               + ("Нет готовности, ждём · " if auto and tr.not_ready else "")
                               + STATE_TEXT[tr.state])

        # --- запись в файл
        self.file.write(m, vac, u_set, current, "AUTO" if auto else "MANUAL")

        # --- графики (ось X - реальное время)
        n = self.cfg["history_s"]
        self.t = (self.t + [time.time()])[-n:]
        self.u_hist = (self.u_hist + [m["u"]])[-n:]
        self.u_set_hist = (self.u_set_hist + [u_set])[-n:]
        self.vac_hist = (self.vac_hist + [vac])[-n:]
        self.curve_u.setData(self.t, self.u_hist)
        self.curve_u_set.setData(self.t, self.u_set_hist)
        self.curve_vac.setData(self.t, self.vac_hist)
        for attr, line in self.lines.items():
            line.setValue(math.log10(getattr(s, attr)))   # в лог-режиме ось = log10
        self.vac_u.add(u_set, vac, n)

    def set_alarm(self, reason):
        """Лампа «Авария»: горит, если есть причина (блокировка, нет связи, автомат сам вышел из AUTO
        из-за ошибки). Причина - во всплывающей подсказке. Ошибку автомата гасит «Сброс» или новый AUTO."""
        self.alarm.set("red" if reason else "gray")
        self.alarm.setToolTip(reason or "Авария не горит")

    def show_mode(self, auto):
        """AUTO: рамка «Тренировки» красная, уставка U заблокирована, работают Start/Stop/Reverse."""
        tr = self.tr
        self.lamp_auto.set("green" if auto and not (tr.paused or tr.not_ready) else "red")
        if auto == self.shown_auto:
            return
        self.shown_auto = auto
        style.group(self.box_train, "red" if auto else "gray", auto)
        self.mode.setText("AUTO" if auto else "MANUAL")
        for b in (self.btn_start, self.btn_stop, self.btn_rev):
            b.setEnabled(auto)
        self.u_field.setEnabled(not auto)          # в AUTO напряжение ведёт алгоритм
