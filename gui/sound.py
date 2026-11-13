"""Фанфары, когда тренировка дошла до Stop (README, п.5).
Мелодию генерируем сами (файл fanfare.wav рядом с настройками), играем средствами Windows."""
import math
import os
import struct
import sys
import wave

from PyQt5 import QtWidgets

NOTES = [(523, 0.15), (659, 0.15), (784, 0.15), (1047, 0.45), (784, 0.15), (1047, 0.6)]  # до-ми-соль-до


def make_wav(path, rate=22050):
    frames = b""
    for freq, dur in NOTES:
        n = int(rate * dur)
        for k in range(n):
            fade = min(1.0, (n - k) / (rate * 0.03))          # без щелчков в конце ноты
            value = 0.5 * fade * math.sin(2 * math.pi * freq * k / rate)
            frames += struct.pack("<h", int(value * 32767))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)


def fanfare(folder):
    """Сыграть фанфары (не блокирует программу). Не Windows - просто системный сигнал."""
    if sys.platform != "win32":
        QtWidgets.QApplication.beep()
        return
    import winsound
    path = os.path.join(folder, "fanfare.wav")
    if not os.path.exists(path):
        make_wav(path)
    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
