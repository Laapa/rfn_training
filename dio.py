import sys  # sys нужен для передачи argv в QApplication
import os  # Отсюда нам понадобятся методы для отображения содержимого директорий
import pathlib

# import serial

# import socket
import time
# from threading import Timer
from PyQt5.QtCore import QTimer, QDateTime
import pyqtgraph as pg
import math 

# import .initials

from PyDAQmx import *
import ctypes
import PyDAQmx as daqmx

from datetime import datetime
from pathlib import Path

from PyQt5 import uic, QtWidgets, QtCore, QtGui

from pyModbusTCP.client import ModbusClient

# import matplotlib.pyplot as plt
import numpy as np

digital_output = Task()
ddata00 = np.array([0,0,0,0,0], dtype=np.uint8)
ddata01 = np.array([1,0,0,0,0], dtype=np.uint8)
ddata02 = np.array([0,1,0,0,0], dtype=np.uint8)
ddata03 = np.array([0,0,1,0,0], dtype=np.uint8)
ddata04 = np.array([0,0,0,0,1], dtype=np.uint8)

try:
    digital_output.CreateDOChan("/PXI1Slot2/port0/line0:4","",daqmx.DAQmx_Val_ChanForAllLines)
except:
    print("No device PXI1Slot2")    
try:
    digital_output.StartTask()
except:
    print("digital output task failed")

# digital_output.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata01,None,None)
# time.sleep(0.5)
#digital_output.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata02,None,None)
#time.sleep(0.5)
digital_output.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata03,None,None)
time.sleep(1.0)
#digital_output.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata04,None,None)
time.sleep(1.0) 
digital_output.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata00,None,None) 