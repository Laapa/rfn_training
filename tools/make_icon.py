"""Рисует иконку программы ui/app.ico (нужен Pillow: pip install pillow).
Запускать один раз, результат лежит в репозитории."""
import math
import os
import sys

from PIL import Image
from PyQt5 import QtGui, QtCore, QtWidgets

app = QtWidgets.QApplication(sys.argv)
S = 256
img = QtGui.QImage(S, S, QtGui.QImage.Format_ARGB32)
img.fill(QtCore.Qt.transparent)
p = QtGui.QPainter(img)
p.setRenderHint(QtGui.QPainter.Antialiasing)

grad = QtGui.QLinearGradient(0, 0, S, S)                 # фон: синий скруглённый квадрат
grad.setColorAt(0, QtGui.QColor("#1e40af"))
grad.setColorAt(1, QtGui.QColor("#0891b2"))
p.setBrush(grad)
p.setPen(QtCore.Qt.NoPen)
p.drawRoundedRect(8, 8, S - 16, S - 16, 52, 52)

p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 70), 6))  # ступеньки напряжения - тренировка
path = QtGui.QPainterPath(QtCore.QPointF(40, 200))
for k in range(5):
    path.lineTo(40 + k * 36, 200 - k * 30)
    path.lineTo(40 + (k + 1) * 36, 200 - k * 30)
p.drawPath(path)

pen = QtGui.QPen(QtGui.QColor("white"), 14)               # ВЧ-синусоида
pen.setCapStyle(QtCore.Qt.RoundCap)
p.setPen(pen)
wave = QtGui.QPainterPath(QtCore.QPointF(40, 128))
for x in range(40, 217, 2):
    wave.lineTo(x, 128 - 52 * math.sin((x - 40) / 176 * 3 * math.pi) * (0.4 + 0.6 * (x - 40) / 176))
p.drawPath(wave)
p.end()

here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ui")
png = os.path.join(here, "app.png")
img.save(png)
Image.open(png).save(os.path.join(here, "app.ico"),
                     sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("готово:", os.path.join(here, "app.ico"))
