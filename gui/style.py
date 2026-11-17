"""Оформление: обычный вид Qt (как в системе), без своих тем и стилей.
Цвет - только там, где он что-то значит: лампы, пороги вакуума, превышения."""

# цвета сигналов: пороги вакуума, лампы, превышения
C = {"green": "#16a34a", "red": "#dc2626", "orange": "#f59e0b", "magenta": "#c026d3", "gray": "#9ca3af"}
LAMP = {"green": "#22c55e", "red": "#ef4444", "gray": "#b0b0b0", "blue": "#3b82f6"}


def app_icon():
    """Путь к иконке программы (ui/app.ico; в exe - внутри сборки)."""
    import os
    import sys
    base = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    return os.path.join(base, "ui", "app.ico")


def color(name):
    """Цвет по имени ("green", "red", ...); "" - обычный цвет текста."""
    return C.get(name, name)
