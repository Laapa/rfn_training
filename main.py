"""Запуск программы.
    python main.py                      - настройки из training_config.json
    python main.py fake_config.json     - другой файл настроек (например, для фейкового стенда)
"""
import os
import sys

from PyQt5 import QtWidgets, QtCore, QtGui

from gui import style
from gui.main_window import MainWindow
from trainer import config as cfg
from trainer.sim import SimResonator


def make_resonators(config):
    """Резонаторы из training_config.json: "sim" - симулятор, "tango" - настоящий."""
    if config["tango_host"]:
        os.environ["TANGO_HOST"] = config["tango_host"]
    result = []
    for i, item in enumerate(config["resonators"]):
        if item["type"] == "tango":
            from trainer.tango_res import TangoResonator   # PyTango нужен только для железа
            res = TangoResonator(item["prefix"], config["vac_coeff"], config["vac_is_current"],
                                 nodb=item.get("nodb", False))
        else:
            res = SimResonator(conditioned=14 + 3 * i, seed=i,         # каждый «грязный» по-своему
                               vac_coeff=config["vac_coeff"], r_sh=config["r_sh"])
            res.set_voltage(10.0)
        result.append((item["name"], res))
    return result


if __name__ == "__main__":
    # Масштаб Windows (125%, 150%, 4K): без этих строк PyQt5 рисует мелко или мыльно.
    # Ставятся ДО создания QApplication.
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Тренировка резонаторов")
    app.setWindowIcon(QtGui.QIcon(style.app_icon()))
    config, message = cfg.load(sys.argv[1] if len(sys.argv) > 1 else None)
    style.apply_theme(app, config["dark_theme"])
    window = MainWindow(make_resonators(config), config, message)
    window.resize(900, 260)   # окна резонаторов встают в половины экрана сами
    window.show()
    sys.exit(app.exec_())
