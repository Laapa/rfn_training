"""Запись данных в .dat, как в старой программе: одна строка на тик.
Свой файл у каждого резонатора: data/<имя>/ГГГГ-ММ-ДД@ЧЧ-ММ-СС.dat

Колонки (первые - как в старой программе, в конце добавлены новые):
дата время  U(кВ)  I(А)  вакуум(А)  вакуум(Торр)  Pпад(кВт)  Pотр(кВт)  фаза(град)
            U_уставка(кВ)  I_уставка(А)  режим
"""
import os
from datetime import datetime


class DataFile:
    def __init__(self, folder):
        self.folder = folder
        self.file = None
        self.name = ""
        self.new_session()

    def new_session(self):
        """Кнопка «Новая сессия»: закрыть старый файл, начать новый."""
        if self.file:
            self.file.close()
        os.makedirs(self.folder, exist_ok=True)
        self.name = os.path.join(self.folder, datetime.now().strftime("%Y-%m-%d@%H-%M-%S") + ".dat")
        self.file = open(self.name, "a", encoding="utf-8")

    def write(self, m, vacuum, setpoint, current, mode):
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cols = [f"{m['u']:.1f}", f"{m['i']:.1f}", f"{m['pump_a']:7.1e}", f"{vacuum:8.2e}",
                f"{m['p_fwd']:.2f}", f"{m['p_ref']:.2f}", f"{m['phase']:.2f}",
                f"{setpoint:.2f}", f"{current:.2f}", mode]
        self.file.write(stamp + "\t" + "\t".join(cols) + "\n")
        self.file.flush()
