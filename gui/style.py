"""Оформление. Раскладка и цвета групп - как в старой программе, вид - современный:
плоские карточки, скруглённые поля и кнопки. Светлая тема по умолчанию, тёмная - по галке.
Цвета берутся из палитры (palette(...)), поэтому одна и та же разметка работает в обеих темах."""
from PyQt5 import QtGui

# Цвета групп и сигналов - те же, что в старой программе, только в современных оттенках
C = {
    "green": "#16a34a", "red": "#dc2626", "orange": "#f59e0b", "magenta": "#c026d3",
    "cyan": "#0891b2", "blue": "#2563eb", "darkblue": "#1e40af", "gray": "#9ca3af",
    "accent": "#2563eb",
}
LAMP = {"green": "#22c55e", "red": "#ef4444", "gray": "#9ca3af", "blue": "#3b82f6"}
PLOT_BG = "#0b1220"     # графики остаются тёмными, как были (чёрный фон, жёлтые заголовки)

THEMES = {   # окно, карточки, поля только-для-чтения, текст, кнопки, рамки
    False: dict(window="#f1f3f6", base="#ffffff", alt="#f3f4f6", text="#111827",
                button="#ffffff", mid="#d1d5db", muted="#6b7280"),
    True: dict(window="#0f141b", base="#18202b", alt="#111821", text="#e5e7eb",
               button="#222c3a", mid="#374151", muted="#9ca3af"),
}

QSS = """
QPushButton { background: palette(button); border: 1px solid palette(mid); border-radius: 8px;
              padding: 5px 14px; }
QPushButton:hover { border-color: %(accent)s; }
QPushButton:pressed { background: %(accent)s; color: white; }
QPushButton:disabled { color: palette(mid); }
QLineEdit, QComboBox { background: palette(base); border: 1px solid palette(mid); border-radius: 6px;
                       padding: 3px 6px; selection-background-color: %(accent)s; }
QLineEdit:focus, QComboBox:focus { border: 1px solid %(accent)s; }
QLineEdit[readOnly="true"] { background: palette(alternate-base); border: 1px solid transparent; }
QLineEdit:disabled { color: palette(mid); }
QComboBox::drop-down { border: none; width: 22px; }
QSlider::groove:vertical { width: 4px; background: palette(mid); border-radius: 2px; }
QSlider::handle:vertical { background: %(accent)s; height: 16px; margin: 0 -6px; border-radius: 8px; }
QTableWidget { background: palette(base); border: 1px solid palette(mid); border-radius: 10px;
               gridline-color: palette(alternate-base); }
QHeaderView::section { background: palette(base); border: none; border-bottom: 1px solid palette(mid);
                       padding: 6px; font-weight: 600; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QSplitter::handle { background: transparent; }
""" % C


def group(box, color, active=False):
    """Группа-карточка: цветная рамка и цветная плашка с названием (цвет - как в старой программе)."""
    c = C[color]
    box.setStyleSheet(
        f"QGroupBox {{ background: palette(base); border: {3 if active else 2}px solid {c};"
        " border-radius: 12px; margin-top: 10px; padding: 10px 6px 4px 6px; }"
        f"QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 2px 10px;"
        f" background: {c}; color: white; border-radius: 6px; font-weight: 600; }}")


def apply_theme(app, dark):
    """Включить тему. Можно вызывать на ходу - все окна перерисуются."""
    t = THEMES[bool(dark)]
    pal = QtGui.QPalette()
    for role, key in ((QtGui.QPalette.Window, "window"), (QtGui.QPalette.Base, "base"),
                      (QtGui.QPalette.AlternateBase, "alt"), (QtGui.QPalette.Button, "button"),
                      (QtGui.QPalette.Mid, "mid"), (QtGui.QPalette.WindowText, "text"),
                      (QtGui.QPalette.Text, "text"), (QtGui.QPalette.ButtonText, "text")):
        pal.setColor(role, QtGui.QColor(t[key]))
    pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor(C["accent"]))
    pal.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text, QtGui.QColor(t["muted"]))
    pal.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, QtGui.QColor(t["muted"]))
    app.setStyle("Fusion")
    app.setFont(QtGui.QFont("Segoe UI", 10))
    app.setPalette(pal)
    app.setStyleSheet(QSS)
    for w in app.allWidgets():                 # перечитать стили с palette(...) у уже открытых окон
        if w.styleSheet():
            w.setStyleSheet(w.styleSheet())


def color(name):
    """Цвет по имени из старой программы ("green", "red", ...); "" - обычный цвет текста."""
    return C.get(name, name)
