"""Запуск программы.   python main.py"""
import sys

from PyQt5 import QtWidgets

from gui.main_window import MainWindow
from trainer.sim import SimResonator

# 1 тик = 1 секунда алгоритма. 1000 мс - реальное время, 200 мс - симулятор в 5 раз быстрее.
TICK_MS = 200


def make_resonators():
    """Пока симуляторы. Позже здесь будут резонаторы из Tango (по config)."""
    result = []
    for i in range(3):
        res = SimResonator(conditioned=24 + 3 * i, seed=i)   # каждый «грязный» по-своему
        res.set_voltage(20.0)
        result.append((f"Резонатор {i + 1}", res))
    return result


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow(make_resonators(), TICK_MS)
    window.resize(950, 1000)   # половина монитора по ширине
    window.show()
    sys.exit(app.exec_())
