"""Оформление в духе старой программы: светлая тема по умолчанию,
тёмная - по выбору (галка в окне «Обзор»). Группы - в цветных рамках, как было."""
import os

ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ui", "icon")

DARK = """
QWidget { background: #202124; color: #e8eaed; }
QLineEdit, QComboBox, QTableWidget { background: #2b2c2f; color: #e8eaed; border: 1px solid #5f6368; }
QPushButton { background: #3c4043; color: #e8eaed; border: 1px solid #5f6368; padding: 4px 10px; }
QPushButton:disabled, QLineEdit:disabled { color: #6f7378; }
QHeaderView::section { background: #2b2c2f; color: #e8eaed; }
"""


def group(box, color, width=3):
    """Рамка группы, как в старой программе (зелёная - вакуум, голубая - данные и т.д.)."""
    box.setStyleSheet(
        f"QGroupBox {{ border: {width}px solid {color}; border-radius: 10px;"
        " margin-top: 2ex; padding-top: 8px; font-size: 11pt; font-weight: bold; }"
        "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; }")


def apply_theme(app, dark):
    app.setStyle("Fusion")
    app.setStyleSheet(DARK if dark else "")


def icon(name):
    return os.path.join(ICONS, name)
