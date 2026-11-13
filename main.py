"""Запуск программы.   python main.py"""
import sys

from PyQt5 import QtWidgets, QtCore

from gui import style
from gui.main_window import MainWindow
from trainer import config as cfg
from trainer.sim import SimResonator


def make_resonators(config):
    """Резонаторы из training_config.json. Пока только симуляторы, Tango - позже."""
    result = []
    for i, item in enumerate(config["resonators"]):
        if item["type"] != "sim":
            raise SystemExit(f"{item['name']}: тип {item['type']} ещё не поддерживается")
        res = SimResonator(conditioned=24 + 3 * i, seed=i,             # каждый «грязный» по-своему
                           vac_coeff=config["vac_coeff"], r_sh=config["r_sh"])
        res.set_voltage(20.0)
        result.append((item["name"], res))
    return result


if __name__ == "__main__":
    # Масштаб Windows (125%, 150%, 4K): без этих строк PyQt5 рисует мелко или мыльно.
    # Ставятся ДО создания QApplication.
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    config, message = cfg.load()
    style.apply_theme(app, config["dark_theme"])
    window = MainWindow(make_resonators(config), config, message)
    window.resize(900, 260)   # окна резонаторов встают в половины экрана сами
    window.show()
    sys.exit(app.exec_())
