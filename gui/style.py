"""Оформление: тёмная тема. Все цвета - здесь, чтобы менять в одном месте."""
import pyqtgraph as pg

BG = "#0d1117"        # фон окна
CARD = "#161b22"      # фон карточек и графиков
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"     # подписи
ACCENT = "#2f81f7"    # синий акцент
GREEN = "#3fb950"
ORANGE = "#d29922"
RED = "#f85149"
MAGENTA = "#db61a2"
GRAY = "#484f58"      # выключенная лампочка
YELLOW = "#e3b341"
MONO = "Consolas"     # шрифт для чисел

QSS = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-family: "Segoe UI"; font-size: 10pt; }}
QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#card QWidget {{ background: transparent; }}
QLabel#cardTitle {{ color: {MUTED}; font-size: 9pt; font-weight: 600;
                    text-transform: uppercase; letter-spacing: 1px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#tileValue {{ font-family: {MONO}; font-size: 15pt; font-weight: 600; }}
QLabel#bigTitle {{ font-size: 15pt; font-weight: 700; }}
QLabel#clock {{ font-family: {MONO}; font-size: 12pt; color: {MUTED}; }}

QLineEdit, QDoubleSpinBox, QComboBox {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 4px 6px; font-family: {MONO}; font-size: 11pt; min-height: 22px; }}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QLineEdit:disabled, QDoubleSpinBox:disabled {{ color: {GRAY}; }}
QComboBox QAbstractItemView {{ background: {CARD}; selection-background-color: {ACCENT}; }}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 22px; }}

QPushButton {{ background: #21262d; border: 1px solid {BORDER}; border-radius: 6px;
               padding: 6px 12px; font-weight: 600; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {ACCENT}; }}
QPushButton:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QPushButton:disabled {{ color: {GRAY}; }}
QPushButton#segment {{ padding: 4px 8px; border-radius: 0px; }}
QPushButton#danger:hover {{ border-color: {RED}; color: {RED}; }}

QTableWidget {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px;
                gridline-color: {BORDER}; font-family: {MONO}; font-size: 11pt; }}
QHeaderView::section {{ background: {CARD}; color: {MUTED}; border: none;
                        border-bottom: 1px solid {BORDER}; padding: 6px; font-weight: 600; }}
QTableWidget::item:selected {{ background: #1f2a3a; }}
QTableWidget::indicator {{ width: 16px; height: 16px; border: 1px solid {MUTED}; border-radius: 4px; }}
QTableWidget::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QSplitter::handle {{ background: {BG}; height: 6px; }}
QScrollArea {{ border: none; }}
QStatusBar {{ color: {MUTED}; }}
"""


def setup(app):
    """Включить тему для всего приложения."""
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    pg.setConfigOptions(background=CARD, foreground=MUTED, antialias=True)
