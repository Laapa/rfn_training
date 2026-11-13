"""Запись данных в .dat, как в старой программе: одна строка на тик.
Свой файл у каждого резонатора: data/<имя>/ГГГГ-ММ-ДД@ЧЧ-ММ-СС.dat
Рядом - журнал событий с тем же именем .log (шаги алгоритма, команды, ошибки связи).

Колонки (первые - как в старой программе, в конце добавлены новые):
дата время  U(кВ)  I(А)  вакуум(А)  вакуум(Торр)  Pпад(кВт)  Pотр(кВт)
            U_уставка(кВ)  I_уставка(А)  режим
(фазометра на стенде нет, поэтому колонки фазы, которая была в старой программе, тоже нет)
"""
import os
from datetime import datetime


class DataFile:
    def __init__(self, folder):
        self.folder = folder
        self.file = None
        self.log_file = None
        self.name = ""
        self.new_session()

    def new_session(self):
        """Кнопка «Новая сессия»: закрыть старый файл, начать новый."""
        if self.file:
            self.file.close()
            self.log_file.close()
        os.makedirs(self.folder, exist_ok=True)
        self.name = os.path.join(self.folder, datetime.now().strftime("%Y-%m-%d@%H-%M-%S") + ".dat")
        self.file = open(self.name, "a", encoding="utf-8")
        self.log_file = open(self.name[:-4] + ".log", "a", encoding="utf-8")

    def log(self, msg):
        """Строка в журнал событий."""
        self.log_file.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "  " + msg + "\n")
        self.log_file.flush()

    def write(self, m, vacuum, setpoint, current, mode):
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cols = [f"{m['u']:.1f}", f"{m['i']:.1f}", f"{m['pump_a']:7.1e}", f"{vacuum:8.2e}",
                f"{m['p_fwd']:.2f}", f"{m['p_ref']:.2f}",
                f"{setpoint:.2f}", f"{current:.2f}", mode]
        self.file.write(stamp + "\t" + "\t".join(cols) + "\n")
        self.file.flush()
