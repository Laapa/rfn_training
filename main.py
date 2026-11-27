"""Запуск программы.
    python main.py                      - спросит «Tango или EPICS?» и возьмёт tango_config.json / epics_config.json
    python main.py fake_config.json     - другой файл настроек (например, для фейкового стенда)
    python main.py fake_epics_config.json  - то же для EPICS-фейка
"""
import faulthandler
import os
import sys
import traceback
from datetime import datetime

from PyQt5 import QtWidgets, QtCore, QtGui

from gui import style
from gui.main_window import MainWindow
from trainer import config as cfg
from trainer.sim import SimResonator


def make_resonators(config):
    """Резонаторы из файла настроек: "sim" - симулятор, "tango" / "epics" - настоящий стенд."""
    if config["tango_host"]:
        os.environ["TANGO_HOST"] = config["tango_host"]
    if config["epics_ca_addr_list"]:            # где искать IOC (до первого обращения к EPICS!)
        os.environ["EPICS_CA_ADDR_LIST"] = config["epics_ca_addr_list"]
        os.environ["EPICS_CA_AUTO_ADDR_LIST"] = "NO"
    result = []
    for i, item in enumerate(config["resonators"]):
        if item["type"] == "tango":
            from trainer.tango_res import TangoResonator   # PyTango нужен только для железа
            res = TangoResonator(item["prefix"], config["vac_coeff"], config["vac_is_current"],
                                 nodb=item.get("nodb", False))
        elif item["type"] == "epics":
            from trainer.epics_res import EpicsResonator   # pyepics нужен только для EPICS
            res = EpicsResonator(item["prefix"], config["vac_coeff"], config["vac_is_current"],
                                 pv=item.get("pv"))
        else:
            res = SimResonator(conditioned=14 + 3 * i, seed=i,         # каждый «грязный» по-своему
                               vac_coeff=config["vac_coeff"], r_sh=config["r_sh"])
            res.set_voltage(10.0)
        result.append((item["name"], res))
    return result


def show_error(kind, value, tb):
    """Любая непойманная ошибка: в exe нет консоли, поэтому пишем её в error.log рядом с настройками
    и показываем окно. Заодно PyQt5 не закрывает программу молча из-за ошибки в обработчике кнопки."""
    text = "".join(traceback.format_exception(kind, value, tb))
    path = os.path.join(os.path.dirname(cfg.PATH), "error.log")
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S}\n{text}\n")
    except OSError:
        pass
    if QtWidgets.QApplication.instance():
        QtWidgets.QMessageBox.critical(None, "Ошибка", f"{value}\n\nПодробности: {path}")
    else:
        print(text, file=sys.stderr)


def choose_stack():
    """Окно при запуске: с какой системой управления работаем. Возвращает "tango", "epics" или None (выход)."""
    box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Question, "Тренировка резонаторов",
                                "С какой системой управления работаем?")
    box.setInformativeText("Настройки берутся из " + " / ".join(cfg.STACK_FILES.values())
                           + " рядом с программой (нет файла - создастся).")
    buttons = {box.addButton(name, QtWidgets.QMessageBox.AcceptRole): kind
               for kind, name in (("tango", "Tango"), ("epics", "EPICS"))}
    box.addButton("Выход", QtWidgets.QMessageBox.RejectRole)
    box.exec_()
    return buttons.get(box.clickedButton())


if __name__ == "__main__":
    sys.excepthook = show_error
    # «Жёсткое» падение внутри библиотеки на C (Python не успевает показать ошибку, окно просто исчезает):
    # хотя бы место падения - в crash.log рядом с программой
    CRASH_LOG = open(os.path.join(cfg.BASE, "crash.log"), "a", encoding="utf-8")
    faulthandler.enable(CRASH_LOG)
    # Масштаб Windows (125%, 150%, 4K): без этих строк PyQt5 рисует мелко или мыльно.
    # Ставятся ДО создания QApplication.
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Тренировка резонаторов")
    app.setWindowIcon(QtGui.QIcon(style.app_icon()))
    if len(sys.argv) > 1:                        # файл указан явно (например, фейк) - без вопроса
        config, message = cfg.load(sys.argv[1])
    else:
        kind = choose_stack()
        if kind is None:
            sys.exit(0)
        config, message = cfg.load(os.path.join(cfg.BASE, cfg.STACK_FILES[kind]), kind)
    window = MainWindow(make_resonators(config), config, message)
    window.resize(900, 260)   # окна резонаторов встают в половины экрана сами
    window.show()
    sys.exit(app.exec_())
