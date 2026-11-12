import sys  # sys нужен для передачи argv в QApplication
import os  # Отсюда нам понадобятся методы для отображения содержимого директорий
import pathlib
import time
from PyQt5.QtCore import QTimer, QDateTime
import pyqtgraph as pg
import math 
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox, QVBoxLayout, QPushButton
from PyDAQmx import *
import ctypes
import PyDAQmx as daqmx
from datetime import datetime
from pathlib import Path
from PyQt5 import uic, QtWidgets, QtCore, QtGui
from pyModbusTCP.client import ModbusClient
import numpy as np
import json
from scipy.interpolate import interp1d
from scipy.signal import find_peaks

# Генерируем данные
x_pad = [0.0, 0.287, 0.574, 0.734, 0.932, 1.124, 1.337, 1.582, 1.908, 2.178, 2.364, 2.684, 3.025, 3.377, 3.763, 4.065, 4.254, 4.539, 4.653, 4.924, 5.078, 5.226, 5.244]
x_otr = [0.0, 0.678, 0.691, 0.755, 0.801, 0.909, 0.967, 1.016, 1.103, 1.167, 1.202, 1.24, 1.28, 1.324, 1.406, 1.487, 1.528, 1.58, 1.674, 1.712, 1.74, 1.78, 1.795, 1.929, 2.006, 2.102, 2.156, 2.209, 2.242, 2.272, 2.292] 
y_pad = [0.0, 0.1, 0.7, 1.2, 2.0, 2.9, 4.0, 5.5, 7.9, 10.3, 11.8, 15.0, 18.7, 23.0, 28.0, 32.1, 35.0, 39.6, 41.5, 46.0, 49.6, 51.2, 51.6]
y_otr = [0.0, 1.2, 1.3, 1.6, 1.8, 2.2, 2.5, 2.7, 3.1, 3.5, 3.7, 3.9, 4.1, 4.4, 4.9, 5.5, 5.8, 6.2, 6.8, 7.2, 7.4, 7.6, 7.85, 8.7, 9.6, 10.6, 11.1, 11.7, 12.0, 12.3, 12.7]

f1 = interp1d(x_pad, y_pad, kind='linear', fill_value='extrapolate')
f2 = interp1d(x_otr, y_otr, kind='linear', fill_value='extrapolate')

digital_buttons = Task()
ddata00 = np.array([0,0,0,0,0], dtype=np.uint8) # Сброс всего
ddata01 = np.array([1,0,0,0,0], dtype=np.uint8) # Сброс генератора
ddata02 = np.array([0,1,0,0,0], dtype=np.uint8) # Сбос ББ
ddata03 = np.array([0,0,1,0,0], dtype=np.uint8) # Выкл модулятора
ddata04 = np.array([0,0,0,0,1], dtype=np.uint8) # Вкл модулятора

try:
    digital_buttons.CreateDOChan("/PXI1Slot2/port0/line0:4","",daqmx.DAQmx_Val_ChanForAllLines)
except:
    print("No device PXI1Slot2")    
try:
    digital_buttons.StartTask()
except:
    print("digital output task failed")

def for_pad(x):
#    return float(f1(x))   # use interpolation function returned by `interp1d`
    return (1.891*x*x+1.2136*x)

def for_otr(x):
#    return float(f2(x))
    return (1.2*x*x+2.2227*x+0.45)

def find_local_maxima(data, num_zones=5):
    # Разделяем данные на зоны
    zone_size = len(data) // num_zones
    local_maxima = []
    for i in range(num_zones):
        # Определяем границы текущей зоны
        start = i * zone_size
        end = (i + 1) * zone_size if i < num_zones - 1 else len(data)
        # Извлекаем данные для текущей зоны
        zone_data = data[start:end]
        # Находим локальные максимумы в зоне
        peaks, _ = find_peaks(zone_data)
        if len(peaks) > 0:
            # Находим индекс максимального значения среди пиков
            max_peak_idx = peaks[np.argmax(zone_data[peaks])]
            # Добавляем глобальный индекс максимума
            local_maxima.append(start + max_peak_idx)
    return local_maxima

# DAQmx установки
nChannels = 8
average = 200
analog_input = Task()
read = int32()
adata = np.zeros((nChannels*average,), dtype=np.float64)
try:
    analog_input.CreateAIVoltageChan("/PXI1Slot2/ai0","",daqmx.DAQmx_Val_Cfg_Default,-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
    analog_input.CreateAIVoltageChan("/PXI1Slot2/ai1","",daqmx.DAQmx_Val_Cfg_Default,-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
    analog_input.CreateAIVoltageChan("/PXI1Slot2/ai2","",daqmx.DAQmx_Val_Cfg_Default,-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
    analog_input.CreateAIVoltageChan("/PXI1Slot2/ai3","",daqmx.DAQmx_Val_Cfg_Default,-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
    analog_input.CreateAIVoltageChan("/PXI1Slot2/ai4","",daqmx.DAQmx_Val_Cfg_Default,-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
    analog_input.CreateAIVoltageChan("/PXI1Slot2/ai5","",daqmx.DAQmx_Val_Cfg_Default,-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
    analog_input.CreateAIVoltageChan("/PXI1Slot2/ai6","",daqmx.DAQmx_Val_Cfg_Default,-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
    analog_input.CreateAIVoltageChan("/PXI1Slot2/ai7","",daqmx.DAQmx_Val_Cfg_Default,-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
except:
    print("No device Dev1")    
try:
    analog_input.StartTask()
except:
    print("analog input task failed")    
analog_output = Task()
try:
    analog_output.CreateAOVoltageChan("/PXI1Slot2/ao0","",-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
    analog_output.CreateAOVoltageChan("/PXI1Slot2/ao1","",-10.0,10.0,daqmx.DAQmx_Val_Volts,None)
except:
    print("No device Dev1")        
try:
    analog_output.StartTask()
except:
    print("analog output task failed")        
# digital_output = Task()
# digital_input = Task()
outdata = np.array([0,0], dtype=np.float64)
outdata_auto = np.array([0,0], dtype=np.float64)
minmax_auto = np.array([0,0], dtype=np.float64)
ddata = np.array([0,0], dtype=np.uint8)
# try:
#    digital_output.CreateDOChan("/PXI1Slot2/port0/line0:1","",daqmx.DAQmx_Val_ChanForAllLines)
#    digital_input.CreateDIChan("/PXI1Slot2/port0/line2:3","",daqmx.DAQmx_Val_ChanForAllLines)
# except:
#    print("No device Dev1")    

vacuum_graph = []
vacuum_graph_A = []
volt_graph = []
cur_graph = []
pad_graph = []
otr_graph = []
phase_graph = []
time_graph = []
X_data = []
Y_data = []
time_graph.append(0)
vacuum_graph.append(0)
vacuum_graph_A.append(0)
volt_graph.append(0)
pad_graph.append(0)
otr_graph.append(0)
phase_graph.append(0)
cur_graph.append(0)

colors = ["y", "b", "r", "g", "o", "k"]
symb_size = 1

lo_vac_On = 0xF03C
lo_vac_Off = 0xF032
warn = 0
freeze_counter = 0
vacuum = 1.e-11
kvolts = 0.
i_coeff_2= 29.

default_config={
        "vac_coeff": 1500,
        "i_coeff": 29,
        "u_dac_coeff": 187,
        "u_adc_coeff": 282,
        "ip_address": "10.0.0.96",
        "port": 502,
        "unit_id": 3,
        "input_reg": 0,
        "red_text": 1.0e-4,
        "green_text": 0.5e-4,
        "orange_text": 6.7e-4,
        "xtime": 2400,
        "u_otr_coeff": 0,
        "r_sh": 3190000.0
    }
tune = 100
tune_auto = 100
step_auto = 1000
vstep_auto = 100
current_auto = 0.1
# Флаги управления
go_up = 1
auto_enabled = 0

# Класс, видимо, для подписей в виде timestamp на графиках

class TimeAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [datetime.fromtimestamp(value) for value in values]

class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()
        dir_path = Path.cwd()
        path = Path(dir_path, "ui", "skif.ui")
        uic.loadUi(path, self)

###############################################################################################
        self.config_path='config.json'
        self.config = self.load_config()
        
        # Калибровочные константы
        global vac_coeff
        vac_coeff = self.config.get('vac_coeff')
        global i_coeff
        i_coeff = self.config.get('i_coeff')
        global u_dac_coeff
        u_dac_coeff = self.config.get('u_dac_coeff')
        global u_adc_coeff
        u_adc_coeff = self.config.get('u_adc_coeff')
        
        #Значения
        global ip_address
        ip_address = self.config.get('ip_address')
        global port 
        port = self.config.get('port')
        global unit_id
        unit_id = self.config.get('unit_id')
        global input_reg
        input_reg = self.config.get('input_reg')
        global red_text
        red_text = self.config.get('red_text')
        global green_text
        green_text = self.config.get('green_text')
        global orange_text
        orange_text = self.config.get('orange_text')
        global xtime
        xtime = int(self.config.get('xtime'))
        global u_otr_coeff
        u_otr_coeff = int(self.config.get('u_otr_coeff'))
        global r_sh
        r_sh = float(self.config.get('r_sh'))     
        
        self.groupBox_11.setStyleSheet("QGroupBox { border: 5px solid green;"
                "font-size: 18px;"
                "border-radius: 10px;"
                "padding-top: 10px;"
                "margin-top: 2ex; }"
                "QGroupBox:title { subcontrol-origin: margin;"
                "subcontrol-position: top left; }")

        self.lineEdit_53.setText(str(vac_coeff))
        self.lineEdit_54.setText(str(i_coeff))
        self.lineEdit_55.setText(str(u_dac_coeff))
        self.lineEdit_56.setText(str(u_adc_coeff))
        self.lineEdit_59.setText(str(xtime))
        self.lineEdit_60.setText(str(u_otr_coeff))
        self.lineEdit_62.setText(str(r_sh))

        self.comboBox.addItems(["Вакуум (торр)", "Ток насоса (A)", "Напряжение", "Ток", "Падающая", "Отраженная", "Фазометр"])
        self.comboBox_2.addItems(["Вакуум (торр)", "Ток насоса (A)", "Напряжение", "Ток", "Падающая", "Отраженная", "Фазометр"])
        self.comboBox_3.addItems(["Вакуум (торр)", "Ток насоса (A)", "Напряжение", "Ток", "Падающая", "Отраженная", "Фазометр"])
        self.comboBox_4.addItems(["Вакуум (торр)", "Ток насоса (A)", "Напряжение", "Ток", "Падающая", "Отраженная", "Фазометр"])
        self.comboBox_5.addItems(["Вакуум (торр)", "Ток насоса (A)", "Напряжение", "Ток", "Падающая", "Отраженная", "Фазометр"])
        self.comboBox_6.addItems(["Вакуум (торр)", "Ток насоса (A)", "Напряжение", "Ток", "Падающая", "Отраженная", "Фазометр"])
        self.comboBox.activated[str].connect(self.onChanged)
        self.comboBox_2.activated[str].connect(self.onChanged_2) 
        self.comboBox_3.activated[str].connect(self.onChanged_3)
        self.comboBox_4.activated[str].connect(self.onChanged_4)
        self.comboBox_5.activated[str].connect(self.onChanged_5) 
        self.comboBox_6.activated[str].connect(self.onChanged_6)
        self.spinBox_5.valueChanged.connect(self.set_average)
        self.spinBox_6.valueChanged.connect(self.set_step_auto)
        self.spinBox_7.valueChanged.connect(self.set_vstep_auto)
        self.spinBox_8.valueChanged.connect(self.set_xtime)
        self.spinBox_8.setValue(int(xtime))
        self.lineEdit_49.setText(str(round(10.*u_dac_coeff/1000., 1)))
        self.verticalSlider.valueChanged.connect(self.set_DAC_spin)
        self.verticalSlider_2.valueChanged.connect(self.set_auto_spin)
#        self.widget.setBackground("w")
#        self.widget_2.setBackground("w")
#        self.widget_3.setBackground("w")
        self.widget.showGrid(x=True, y=True)
        self.widget.setTitle("Vacuum (torr) vs Time", color="y", size="14pt")
        self.comboBox.setCurrentIndex(0)
        self.widget_5.enableAutoRange()
        self.widget_2.showGrid(x=True, y=True)
        self.widget_2.setTitle("Voltage vs Time", color="y", size="14pt")
        self.comboBox_2.setCurrentIndex(2)
        self.widget_3.showGrid(x=True, y=True)
        self.widget_3.setTitle("Reflected vs Time", color="y", size="14pt")
        self.comboBox_3.setCurrentIndex(5)
        self.widget_4.showGrid(x=True, y=True)
        self.widget_5.showGrid(x=True, y=True)
        self.widget_6.showGrid(x=True, y=True)
        self.widget_4.setYRange(0., 500.)
        self.widget_5.setYRange(0., 1.e-3)
        self.widget_6.setXRange(0., 550)
        self.widget_4.setTitle("Voltage (kV)", color="y", size="14pt")
        self.widget_5.setTitle("Vacuum (torr)", color="y", size="14pt")
        self.widget_6.setTitle("Vacuum (torr) vs Voltage", color="y", size="14pt")

        date_axis_4 = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation = 'bottom')
        date_axis_5 = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation = 'bottom')
        self.widget_4.setAxisItems(axisItems = {'bottom': date_axis_4})
        self.widget_5.setAxisItems(axisItems = {'bottom': date_axis_5})

        date_axis = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation = 'bottom')
        date_axis_2 = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation = 'bottom')
        date_axis_3 = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation = 'bottom')
        self.widget.setAxisItems(axisItems = {'bottom': date_axis})
        self.widget_2.setAxisItems(axisItems = {'bottom': date_axis_2})
        self.widget_3.setAxisItems(axisItems = {'bottom': date_axis_3})

        date_axis_7 = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation = 'bottom')
        date_axis_8 = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation = 'bottom')
        date_axis_9 = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation = 'bottom')
        self.widget_7.setAxisItems(axisItems = {'bottom': date_axis_7})
        self.widget_8.setAxisItems(axisItems = {'bottom': date_axis_8})
        self.widget_9.setAxisItems(axisItems = {'bottom': date_axis_9})


# С чего начинается графика.....
        
        pen = pg.mkPen(color=(255, 0, 0))
        pen_2 = pg.mkPen(color=(0, 255, 0))
        pen_3 = pg.mkPen(color=(0, 0, 255))
        pen_4 = pg.mkPen(color=(127, 127, 0))
        pen_5 = pg.mkPen(color=(0, 127, 127))
        pen_zero = pg.mkPen(color=(0, 0, 0))

        self.x_data_voltage = []*xtime
        self.x_data_vacuum = []*xtime
        self.x_data_vacuum_A = []*xtime
        self.y_data_voltage = []*xtime
        self.y_data_vacuum = []*xtime
        self.y_data_vacuum_A = []*xtime

        self.x_data_curr_fider = []*xtime
        self.y_data_curr_fider = []*xtime
        self.x_data_falling_wave = []*xtime
        self.y_data_falling_wave = []*xtime
        self.x_data_reflected_wave = []*xtime
        self.y_data_reflected_wave = []*xtime
        self.x_data_phase = []*xtime
        self.y_data_phase = []*xtime
       
        self.x_data_daqmx = []*xtime
        self.x_data_modbus = []*xtime
        self.y_data1 = []*xtime
        self.y_data2 = []*xtime
        self.y_data3 = []*xtime

        self.vacuum_data = []*xtime
        self.current_data = []*xtime
        self.voltage_data = []*xtime
        self.sensor_data = []*xtime
        self.phasemeter_data = []*xtime

        self.line = self.widget.plot(
            pen=pen,
            symbol="o",
            symbolSize=symb_size,
            symbolBrush="b",
        )
        self.line.clear()

        self.line_2 = self.widget_2.plot(
            pen=pen,
            symbol="o",
            symbolSize=symb_size,
            symbolBrush="b",
        )
        self.line_2.clear()

        self.line_3 = self.widget_3.plot(
            pen=pen,
            symbol="o",
            symbolSize=symb_size,
            symbolBrush="b",
        )
        self.line_3.clear()

        self.line_4 = self.widget_4.plot(
            pen=pen,
            symbol="o",
            symbolSize=symb_size,
            symbolBrush="b",
        )
        self.line_4.clear()

        self.line_5 = self.widget_5.plot(
            pen=pen,
            symbol="o",
            symbolSize=symb_size,
            symbolBrush="b",
        )
        self.line_5.clear()

        self.line_6 = self.widget_6.plot(
            pen=pen_zero,
            symbol="o",
            symbolSize=symb_size,
            symbolBrush="y",
        )
        self.line_6.clear()

        self.line_7 = self.widget_7.plot(
            pen=pen,
            symbol="o",
            symbolSize=symb_size,
            symbolBrush="w",
        )
        self.line_7.clear()

        self.line_8 = self.widget_8.plot(
            pen=pen,
            symbol="o",
            symbolSize=symb_size,
            symbolBrush="w",
        )
        self.line_8.clear()

        self.line_9 = self.widget_9.plot(
            pen=pen,
            symbol="o",
            symbolSize=symb_size,
            symbolBrush="w",
        )
        self.line_9.clear()              


        self.lineEdit_39.setStyleSheet("color: red;  background-color: white")
        self.lineEdit_39.setFont(QtGui.QFont('Consolas', 16))
        self.lineEdit_40.setStyleSheet("color: green;  background-color: white")
        self.lineEdit_40.setFont(QtGui.QFont('Consolas', 16))
        self.lineEdit_41.setStyleSheet("color: orange;  background-color: white")
        self.lineEdit_41.setFont(QtGui.QFont('Consolas', 16))
        self.lineEdit_43.setStyleSheet("color: red;  background-color: white")
        self.lineEdit_43.setFont(QtGui.QFont('Consolas', 16))
        self.lineEdit_44.setStyleSheet("color: green;  background-color: white")
        self.lineEdit_44.setFont(QtGui.QFont('Consolas', 16))
        self.lineEdit_42.setStyleSheet("color: orange;  background-color: white")
        self.lineEdit_42.setFont(QtGui.QFont('Consolas', 16))
        self.lineEdit_39.setText(str("{:7.1e}".format(red_text)))
        self.lineEdit_40.setText(str("{:7.1e}".format(green_text)))
        self.lineEdit_41.setText(str("{:7.1e}".format(orange_text)))
        self.lineEdit_42.setText(str("{:7.1e}".format(orange_text/vac_coeff)))
        self.lineEdit_43.setText(str("{:7.1e}".format(red_text/vac_coeff)))
        self.lineEdit_44.setText(str("{:7.1e}".format(green_text/vac_coeff)))

        self.timer_auto = QTimer()
        self.timer = QTimer()
        self.daqmx_timer = QTimer()
        self.modbus_timer = QTimer()
        self.timer.timeout.connect(self.showTime)
        self.timer.start(1000) 
        self.daqmx_timer.timeout.connect(self.daqmx_read)
        self.daqmx_timer.timeout.connect(self.update_x_axis)
        self.daqmx_timer.start(1000)
        self.modbus_timer.timeout.connect(self.modbus_read)
        self.timer_auto.timeout.connect(self.auto_go)
        self.timer.timeout.connect(self.update_widget)
        self.timer.timeout.connect(self.update_widget_2)
        self.timer.timeout.connect(self.update_widget_3)
        self.timer.timeout.connect(self.update_widget_4)
        self.timer.timeout.connect(self.update_widget_5)
        self.timer.timeout.connect(self.update_widget_6)
        self.timer.timeout.connect(self.update_max_points_tab3)
        self.connect()

        self.lineEdit.setText(ip_address)
        self.lineEdit_2.setText(str(port))
        self.lineEdit_3.setText(str(unit_id))
        self.checkBox_2.setStyleSheet('''
            QCheckBox::indicator:unchecked {
                image: url(ui/icon/switch_off.png);
            }
            QCheckBox::indicator:checked {
                image: url(ui/icon/switch_on.png);
            }
        ''')
        self.checkBox_3.setStyleSheet('''
            QCheckBox::indicator:unchecked {
                image: url(ui/icon/switch_on_min.png);
            }
            QCheckBox::indicator:checked {
                image: url(ui/icon/switch_off_min.png);
            }
        ''')
        self.checkBox_4.setStyleSheet('''
            QCheckBox::indicator:unchecked {
                image: url(ui/icon/arrow_up_gray_10.png);
            }
            QCheckBox::indicator:checked {
                image: url(ui/icon/arrow_up_10.png);
            }
        ''')
        self.checkBox_5.setStyleSheet('''
            QCheckBox::indicator:unchecked {
                image: url(ui/icon/arrow_down_gray_10.png);
            }
            QCheckBox::indicator:checked {
                image: url(ui/icon/arrow_down_10.png);
            }
        ''')
        self.label_20.setStyleSheet("font-size: 18px;")
        self.label_23.setStyleSheet("font-size: 18px;")
        self.label_24.setStyleSheet("font-size: 18px;")
        self.label_25.setStyleSheet("font-size: 18px;")
        self.label_26.setStyleSheet("font-size: 18px;")
        self.label_27.setStyleSheet("font-size: 18px;")
        self.label_28.setStyleSheet("font-size: 18px;")
        self.label_29.setStyleSheet("font-size: 18px;")
        self.label_30.setStyleSheet("font-size: 18px;")
        self.label_31.setStyleSheet("font-size: 18px;")
        self.label_32.setStyleSheet("font-size: 18px;")
        self.label_33.setStyleSheet("font-size: 18px;")
        self.label_34.setStyleSheet("font-size: 18px;")
        self.label_35.setStyleSheet("font-size: 18px;")
        self.label_36.setStyleSheet("font-size: 18px;")
        self.label_37.setStyleSheet("font-size: 18px;")
        self.label_38.setStyleSheet("font-size: 18px;")
        self.label_39.setStyleSheet("font-size: 18px;")
        self.lineEdit_34.setStyleSheet("font-size: 18px;")
        self.lineEdit_35.setStyleSheet("font-size: 18px;")
        self.lineEdit_37.setStyleSheet("font-size: 18px;")
        self.lineEdit_38.setStyleSheet("font-size: 18px;")
        self.pushButton_19.setStyleSheet("font-size: 18px;")
        self.pushButton_20.setStyleSheet("font-size: 18px;")
        self.pushButton_22.setStyleSheet("font-size: 18px;")
        self.spinBox_6.setStyleSheet("font-size: 18px;")
        self.spinBox_7.setStyleSheet("font-size: 18px;")
        self.groupBox.setStyleSheet("QGroupBox { border: 3px solid green;"
                            "border-radius: 10px;"
                            "margin-top: 2ex; }"
                            "QGroupBox:title { subcontrol-origin: margin;"
                            "subcontrol-position: top left; }")
        self.groupBox_2.setStyleSheet("QGroupBox { border: 3px solid blue;"
                            "border-radius: 10px;"
                            "padding-top: 10px;"
                            "margin-top: 2ex; }"
                            "QGroupBox:title { subcontrol-origin: margin;"
                            "subcontrol-position: top left; }")
        self.groupBox_3.setStyleSheet("QGroupBox { border: 3px solid orange;"
                            "border-radius: 10px;"
                            "padding-top: 10px;"
                            "margin-top: 2ex; }"
                            "QGroupBox:title { subcontrol-origin: margin;"
                            "subcontrol-position: top left; }")
        self.groupBox_6.setStyleSheet("QGroupBox { border: 3px solid magenta;"
                            "border-radius: 10px;"
                            "padding-top: 10px;"
                            "margin-top: 2ex; }"
                            "QGroupBox:title { subcontrol-origin: margin;"
                            "subcontrol-position: top left; }")
        self.groupBox_7.setStyleSheet("QGroupBox { border: 3px solid cyan;"
                            "border-radius: 10px;"
                            "padding-top: 10px;"
                            "margin-top: 2ex; }"
                            "QGroupBox:title { subcontrol-origin: margin;"
                            "subcontrol-position: top left; }")
        self.groupBox_8.setStyleSheet("QGroupBox { border: 5px solid red;"
                            "border-radius: 10px;"
                            "padding-top: 10px;"
                            "margin-top: 2ex; }"
                            "QGroupBox:title { subcontrol-origin: margin;"
                            "subcontrol-position: top left; }")
        self.groupBox_9.setStyleSheet("QGroupBox { border: 5px solid gray;"
                            "border-radius: 10px;"
                            "padding-top: 10px;"
                            "margin-top: 2ex; }"
                            "QGroupBox:title { subcontrol-origin: margin;"
                            "subcontrol-position: top left; }")
        self.groupBox_10.setStyleSheet("QGroupBox { border: 3px solid darkblue;"
                            "border-radius: 10px;"
                            "padding-top: 10px;"
                            "margin-top: 2ex; }"
                            "QGroupBox:title { subcontrol-origin: margin;"
                            "subcontrol-position: top left; }")
        self.pushButton_2.clicked.connect(self.connect)
        self.pushButton_6.clicked.connect(self.disconnect)
        self.pushButton_9.clicked.connect(self.read_graphs_from_file)
        self.checkBox.clicked.connect(self.check)
        self.checkBox_3.clicked.connect(self.auto_on_off)
        self.checkBox_4.clicked.connect(self.arrow_up)
        self.checkBox_5.clicked.connect(self.arrow_down)
        self.pushButton_7.clicked.connect(self.start_daqmx)
        self.pushButton_4.clicked.connect(self.start_mod)
        self.pushButton_5.clicked.connect(self.stop_mod)
        self.pushButton_8.clicked.connect(self.stop_daqmx)
        self.pushButton_11.clicked.connect(self.volt_up)
        self.pushButton_12.clicked.connect(self.cur_up)
        self.pushButton_13.clicked.connect(self.volt_down)
        self.pushButton_14.clicked.connect(self.cur_down)
        self.pushButton_15.clicked.connect(self.max_up_auto)
        self.pushButton_16.clicked.connect(self.min_up_auto)
        self.pushButton_17.clicked.connect(self.max_down_auto)
        self.pushButton_18.clicked.connect(self.min_down_auto)
        self.pushButton_20.clicked.connect(self.auto_on)
        self.pushButton_19.clicked.connect(self.auto_off)
        self.pushButton_21.clicked.connect(self.set_colors)
        self.pushButton_25.clicked.connect(self.clear_widget_6)
        self.pushButton_26.clicked.connect(self.clear_graph)
        self.pushButton_27.clicked.connect(self.write_new_config)
        self.pushButton_28.clicked.connect(self.marker_for_widget_5)
        self.pushButton_30.clicked.connect(self.reset_GEN)
        self.pushButton_31.clicked.connect(self.reset_BB)
        self.pushButton_32.clicked.connect(self.mod_on)
        self.pushButton_33.clicked.connect(self.mod_off)
 #       self.pushButton_23.clicked.connect(self.auto_yes)  
 #       self.pushButton_24.clicked.connect(self.auto_no)
        self.pushButton_22.clicked.connect(self.reverse_go)

        self.widget_4.setXLink(self.widget_5)
        self.widget.setXLink(self.widget_3)
        self.widget_2.setXLink(self.widget_3)
        self.widget_7.setXLink(self.widget_9)
        self.widget_8.setXLink(self.widget_9)
        
        self.widget.setClipToView(True)
        self.widget_2.setClipToView(True)
        self.widget_3.setClipToView(True)
        self.widget_4.setClipToView(True)
        self.widget_5.setClipToView(True)
        self.widget_6.setClipToView(True)
        self.widget_7.setClipToView(True)
        self.widget_8.setClipToView(True)
        self.widget_9.setClipToView(True)

                
        self.max_count = 5  # Количество максимальных значений для отображения

        # Настройка графиков в окне 2
        self.max_points_tab2_1 = [self.widget.plot([], [], pen='g', symbol='o', symbolPen ='g', symbolBrush=10) for _ in range(self.max_count)]  # максимальные значения
        self.text_items_tab2_1 = [pg.TextItem('', anchor=(0, 1)) for _ in range(self.max_count)]  # текст для максимума
        for text_item in self.text_items_tab2_1:
            self.widget.addItem(text_item)

        self.max_points_tab2_2 = [self.widget_2.plot([], [], pen='r', symbol='o', symbolPen ='b', symbolBrush=10) for _ in range(self.max_count)]  # максимальные значения
        self.text_items_tab2_2 = [pg.TextItem('', anchor=(0, 1)) for _ in range(self.max_count)]  # текст для максимума второго графика
        for text_item in self.text_items_tab2_2:
            self.widget_2.addItem(text_item)

        self.max_points_tab2_3 = [self.widget_3.plot([], [], pen='r', symbol='o', symbolPen ='b', symbolBrush=10) for _ in range(self.max_count)]  # максимальные значения
        self.text_items_tab2_3 = [pg.TextItem('', anchor=(0, 1)) for _ in range(self.max_count)]  # текст для максимума третьего графика
        for text_item in self.text_items_tab2_3:
            self.widget_3.addItem(text_item)    

        # Настройка графиков в окне 3
        self.max_points_tab3_1 = [self.widget_7.plot([], [], pen='g', symbol='o', symbolPen ='g', symbolBrush=10) for _ in range(self.max_count)]  # максимальные значения
        self.text_items_tab3_1 = [pg.TextItem('', anchor=(0, 1)) for _ in range(self.max_count)]  # текст для максимума
        for text_item in self.text_items_tab3_1:
            self.widget_7.addItem(text_item)

        self.max_points_tab3_2 = [self.widget_8.plot([], [], pen='r', symbol='o', symbolPen ='b', symbolBrush=10) for _ in range(self.max_count)]  # максимальные значения
        self.text_items_tab3_2 = [pg.TextItem('', anchor=(0, 1)) for _ in range(self.max_count)]  # текст для максимума второго графика
        for text_item in self.text_items_tab3_2:
            self.widget_8.addItem(text_item)

        self.max_points_tab3_3 = [self.widget_9.plot([], [], pen='r', symbol='o', symbolPen ='b', symbolBrush=10) for _ in range(self.max_count)]  # максимальные значения
        self.text_items_tab3_3 = [pg.TextItem('', anchor=(0, 1)) for _ in range(self.max_count)]  # текст для максимума третьего графика
        for text_item in self.text_items_tab3_3:
            self.widget_9.addItem(text_item)    

        self.Pressed=False
        self.pushButton_29.clicked.connect(self.stop_drawing_graphs_tab2)

        now = datetime.now()
        self.filename = now.strftime("%Y-%m-%d")+"@"+now.strftime("%H-%M-%S")
        self.file = open(self.filename + '.dat', 'a')
        self.lineEdit_51.setText("Начата запись в файл " + self.filename)
        self.populate_combo_box()
        self.show()

    def reset_GEN(self):
        digital_buttons.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata01,None,None)
        time.sleep(1.0) 
        digital_buttons.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata00,None,None)

    def reset_BB(self):
        digital_buttons.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata02,None,None)
        time.sleep(1.0) 
        digital_buttons.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata00,None,None)

    def mod_on(self):
        digital_buttons.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata04,None,None)
        time.sleep(1.0) 
        digital_buttons.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata00,None,None)

    def mod_off(self):
        digital_buttons.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata03,None,None)
        time.sleep(1.0) 
        digital_buttons.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata00,None,None)        

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setWindowTitle('Ошибка')
            error_dialog.setText('Произошла ошибка:')
            error_dialog.setInformativeText(f"Файл {self.config_path} не найден. Будет создан файл с настройками по умолчанию.")
            error_dialog.setStandardButtons(QMessageBox.Ok)
            error_dialog.exec_()  # Отображение окна
            self.lineEdit_52.setText(f"Файл {self.config_path} не найден. Создание файла с настройками по умолчанию.")
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
            self.lineEdit_52.setText(f"Файл {self.config_path} не найден. Cоздан файл {self.config_path} с настройками по умолчанию.")

            return self.load_config()
        
    def write_new_config(self):
        new_default_config={
            "vac_coeff": float(self.lineEdit_53.text()),
            "i_coeff": float(self.lineEdit_54.text()),
            "u_dac_coeff": float(self.lineEdit_55.text()),
            "u_adc_coeff": float(self.lineEdit_56.text()),
            "ip_address": "10.0.0.96",
            "port": 502,
            "unit_id": 3,
            "input_reg": 0,
            "red_text": float(self.lineEdit_39.text()),
            "green_text": float(self.lineEdit_40.text()),
            "orange_text": float(self.lineEdit_41.text()),
            "xtime": float(self.lineEdit_59.text()),
            "u_otr_coeff": float(self.lineEdit_60.text()),
            "r_sh": float(self.lineEdit_62.text())
        }
        with open(self.config_path, 'w') as f:
            f.write('')  # Записываем пустую строку, что оставляет файл пустым
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(new_default_config, f, indent=4)
        self.clear_graph()
        self.lineEdit_52.setText(f"Файл {self.config_path} успешно перезаписан. Начата запись в файл " + self.filename)
        self.spinBox_8.setValue(int(xtime))
        pass

    def populate_combo_box(self):
        #Заполнить комбобокс именами файлов .dat в текущей директории
        current_dir = os.getcwd()
        dat_files = [f for f in os.listdir(current_dir) if f.endswith('.dat')]
        if dat_files:
            self.comboBox_7.addItems(dat_files)
        else:
            QMessageBox.warning(self, "Предупреждение", "Файлы с расширением .dat не найдены в текущей директории.")

    def read_graphs_from_file(self):
        file_name = self.comboBox_7.currentText()
        file_name = file_name.replace('.dat', '')
        file_name = file_name + ".dat"
        try:
            # Открываем файл для чтения
            with open(file_name, 'r') as fr:
                # Читаем данные из файла
                data = np.loadtxt(fr, dtype=str)
                # Проверяем, что данные были загружены
                if data.size == 0:
                    map = QtGui.QPixmap("ui/icon/blue-led-on.png")
                    self.label_68.setPixmap(map)
                    self.lineEdit_51.setText("Файл " + file_name + " не содержит данных")
                    self.lineEdit_51.setText(str(ex))
                    self.line_7.setData(x=[0], y=[0])
                    self.line_8.setData(x=[0], y=[0])
                    self.line_9.setData(x=[0], y=[0])
                    map = QtGui.QPixmap("ui/icon/red-led-on.png")
                    self.label_68.setPixmap(map)
                    self.lineEdit_20.setText("0")
                    self.lineEdit_21.setText("0")
                    return
                # Разделяем данные на компоненты
                timestamps = [datetime.strptime(d + ' ' + t, '%Y-%m-%d %H:%M:%S') for d, t in data[:, :2]]
                self.Urez = data[:, 2].astype(float)
                self.Ifid = data[:, 3].astype(float)
                self.Vac_A = data[:, 4].astype(float)
                self.Vac = data[:, 5].astype(float)
                self.Upad = data[:, 6].astype(float)
                self.Uotr = data[:, 7].astype(float)
                self.Phase = data[:, 8].astype(float)
                # Преобразуем метки времени в числовой формат
                self.x_values = [x.timestamp() for x in timestamps]
                n_col = data.shape[1]
                n_row = data.shape[0]
                # Обновляем пользовательский интерфейс
                map = QtGui.QPixmap("ui/icon/green-led-on.png")
                self.label_68.setPixmap(map)
                self.lineEdit_20.setText(str(n_col))
                self.lineEdit_21.setText(str(n_row))
                self.line_7.setData(x=self.x_values, y=self.Vac)
                self.line_8.setData(x=self.x_values, y=self.Urez)
                self.line_9.setData(x=self.x_values, y=self.Uotr)
                self.comboBox_4.setCurrentText("Вакуум (торр)") 
                self.comboBox_5.setCurrentText("Напряжение") 
                self.comboBox_6.setCurrentText("Отраженная")
                self.widget_7.setTitle("Vacuum (torr) vs Time", color="y", size="14pt")
                self.widget_8.setTitle("Voltage vs Time", color="y", size="14pt")
                self.widget_9.setTitle("Reflected vs Time", color="y", size="14pt") 
                self.lineEdit_51.setText("Открыт файл " + file_name)
                self.data_tab3_graph1=self.Vac
                self.data_tab3_graph2=self.Urez
                self.data_tab3_graph3=self.Uotr
                self.update_max_points_tab3()
        except Exception as ex:
            self.lineEdit_51.setText(str(ex))
            self.line_7.setData(x=[0], y=[0])
            self.line_8.setData(x=[0], y=[0])
            self.line_9.setData(x=[0], y=[0])
            map = QtGui.QPixmap("ui/icon/red-led-on.png")
            self.label_68.setPixmap(map)
            self.lineEdit_20.setText("0")
            self.lineEdit_21.setText("0")

    def stop_drawing_graphs_tab2(self):
        if not self.Pressed:
            self.Pressed=True
            self.pushButton_29.setStyleSheet("QPushButton { background-color: red;"
                                             "font: Bold 14px; }")

        else:
            self.Pressed=False
            self.pushButton_29.setStyleSheet("QPushButton { background-color: lightgrey;"
                                                "font: Bold 14px; }")
    
    def arrow_up(self):
        global go_up
        go_up = 1
        self.checkBox_5.setCheckState(False)

    def arrow_down(self):
        global go_up
        go_up = 0
        self.checkBox_4.setCheckState(False)
    
    def clear_graph(self):
        time_graph.clear()
        vacuum_graph.clear()
        vacuum_graph_A.clear()
        volt_graph.clear()
        pad_graph.clear()
        otr_graph.clear()
        phase_graph.clear()
        time_graph.append(0)
        vacuum_graph.append(0)
        vacuum_graph_A.append(0)
        volt_graph.append(0)
        pad_graph.append(0)
        otr_graph.append(0)
        phase_graph.append(0)
        self.file.close()
        now = datetime.now()
        self.filename = now.strftime("%Y-%m-%d")+"@"+now.strftime("%H-%M-%S")
        self.file = open(self.filename + '.dat', 'a')
        self.lineEdit_51.setText("Начата запись в файл " + self.filename)
    
    def set_xtime(self):
        global xtime
        #xtime = self.spinBox_8.value()
        pass

    def update_x_axis(self):
        global xtime
        current_time=datetime.now()
        # Append new data
        self.x_data_voltage.append(current_time)
        self.x_data_vacuum.append(current_time)
        self.x_data_vacuum_A.append(current_time)
        self.x_data_curr_fider.append(current_time)
        self.x_data_falling_wave.append(current_time)
        self.x_data_reflected_wave.append(current_time)
        self.x_data_phase.append(current_time)
        # Keep last xtime measures
        self.x_data_voltage = self.x_data_voltage[-xtime:]
        self.x_data_vacuum = self.x_data_vacuum[-xtime:]
        self.x_data_vacuum_A = self.x_data_vacuum_A[-xtime:]
        self.x_data_curr_fider = self.x_data_curr_fider[-xtime:]
        self.x_data_falling_wave = self.x_data_falling_wave[-xtime:]
        self.x_data_reflected_wave = self.x_data_reflected_wave[-xtime:]
        self.x_data_phase = self.x_data_phase[-xtime:]

    def backtrack(self):
        global outdata_auto
        global vstep_auto
        global go_up
        if auto_enabled == 1:
            self.auto_on()
            if (go_up):
                outdata_auto[0] = outdata_auto[0] - vstep_auto/1000.
                analog_output.WriteAnalogF64(1, 0, 10, daqmx.DAQmx_Val_GroupByChannel, -outdata_auto, None, None)
                if auto_enabled == 0:
                    self.lineEdit_35.setText(str(round(outdata_auto[0], 5)))
                self.lineEdit_57.setText(str(round(outdata_auto[0]*u_dac_coeff, 1)))
            else:
                outdata_auto[0] = outdata_auto[0] + vstep_auto/1000.
                analog_output.WriteAnalogF64(1, 0, 10, daqmx.DAQmx_Val_GroupByChannel, -outdata_auto, None, None)
                if auto_enabled == 0:
                    self.lineEdit_35.setText(str(round(outdata_auto[0], 5)))
                self.lineEdit_57.setText(str(round(outdata_auto[0]*u_dac_coeff, 1)))

    def auto_on_off(self):
        global auto_enabled
        global outdata
        global outdata_auto
        state = self.checkBox_3.checkState()
        if (state):
            auto_enabled = 1
            outdata[0] = float(self.lineEdit_35.text())
            outdata_auto[0] = outdata[0]
            self.pushButton_19.setEnabled(True)
            self.pushButton_20.setEnabled(True)
            self.pushButton_22.setEnabled(True)
            self.pushButton_23.setEnabled(False)
            self.pushButton_24.setEnabled(True)
            self.groupBox_8.setStyleSheet("QGroupBox { border: 5px solid gray;"
                            "font-size: 18px;"
                            "border-radius: 10px;"
                            "padding-top: 10px;"
                            "margin-top: 2ex; }"
                            "QGroupBox:title { subcontrol-origin: margin;"
                            "subcontrol-position: top left; }")
            self.groupBox_9.setStyleSheet("QGroupBox { border: 5px solid red;"
                            "font-size: 18px;"
                            "border-radius: 10px;"
                            "padding-top: 10px;"
                            "margin-top: 2ex; }"
                            "QGroupBox:title { subcontrol-origin: margin;"
                            "subcontrol-position: top left; }")                      
        else:
            auto_enabled = 0
            self.timer_auto.stop()
            self.pushButton_19.setEnabled(False)
            self.pushButton_20.setEnabled(False)
            self.pushButton_22.setEnabled(False)
            self.pushButton_23.setEnabled(True)
            self.pushButton_24.setEnabled(False)
            map = QtGui.QPixmap("ui/icon/red-led-on.png")
            self.label_38.setPixmap(map)
#            self.label_47.setEnabled(False)
#            self.label_48.setEnabled(False)
            outdata[0] = outdata_auto[0] 
            self.groupBox_9.setStyleSheet("QGroupBox { border: 5px solid gray;"
                            "font-size: 18px;"
                            "border-radius: 10px;"
                            "padding-top: 10px;"
                            "margin-top: 2ex; }"
                            "QGroupBox:title { subcontrol-origin: margin;"
                            "subcontrol-position: top left; }")
            self.groupBox_8.setStyleSheet("QGroupBox { border: 5px solid red;"
                            "font-size: 18px;"
                            "border-radius: 10px;"
                            "padding-top: 10px;"
                            "margin-top: 2ex; }"
                            "QGroupBox:title { subcontrol-origin: margin;"
                            "subcontrol-position: top left; }") 
        
    def auto_yes(self):
        global auto_enabled
        global outdata
        global outdata_auto
        outdata[0] = float(self.lineEdit_35.text())
        outdata_auto[0] = outdata[0]
        map = QtGui.QPixmap("ui/icon/green-led-on.png")
        self.label_42.setPixmap(map)
        self.pushButton_19.setEnabled(True)
        self.pushButton_20.setEnabled(True)
        self.pushButton_22.setEnabled(True)
        self.pushButton_23.setEnabled(False)
        self.pushButton_24.setEnabled(True)
        auto_enabled = 1

    def auto_no(self):
        global auto_enabled
        map = QtGui.QPixmap("ui/icon/red-led-on.png")
        self.label_42.setPixmap(map)
        self.pushButton_19.setEnabled(False)
        self.pushButton_20.setEnabled(False)
        self.pushButton_22.setEnabled(False)
        self.pushButton_23.setEnabled(True)
        self.pushButton_24.setEnabled(False)
        auto_enabled = 0
        self.timer_auto.stop()
        map = QtGui.QPixmap("ui/icon/red-led-on.png")
        self.label_38.setPixmap(map)
#        self.label_47.setEnabled(False)
#        self.label_48.setEnabled(False)
        outdata[0] = outdata_auto[0]

    def reverse_go(self):
        global go_up
        if (go_up):
            go_up = 0
            self.checkBox_5.click()
        else:
            go_up = 1
            self.checkBox_4.click()
    
    def set_colors(self):
        global green_text
        global red_text
        global orange_text
        red_text = float(self.lineEdit_39.text())
        green_text = float(self.lineEdit_40.text())
        orange_text = float(self.lineEdit_41.text())
        self.lineEdit_42.setText(str("{:7.1e}".format(orange_text/vac_coeff)))
        self.lineEdit_43.setText(str("{:7.1e}".format(red_text/vac_coeff)))
        self.lineEdit_44.setText(str("{:7.1e}".format(green_text/vac_coeff)))

    def auto_go(self):
        global current_auto
        global outdata_auto
        global vstep_auto
        global minmax_auto
        global go_up
        current_auto = float(self.lineEdit_34.text())
        outdata_auto[1] = current_auto
        if (go_up):
#            self.label_47.setEnabled(True)
#            self.label_48.setEnabled(False)
            outdata_auto[0] = outdata_auto[0] + vstep_auto/1000.
            analog_output.WriteAnalogF64(1, 0, 10, daqmx.DAQmx_Val_GroupByChannel, -outdata_auto, None, None)
            self.lineEdit_35.setText(str(round(outdata_auto[0], 5)))
            self.lineEdit_57.setText(str(round(outdata_auto[0]*u_dac_coeff, 1)))
            if (outdata_auto[0] >= minmax_auto[0]):
                self.checkBox_5.click()  
        else:
#            self.label_47.setEnabled(False)
#            self.label_48.setEnabled(True)
            outdata_auto[0] = outdata_auto[0]-vstep_auto/1000.
            analog_output.WriteAnalogF64(1, 0, 10, daqmx.DAQmx_Val_GroupByChannel, -outdata_auto, None, None)
            self.lineEdit_35.setText(str(round(outdata_auto[0], 5)))
            self.lineEdit_57.setText(str(round(outdata_auto[0]*u_dac_coeff, 1)))
            if (outdata_auto[0] <= minmax_auto[1]):
                self.checkBox_4.click()  
                    
    def auto_on(self):
        global step_auto
        self.timer_auto.start(step_auto)
        map = QtGui.QPixmap("ui/icon/green-led-on.png")
        self.label_38.setPixmap(map)

    def auto_off(self):
        self.timer_auto.stop()
        map = QtGui.QPixmap("ui/icon/red-led-on.png")
        self.label_38.setPixmap(map)

    def max_up_auto(self):
        global tune_auto
        global minmax_auto
        minmax_auto[0] = minmax_auto[0] + 1./tune_auto
        self.lineEdit_38.setText(str(round(minmax_auto[0], 5)))
        self.lineEdit_46.setText(str(round(minmax_auto[0]*u_dac_coeff, 1)))

    def max_down_auto(self):
        global tune_auto
        global minmax_auto
        minmax_auto[0] = minmax_auto[0] - 1./tune_auto
        self.lineEdit_38.setText(str(round(minmax_auto[0], 5)))
        self.lineEdit_46.setText(str(round(minmax_auto[0]*u_dac_coeff, 1)))

    def min_up_auto(self):
        global tune_auto
        global minmax_auto
        minmax_auto[1] = minmax_auto[1] + 1./tune_auto
        self.lineEdit_37.setText(str(round(minmax_auto[1], 5)))
        self.lineEdit_47.setText(str(round(minmax_auto[1]*u_dac_coeff, 1)))

    def min_down_auto(self):
        global tune_auto
        global minmax_auto
        minmax_auto[1] = minmax_auto[1] - 1./tune_auto
        self.lineEdit_37.setText(str(round(minmax_auto[1], 5)))
        self.lineEdit_47.setText(str(round(minmax_auto[1]*u_dac_coeff, 1)))
        
    def volt_up(self):
        global tune
        global outdata
        outdata[1] = float(self.lineEdit_34.text())
        outdata[0] = outdata[0] + 1./tune
        analog_output.WriteAnalogF64(1, 0, 10, daqmx.DAQmx_Val_GroupByChannel, -outdata, None, None)
        self.lineEdit_35.setText(str(round(outdata[0], 5)))
        self.lineEdit_57.setText(str(round(outdata[0]*u_dac_coeff, 1)))
                        
    def cur_up(self):
        global tune
        global outdata
        outdata[0] = float(self.lineEdit_35.text())
        outdata[1] = outdata[1] + 1./tune
        analog_output.WriteAnalogF64(1, 0, 10, daqmx.DAQmx_Val_GroupByChannel, -outdata, None, None)
        self.lineEdit_34.setText(str(round(outdata[1], 5)))
        self.lineEdit_58.setText(str(round(outdata[1]*i_coeff_2, 1)))

    def volt_down(self):
        global tune
        global outdata
        outdata[1] = float(self.lineEdit_34.text())
        outdata[0] = outdata[0] - 1./tune
        analog_output.WriteAnalogF64(1, 0, 10, daqmx.DAQmx_Val_GroupByChannel, -outdata, None, None)
        self.lineEdit_35.setText(str(round(outdata[0], 5)))
        self.lineEdit_57.setText(str(round(outdata[0]*u_dac_coeff, 1)))

    def cur_down(self):
        global tune
        global outdata
        outdata[0] = float(self.lineEdit_35.text())
        outdata[1] = outdata[1] - 1./tune
        analog_output.WriteAnalogF64(1, 0, 10, daqmx.DAQmx_Val_GroupByChannel, -outdata, None, None)
        self.lineEdit_34.setText(str(round(outdata[1], 5)))
        self.lineEdit_58.setText(str(round(outdata[1]*i_coeff_2, 1)))
      
    def set_DAC_spin(self):
        global tune
        if (self.verticalSlider.value()==3):
            tune = 1000
        elif (self.verticalSlider.value()==2):
            tune = 100
        elif (self.verticalSlider.value()==1):
            tune = 10
        
    def set_auto_spin(self):
        global tune_auto
        if (self.verticalSlider_2.value()==3):
            tune_auto = 1000
        elif (self.verticalSlider_2.value()==2):
            tune_auto = 100
        elif (self.verticalSlider_2.value()==1):
            tune_auto = 10    

    def showTime(self):
        current_time=QDateTime.currentDateTime()
        formatted_time=current_time.toString('yyyy-MM-dd hh:mm:ss dddd')
        self.lineEdit_8.setText(formatted_time)
    
    def daqmx_read(self):
        global vacuum
        global xtime
        analog_input.ReadAnalogF64(average,10.0,daqmx.DAQmx_Val_GroupByScanNumber,adata,nChannels*average,ctypes.byref(read),None)
        self.lineEdit_13.setText(str(round(adata[0], 3)))
        self.lineEdit_14.setText(str(round(adata[1], 3)))
        self.lineEdit_15.setText(str(round(adata[2], 3)))
        self.lineEdit_16.setText(str(round(adata[3], 3)))
        self.lineEdit_23.setText(str(round(adata[4], 3)))
        self.lineEdit_22.setText(str(round(adata[5], 3)))
        if (adata[6]>1.5):
            map = QtGui.QPixmap("ui/icon/green-led-on.png")
            self.label_62.setPixmap(map)
            map = QtGui.QPixmap("ui/icon/gray-led-on.png")
            self.label_63.setPixmap(map)
        else:
            map = QtGui.QPixmap("ui/icon/red-led-on.png")
            self.label_63.setPixmap(map)
            map = QtGui.QPixmap("ui/icon/gray-led-on.png")
            self.label_62.setPixmap(map)
        if (adata[7]>3.5):
            map = QtGui.QPixmap("ui/icon/green-led-on.png")
            self.label_67.setPixmap(map)
        else:
            map = QtGui.QPixmap("ui/icon/gray-led-on.png")
            self.label_67.setPixmap(map)
        av_cur=av_volt=av_loc=av_phase=av_pad=av_otr=0.
        for i in range(average):
            av_cur += adata[nChannels*i]
            av_volt += adata[nChannels*i+1]
            av_loc += adata[nChannels*i+2]
            av_phase += adata[nChannels*i+3]
            av_pad += adata[nChannels*i+4]
            av_otr += adata[nChannels*i+5]
        av_cur = av_cur/average
        av_volt = av_volt/average
        av_loc = av_loc/average
        av_phase = av_phase/average
        av_pad = av_pad/average
        av_otr = av_otr/average
        self.lineEdit_32.setText(str(round(av_cur, 3)))
        self.lineEdit_27.setText(str(round(av_volt, 3)))
        self.lineEdit_30.setText(str(round(av_loc, 3)))
        self.lineEdit_25.setText(str(round(av_phase, 3)))
        self.lineEdit_48.setText(str(round(av_phase/0.05, 2)))
        self.y_data_phase.append(round(av_phase/0.05, 2))
        self.y_data_phase = self.y_data_phase[-xtime:]        
        self.lineEdit_33.setText(str(round(av_pad, 3)))
        self.lineEdit_31.setText(str(round(av_otr, 3)))
        current = av_cur*i_coeff
        self.lineEdit_24.setText(str(round(current, 1)))        
        self.y_data_curr_fider.append(round(current, 1))
        self.y_data_curr_fider = self.y_data_curr_fider[-xtime:]
        pad = for_pad(av_pad)
        self.lineEdit_29.setText(str(round(pad, 2)))
        self.y_data_falling_wave.append(round(pad, 2))
        self.y_data_falling_wave = self.y_data_falling_wave[-xtime:]
        otr = for_otr(av_otr)
        self.lineEdit_28.setText(str(round(otr, 2)))
        self.y_data_reflected_wave.append(round(otr, 2))
        self.y_data_reflected_wave = self.y_data_reflected_wave[-xtime:]
        kvolts = av_volt*u_adc_coeff
        kvolts_sh = math.sqrt(2*abs(pad-otr)*1.e3*r_sh)/1.e3
        self.lineEdit_36.setText(str(round(kvolts, 1)))
        self.lineEdit_50.setText(str(round(kvolts, 1)))
        self.lineEdit_61.setText(str(round(kvolts_sh, 1)))
        self.lineEdit_63.setText(str(round(kvolts_sh, 1)))
        if (kvolts>0):
            self.y_data_voltage.append((round(kvolts, 1)))
        else:
            self.y_data_voltage.append((round(0., 1)))
        self.y_data_voltage = self.y_data_voltage[-xtime:]  
        self.y_data_vacuum_A.append(vacuum)
        self.y_data_vacuum_A = self.y_data_vacuum_A[-xtime:]
        self.y_data_vacuum.append(vacuum/vac_coeff)
        self.y_data_vacuum = self.y_data_vacuum[-xtime:]
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.file.write(str(timestamp)+'\t'+str(round(kvolts, 1))+'\t'+str(round(current, 1))+'\t'+str("{:7.1e}".format(vacuum))+'\t'+str("{:8.2e}".format(vacuum/vac_coeff))+'\t'+str(round(pad, 2))+'\t'+str(round(otr, 2))+'\t'+str(round(av_phase/0.05, 2))+'\n')
        self.file.flush()
        if (kvolts>0):
            volt_graph.append(round(kvolts, 1))
        else:
            volt_graph.append(round(0., 1))
        vacuum_graph_A.append(vacuum)
        vacuum_graph.append(vacuum/vac_coeff)
        time_graph.append(time_graph[-1]+1)

        if float(self.lineEdit_28.text())>u_otr_coeff:
            self.lineEdit_28.setStyleSheet("color: red;  background-color: white")
        else:
            self.lineEdit_28.setStyleSheet("color: black;  background-color: white")
    
    def connect(self):
        global c
        c = ModbusClient(host=ip_address, port=port, unit_id=unit_id, auto_open=False, debug=False)
        connected = c.open()
        if connected:
            map = QtGui.QPixmap("ui/icon/green-led-on.png")
            self.label.setPixmap(map)
            self.checkBox.setEnabled(True)
            self.pushButton_2.setEnabled(False)
            self.pushButton_6.setEnabled(True)
            self.modbus_timer.start(500)
        else:
            map = QtGui.QPixmap("ui/icon/blue-led-on.png")
            self.label.setPixmap(map)
            
    #    self.pushButton.setEnabled(False)
    #    self.pushButton_2.setEnabled(True)
    #    self.pushButton_3.setEnabled(True)

    def disconnect(self):
        global c
        c.close()
        map = QtGui.QPixmap("ui/icon/red-led-on.png")
        self.label.setPixmap(map)
        self.checkBox.setCheckState(False)
        self.pushButton.setEnabled(False)
        self.checkBox.setEnabled(False)
        self.pushButton_2.setEnabled(True)
        self.pushButton_6.setEnabled(False)
        self.modbus_timer.stop() 
    #    self.pushButton_7.setEnabled(True)
    #    self.pushButton_2.setEnabled(False)
    #    self.pushButton_3.setEnabled(False)

    def start_daqmx(self):
        analog_input.StartTask()
        self.daqmx_timer.start(1000)
        self.pushButton_7.setEnabled(False)
        self.pushButton_8.setEnabled(True)
        self.spinBox_5.setEnabled(False)
        map = QtGui.QPixmap("ui/icon/green-led-on.png")
        self.label_3.setPixmap(map)

    def stop_daqmx(self):
        self.daqmx_timer.stop()
        analog_input.StopTask()
        self.pushButton_7.setEnabled(True)
        self.pushButton_8.setEnabled(False)
        self.spinBox_5.setEnabled(True)
        map = QtGui.QPixmap("ui/icon/red-led-on.png")
        self.label_3.setPixmap(map)

    #    analog_output.StartTask()

    def set_average(self):
        global average
        global adata
        average = self.spinBox_5.value()
        adata = np.zeros((nChannels*average,), dtype=np.float64)

    def set_step_auto(self):
        global step_auto
        step_auto = self.spinBox_6.value()

    def set_vstep_auto(self):
        global vstep_auto
        vstep_auto = self.spinBox_7.value()
        self.lineEdit_49.setText(str(round(vstep_auto*u_dac_coeff/1000., 1)))
        
    def onChanged(self, text):      
        if text == "Вакуум (торр)":
            self.widget.setTitle("Vacuum (torr) vs Time", color="y", size="14pt")
            self.widget.enableAutoRange(axis=pg.ViewBox.YAxis) 
        elif text == "Ток насоса (A)":
            self.widget.setTitle("Ipump (A) vs Time", color="y", size="14pt")
            self.widget.enableAutoRange(axis=pg.ViewBox.YAxis)    
        elif text == "Напряжение":
            self.widget.setTitle("Voltage vs Time", color="y", size="14pt")
            self.widget.enableAutoRange(axis=pg.ViewBox.YAxis) 
        elif text == "Ток":
            self.widget.setTitle("Current vs Time", color="y", size="14pt")
            self.widget.enableAutoRange(axis=pg.ViewBox.YAxis) 
        elif text == "Падающая":
            self.widget.setTitle("Incident vs Time", color="y", size="14pt")
            self.widget.enableAutoRange(axis=pg.ViewBox.YAxis) 
        elif text == "Отраженная":
            self.widget.setTitle("Reflected vs Time", color="y", size="14pt")
            self.widget.enableAutoRange(axis=pg.ViewBox.YAxis)    
        elif text == "Фазометр":
            self.widget.setTitle("Phase vs Time", color="y", size="14pt")
            self.widget.enableAutoRange(axis=pg.ViewBox.YAxis) 

    def onChanged_2(self, text):
        if text == "Вакуум (торр)":
            self.widget_2.setTitle("Vacuum (torr) vs Time", color="y", size="14pt")
            self.widget_2.enableAutoRange(axis=pg.ViewBox.YAxis) 
        elif text == "Ток насоса (A)":
            self.widget_2.setTitle("Ipump (A) vs Time", color="y", size="14pt")
            self.widget_2.enableAutoRange(axis=pg.ViewBox.YAxis)    
        elif text == "Напряжение":
            self.widget_2.setTitle("Voltage vs Time", color="y", size="14pt")
            self.widget_2.enableAutoRange(axis=pg.ViewBox.YAxis) 
        elif text == "Ток":
            self.widget_2.setTitle("Current vs Time", color="y", size="14pt")
            self.widget_2.enableAutoRange(axis=pg.ViewBox.YAxis) 
        elif text == "Падающая":
            self.widget_2.setTitle("Incident vs Time", color="y", size="14pt")
            self.widget_2.enableAutoRange(axis=pg.ViewBox.YAxis) 
        elif text == "Отраженная":
            self.widget_2.setTitle("Reflected vs Time", color="y", size="14pt")
            self.widget_2.enableAutoRange(axis=pg.ViewBox.YAxis) 
        elif text == "Фазометр":
            self.widget_2.setTitle("Phase vs Time", color="y", size="14pt")
            self.widget_2.enableAutoRange(axis=pg.ViewBox.YAxis) 

    def onChanged_3(self, text):
        if text == "Вакуум (торр)":
            self.widget_3.setTitle("Vacuum (torr) vs Time", color="y", size="14pt")
            self.widget_3.enableAutoRange(axis=pg.ViewBox.YAxis)
        elif text == "Ток насоса (A)":
            self.widget_3.setTitle("Ipump (A) vs Time", color="y", size="14pt")
            self.widget_3.enableAutoRange(axis=pg.ViewBox.YAxis)    
        elif text == "Напряжение":
            self.widget_3.setTitle("Voltage vs Time", color="y", size="14pt")
            self.widget_3.enableAutoRange(axis=pg.ViewBox.YAxis)
        elif text == "Ток":
            self.widget_3.setTitle("Current vs Time", color="y", size="14pt")
            self.widget_3.enableAutoRange(axis=pg.ViewBox.YAxis)
        elif text == "Падающая":
            self.widget_3.setTitle("Incident vs Time", color="y", size="14pt")
            self.widget_3.enableAutoRange(axis=pg.ViewBox.YAxis)
        elif text == "Отраженная":
            self.widget_3.setTitle("Reflected vs Time", color="y", size="14pt")
            self.widget_3.enableAutoRange(axis=pg.ViewBox.YAxis)
        elif text == "Фазометр":
            self.widget_3.setTitle("Phase vs Time", color="y", size="14pt")
            self.widget_3.enableAutoRange(axis=pg.ViewBox.YAxis)

    def onChanged_4(self, text):      
        if text == "Вакуум (торр)":
            self.widget_7.setTitle("Vacuum (torr) vs Time", color="y", size="14pt")
            self.line_7.setData(x=self.x_values, y=self.Vac)
            self.data_tab3_graph1=self.Vac
        elif text == "Ток насоса (A)":
            self.widget_7.setTitle("Ipump (A) vs Time", color="y", size="14pt") 
            self.line_7.setData(x=self.x_values, y=self.Vac_A)
            self.data_tab3_graph1=self.Vac_A
        elif text == "Напряжение":
            self.widget_7.setTitle("Voltage vs Time", color="y", size="14pt")
            self.line_7.setData(x=self.x_values, y=self.Urez)
            self.data_tab3_graph1=self.Urez
        elif text == "Ток":
            self.widget_7.setTitle("Current vs Time", color="y", size="14pt")
            self.line_7.setData(x=self.x_values, y=self.Ifid)
            self.data_tab3_graph1=self.Ifid
        elif text == "Падающая":
            self.widget_7.setTitle("Incident vs Time", color="y", size="14pt")
            self.line_7.setData(x=self.x_values, y=self.Upad)
            self.data_tab3_graph1=self.Upad
        elif text == "Отраженная":
            self.widget_7.setTitle("Reflected vs Time", color="y", size="14pt")
            self.line_7.setData(x=self.x_values, y=self.Uotr)
            self.data_tab3_graph1=self.Uotr
        elif text == "Фазометр":
            self.widget_7.setTitle("Phase vs Time", color="y", size="14pt")
            self.line_7.setData(x=self.x_values, y=self.Phase)
            self.data_tab3_graph1=self.Phase
        self.update_max_points_tab3()

    def onChanged_5(self, text):
        if text == "Вакуум (торр)":
            self.widget_8.setTitle("Vacuum (torr) vs Time", color="y", size="14pt")
            self.line_8.setData(x=self.x_values, y=self.Vac)
            self.data_tab3_graph2=self.Vac
        elif text == "Ток насоса (A)":
            self.widget_8.setTitle("Ipump (A) vs Time", color="y", size="14pt") 
            self.line_8.setData(x=self.x_values, y=self.Vac_A)
            self.data_tab3_graph2=self.Vac_A
        elif text == "Напряжение":
            self.widget_8.setTitle("Voltage vs Time", color="y", size="14pt")
            self.line_8.setData(x=self.x_values, y=self.Urez)
            self.data_tab3_graph2=self.Urez
        elif text == "Ток":
            self.widget_8.setTitle("Current vs Time", color="y", size="14pt")
            self.line_8.setData(x=self.x_values, y=self.Ifid)
            self.data_tab3_graph2=self.Ifid
        elif text == "Падающая":
            self.widget_8.setTitle("Incident vs Time", color="y", size="14pt")
            self.line_8.setData(x=self.x_values, y=self.Upad)
            self.data_tab3_graph2=self.Upad
        elif text == "Отраженная":
            self.widget_8.setTitle("Reflected vs Time", color="y", size="14pt")
            self.line_8.setData(x=self.x_values, y=self.Uotr)
            self.data_tab3_graph2=self.Uotr
        elif text == "Фазометр":
            self.widget_8.setTitle("Phase vs Time", color="y", size="14pt")
            self.line_8.setData(x=self.x_values, y=self.Phase)
            self.data_tab3_graph2=self.Phase
        self.update_max_points_tab3()

    def onChanged_6(self, text):
        if text == "Вакуум (торр)":
            self.widget_9.setTitle("Vacuum (torr) vs Time", color="y", size="14pt")
            self.line_9.setData(x=self.x_values, y=self.Vac)
            self.data_tab3_graph3=self.Vac
        elif text == "Ток насоса (A)":
            self.widget_9.setTitle("Ipump (A) vs Time", color="y", size="14pt") 
            self.line_9.setData(x=self.x_values, y=self.Vac_A)
            self.data_tab3_graph3=self.Vac_A
        elif text == "Напряжение":
            self.widget_9.setTitle("Voltage vs Time", color="y", size="14pt")
            self.line_9.setData(x=self.x_values, y=self.Urez)
            self.data_tab3_graph3=self.Urez
        elif text == "Ток":
            self.widget_9.setTitle("Current vs Time", color="y", size="14pt")
            self.line_9.setData(x=self.x_values, y=self.Ifid)
            self.data_tab3_graph3=self.Ifid
        elif text == "Падающая":
            self.widget_9.setTitle("Incident vs Time", color="y", size="14pt")
            self.line_9.setData(x=self.x_values, y=self.Upad)
            self.data_tab3_graph3=self.Upad
        elif text == "Отраженная":
            self.widget_9.setTitle("Reflected vs Time", color="y", size="14pt")
            self.line_9.setData(x=self.x_values, y=self.Uotr)
            self.data_tab3_graph3=self.Uotr
        elif text == "Фазометр":
            self.widget_9.setTitle("Phase vs Time", color="y", size="14pt")
            self.line_9.setData(x=self.x_values, y=self.Phase)
            self.data_tab3_graph3=self.Phase
        self.update_max_points_tab3()                       

    def update_widget(self):
        if not self.Pressed:
            text=str(self.comboBox.currentText())
            x_data=[]
            y_data=[]
            if text == "Вакуум (торр)":
                x_data=[x.timestamp() for x in self.x_data_vacuum]
                y_data=self.y_data_vacuum
            if text == "Ток насоса (A)":
                x_data=[x.timestamp() for x in self.x_data_vacuum_A]
                y_data=self.y_data_vacuum_A
            elif text == "Напряжение":
                x_data=[x.timestamp() for x in self.x_data_voltage]
                y_data=self.y_data_voltage
            elif text == "Ток":
                x_data=[x.timestamp() for x in self.x_data_curr_fider]
                y_data=self.y_data_curr_fider
            elif text == "Падающая":
                x_data=[x.timestamp() for x in self.x_data_falling_wave]
                y_data=self.y_data_falling_wave
            elif text == "Отраженная":
                x_data=[x.timestamp() for x in self.x_data_reflected_wave]
                y_data=self.y_data_reflected_wave   
            elif text == "Фазометр":
                x_data=[x.timestamp() for x in self.x_data_phase]
                y_data=self.y_data_phase
            self.line.setData(x=x_data, y=y_data)


        #    data = np.array(y_data)
        #    if len(data) > self.max_count:
        #        self.max_indices_tab2 = find_local_maxima(data, num_zones=self.max_count)
        #    else:
        #        self.max_indices_tab2 = np.arange(len(data))

        #    self.max_values_tab2 = np.array(y_data)[self.max_indices_tab2] 
        #    self.max_times_tab2 = np.array(x_data)[self.max_indices_tab2] 

        #    for i in range(self.max_count):
        #        if i < len(self.max_values_tab2):
        #            self.max_points_tab2_1[i].setData([self.max_times_tab2[i]], [self.max_values_tab2[i]])
        #            if (abs(self.max_values_tab2[i]) < 1000) and (abs(self.max_values_tab2[i]) >= 0.01):
        #                self.text_items_tab2_1[i].setHtml(f"<div style='color: red'>{self.max_values_tab2[i]:8.2f}</div>")
        #            else:
        #                self.text_items_tab2_1[i].setHtml(f"<div style='color: red'>{self.max_values_tab2[i]:8.2e}</div>")
        #            self.text_items_tab2_1[i].setPos(self.max_times_tab2[i], self.max_values_tab2[i]) 
        #        else:
        #            self.max_points_tab2_1[i].setData([], [])  # Очистка, если нет данных
        #            self.text_items_tab2_1[i].setHtml('')  # Очистка текста                


        # Получаем текущие границы отображаемого диапазона по оси X
        view_range = self.widget.getViewBox().viewRange()
        x_min, x_max = view_range[0][0], view_range[0][1]

        # Преобразуем границы в индексы данных
        data = np.array(y_data)
        x_values = np.array(x_data)

        # Находим индексы, соответствующие видимому диапазону
        visible_indices = np.where((x_values >= x_min) & (x_values <= x_max))[0]

        # Если данных в видимой области недостаточно
        if len(visible_indices) == 0:
            # Очищаем максимумы, если нет видимых данных
            for i in range(self.max_count):
                self.max_indices_tab2[i].setData([], [])
                self.text_items_tab2_1[i].setHtml('')
            return

        # Находим максимумы только в видимой области
        visible_data = data[visible_indices]
        if len(visible_data) > self.max_count:
            self.max_indices_tab2 = find_local_maxima(visible_data, num_zones=self.max_count)
        else:
            self.max_indices_tab2 = np.arange(len(visible_data))

        # Получаем максимумы и соответствующие им время
        self.max_values_tab2 = visible_data[self.max_indices_tab2]
        self.max_times_tab2 = x_values[visible_indices][self.max_indices_tab2]

        # Обновляем точки максимума и текст для первого графика
        for i in range(self.max_count):
            if i < len(self.max_values_tab2):
                self.max_points_tab2_1[i].setData([self.max_times_tab2[i]], [self.max_values_tab2[i]])
                if (abs(self.max_values_tab2[i]) < 1000) and (abs(self.max_values_tab2[i]) >= 0.01):
                    self.text_items_tab2_1[i].setHtml(f"<div style='color: lightgreen'>{self.max_values_tab2[i]:8.2f}</div>")
                else:
                    self.text_items_tab2_1[i].setHtml(f"<div style='color: lightgreen'>{self.max_values_tab2[i]:8.2e}</div>")
                self.text_items_tab2_1[i].setPos(self.max_times_tab2[i], self.max_values_tab2[i])
            else:
                self.max_points_tab2_1[i].setData([], [])  # Очистка, если нет данных
                self.text_items_tab2_1[i].setHtml('')  # Очистка текста

    def update_widget_2(self):
        if not self.Pressed:
            text=str(self.comboBox_2.currentText())
            x_data=[]
            y_data=[]
            if text == "Вакуум (торр)":
                x_data=[x.timestamp() for x in self.x_data_vacuum]
                y_data=self.y_data_vacuum
            if text == "Ток насоса (A)":
                x_data=[x.timestamp() for x in self.x_data_vacuum_A]
                y_data=self.y_data_vacuum_A
            elif text == "Напряжение":
                x_data=[x.timestamp() for x in self.x_data_voltage]
                y_data=self.y_data_voltage
            elif text == "Ток":
                x_data=[x.timestamp() for x in self.x_data_curr_fider]
                y_data=self.y_data_curr_fider
            elif text == "Падающая":
                x_data=[x.timestamp() for x in self.x_data_falling_wave]
                y_data=self.y_data_falling_wave
            elif text == "Отраженная":
                x_data=[x.timestamp() for x in self.x_data_reflected_wave]
                y_data=self.y_data_reflected_wave   
            elif text == "Фазометр":
                x_data=[x.timestamp() for x in self.x_data_phase]
                y_data=self.y_data_phase
            self.line_2.setData(x=x_data, y=y_data)

#            self.max_values_tab2 = visible_data[self.max_indices_tab2]      # danger!
#            self.max_times_tab2 = x_values[visible_indices][self.max_indices_tab2]

            # Обновляем точки максимума и текст для второго графика
            for i in range(self.max_count):
                if i < len(self.max_values_tab2):
                    corresponding_time2 = self.max_times_tab2[i]
                
                    # Найдем индекс, соответствующий времени на графике 2
                    idx2 = np.argmin(np.abs(np.array(x_data) - corresponding_time2))
                    corresponding_value2 = y_data[idx2]
                    self.max_points_tab2_2[i].setData([corresponding_time2], [corresponding_value2])
                    if (abs(corresponding_value2) < 1000) and (abs(corresponding_value2) >= 0.01):
                        self.text_items_tab2_2[i].setHtml(f"<div style='color: lightgreen'>{corresponding_value2:8.2f}</div>")
                    else:
                        self.text_items_tab2_2[i].setHtml(f"<div style='color: lightgreen'>{corresponding_value2:8.2e}</div>")              
                    self.text_items_tab2_2[i].setPos(corresponding_time2, corresponding_value2)
                else:
                    self.max_points_tab2_2[i].setData([], [])  # Очистка, если нет данных
                    self.text_items_tab2_2[i].setHtml('')  # Очистка текста                

    def update_widget_3(self):
        if not self.Pressed:
            text=str(self.comboBox_3.currentText())
            x_data=[]
            y_data=[]
            if text == "Вакуум (торр)":
                x_data=[x.timestamp() for x in self.x_data_vacuum]
                y_data=self.y_data_vacuum
            if text == "Ток насоса (A)":
                x_data=[x.timestamp() for x in self.x_data_vacuum_A]
                y_data=self.y_data_vacuum_A
            elif text == "Напряжение":
                x_data=[x.timestamp() for x in self.x_data_voltage]
                y_data=self.y_data_voltage
            elif text == "Ток":
                x_data=[x.timestamp() for x in self.x_data_curr_fider]
                y_data=self.y_data_curr_fider
            elif text == "Падающая":
                x_data=[x.timestamp() for x in self.x_data_falling_wave]
                y_data=self.y_data_falling_wave
            elif text == "Отраженная":
                x_data=[x.timestamp() for x in self.x_data_reflected_wave]
                y_data=self.y_data_reflected_wave   
            elif text == "Фазометр":
                x_data=[x.timestamp() for x in self.x_data_phase]
                y_data=self.y_data_phase
            self.line_3.setData(x=x_data, y=y_data) 

#            self.max_values_tab2 = visible_data[self.max_indices_tab2]      # danger!
#            self.max_times_tab2 = x_values[visible_indices][self.max_indices_tab2]

            # Обновляем точки максимума и текст для третьего графика
            for i in range(self.max_count):
                if i < len(self.max_values_tab2):
                    corresponding_time3 = self.max_times_tab2[i]

                    # Найдем индекс, соответствующий времени на графике 3
                    idx3 = np.argmin(np.abs(np.array(x_data) - corresponding_time3))
                    corresponding_value3 = y_data[idx3]
                    self.max_points_tab2_3[i].setData([corresponding_time3], [corresponding_value3])
                    if (abs(corresponding_value3) < 1000) and (abs(corresponding_value3) >= 0.01):
                        self.text_items_tab2_3[i].setHtml(f"<div style='color: lightgreen'>{corresponding_value3:8.2f}</div>")
                    else:
                        self.text_items_tab2_3[i].setHtml(f"<div style='color: lightgreen'>{corresponding_value3:8.2e}</div>")   
                    self.text_items_tab2_3[i].setPos(corresponding_time3, corresponding_value3)
                else:
                    self.max_points_tab2_3[i].setData([], [])  # Очистка, если нет данных
                    self.text_items_tab2_3[i].setHtml('')  # Очистка текста          

    def update_widget_4(self):
        self.line_4.setData(x=[x.timestamp() for x in self.x_data_voltage], y=self.y_data_voltage)       

    def marker_for_widget_5(self):
        if self.pushButton_28.text() == "A":
            self.pushButton_28.setText("торр")
        else:
            self.pushButton_28.setText("A")
    
    def update_widget_5(self):
        if self.pushButton_28.text() == "A":
            self.line_5.setData(x=[x.timestamp() for x in self.x_data_vacuum], y=self.y_data_vacuum)
            self.widget_5.setTitle("Vacuum (torr)", color="y", size="14pt")
            self.widget_5.enableAutoRange(axis=pg.ViewBox.YAxis) 
        else:
            self.line_5.setData(x=[x.timestamp() for x in self.x_data_vacuum], y=self.y_data_vacuum_A)
            self.widget_5.setTitle("Ipump (A)", color="y", size="14pt")
            self.widget_5.enableAutoRange(axis=pg.ViewBox.YAxis)

    def update_max_points_tab3(self):
        try:
            # Получаем текущие границы отображаемого диапазона по оси X
            view_range = self.widget_7.getViewBox().viewRange()
            x_min, x_max = view_range[0][0], view_range[0][1]

            # Преобразуем границы в индексы данных
            data = np.array(self.data_tab3_graph1)
            x_values = np.array(self.x_values)

            # Находим индексы, соответствующие видимому диапазону
            visible_indices = np.where((x_values >= x_min) & (x_values <= x_max))[0]

            # Если данных в видимой области недостаточно
            if len(visible_indices) == 0:
                # Очищаем максимумы, если нет видимых данных
                for i in range(self.max_count):
                    self.max_points_tab3_1[i].setData([], [])
                    self.text_items_tab3_1[i].setHtml('')
                return

            # Находим максимумы только в видимой области
            visible_data = data[visible_indices]
            if len(visible_data) > self.max_count:
                max_indices = find_local_maxima(visible_data, num_zones=self.max_count)
            else:
                max_indices = np.arange(len(visible_data))

            # Получаем максимумы и соответствующие им время
            max_values = visible_data[max_indices]
            max_times = x_values[visible_indices][max_indices]

            # Обновляем точки максимума и текст для первого графика
            for i in range(self.max_count):
                if i < len(max_values):
                    self.max_points_tab3_1[i].setData([max_times[i]], [max_values[i]])
                    if (abs(max_values[i]) < 1000) and (abs(max_values[i]) >= 0.01):
                        self.text_items_tab3_1[i].setHtml(f"<div style='color: lightgreen'>{max_values[i]:8.2f}</div>")
                    else:
                        self.text_items_tab3_1[i].setHtml(f"<div style='color: lightgreen'>{max_values[i]:8.2e}</div>")
                    self.text_items_tab3_1[i].setPos(max_times[i], max_values[i])
                else:
                    self.max_points_tab3_1[i].setData([], [])  # Очистка, если нет данных
                    self.text_items_tab3_1[i].setHtml('')  # Очистка текста
            # Обновляем точки максимума и текст для второго графика
            for i in range(self.max_count):
                if i < len(max_values):
                    corresponding_time2 = max_times[i]

                    # Найдем индекс, соответствующий времени на графике 2
                    idx2 = np.argmin(np.abs(np.array(self.x_values) - corresponding_time2))
                    corresponding_value2 = self.data_tab3_graph2[idx2]

                    # Обновление данных и текста
                    self.max_points_tab3_2[i].setData([corresponding_time2], [corresponding_value2])
                    if (abs(corresponding_value2) < 1000) and (abs(corresponding_value2) >= 0.01):
                        self.text_items_tab3_2[i].setHtml(f"<div style='color: lightgreen'>{corresponding_value2:8.2f}</div>")
                    else:
                        self.text_items_tab3_2[i].setHtml(f"<div style='color: lightgreen'>{corresponding_value2:8.2e}</div>")              
                    self.text_items_tab3_2[i].setPos(corresponding_time2, corresponding_value2)
                else:
                    self.max_points_tab3_2[i].setData([], [])  # Очистка, если нет данных
                    self.text_items_tab3_2[i].setHtml('')  # Очистка текста

            # Обновляем точки максимума и текст для третьего графика
            for i in range(self.max_count):
                if i < len(max_values):
                    corresponding_time3 = max_times[i]

                    # Найдем индекс, соответствующий времени на графике 3
                    idx3 = np.argmin(np.abs(np.array(self.x_values) - corresponding_time3))
                    corresponding_value3 = self.data_tab3_graph3[idx3]

                    # Обновление данных и текста
                    self.max_points_tab3_3[i].setData([corresponding_time3], [corresponding_value3])
                    if ((abs(corresponding_value3) < 1000) and (abs(corresponding_value3) >= 0.01)):
                        self.text_items_tab3_3[i].setHtml(f"<div style='color: lightgreen'>{corresponding_value3:8.2f}</div>")
                    else:
                        self.text_items_tab3_3[i].setHtml(f"<div style='color: lightgreen'>{corresponding_value3:8.2e}</div>")   
                    self.text_items_tab3_3[i].setPos(corresponding_time3, corresponding_value3)
                else:
                    self.max_points_tab3_3[i].setData([], [])  # Очистка, если нет данных
                    self.text_items_tab3_3[i].setHtml('')  # Очистка текста

            #self.widget_7.autoRange()
            #self.widget_8.autoRange() 
            #self.widget_9.autoRange() 
        except:
            pass                      

    def update_widget_6(self):
        global kvolts
        global vacuum
        global outdata
        try:
            X_data.append(float(self.lineEdit_36.text()))
            Y_data.append(vacuum/vac_coeff)
            self.line_6.setData(X_data, Y_data)
        except:
            pass
        
    def clear_widget_6(self):
        X_data.clear()
        Y_data.clear()
        
    def check(self):
        state = self.checkBox.checkState()
        if state:
            self.pushButton.setEnabled(True)
            c.write_single_coil(2, 0xFF)
        else:
            self.pushButton.setEnabled(False)
            c.write_single_coil(2, 0x00)

    def modbus_read(self):
        global vacuum
        global c
        global warn
        global input_reg
        global freeze_counter
        global vac_coeff
        global auto_enabled
        input_reg = c.read_input_registers(0x01, 1)
        try:
            tdata = input_reg[0]
        except TypeError:
            freeze_counter += 1
            self.lineEdit_45.setText(str(freeze_counter))
            self.disconnect()
            time.sleep(0.5)
            self.connect()
            time.sleep(0.5)
            input_reg = c.read_input_registers(0x01, 1)
            tdata = input_reg[0]
    #   tdata = 0xDC0C
        mantissa = tdata & 0x3FF
        power = ~((tdata>>10))&0x1F
        power = power + 1
        sign = tdata>>15
        if sign == 1:
            sign = -1
        else:
            sign = 1
        vacuum = mantissa*10**(power*sign)
        self.lineEdit_17.setText(str("{:7.1e}".format(vacuum)))
        self.lineEdit_18.setText(str("{:7.1e}".format(vacuum)))
        self.lineEdit_26.setText(str("{:7.1e}".format(vacuum/vac_coeff)))
        if (vacuum <= green_text):
            self.lineEdit_17.setStyleSheet("color: green;  background-color: white")
            self.lineEdit_17.setFont(QtGui.QFont('Consolas', 20))
            self.lineEdit_26.setStyleSheet("color: green;  background-color: white")
            self.lineEdit_26.setFont(QtGui.QFont('Consolas', 16))
            self.lineEdit_18.setStyleSheet("color: green;  background-color: white")
            self.lineEdit_18.setFont(QtGui.QFont('Consolas', 16))
        elif (vacuum >= orange_text):
            self.backtrack()
            self.lineEdit_17.setStyleSheet("color: magenta;  background-color: white")
            self.lineEdit_17.setFont(QtGui.QFont('Consolas', 20))
            self.lineEdit_26.setStyleSheet("color: magenta;  background-color: white")
            self.lineEdit_26.setFont(QtGui.QFont('Consolas', 16))
            self.lineEdit_18.setStyleSheet("color: magenta;  background-color: white")
            self.lineEdit_18.setFont(QtGui.QFont('Consolas', 16))
        elif (vacuum >= red_text):
            self.auto_off()
            warn = 1
            self.lineEdit_17.setStyleSheet("color: red;  background-color: white")
            self.lineEdit_17.setFont(QtGui.QFont('Consolas', 20))
            self.lineEdit_26.setStyleSheet("color: red;  background-color: white")
            self.lineEdit_26.setFont(QtGui.QFont('Consolas', 16))
            self.lineEdit_18.setStyleSheet("color: red;  background-color: white")
            self.lineEdit_18.setFont(QtGui.QFont('Consolas', 16))
        else:
            self.lineEdit_17.setStyleSheet("color: black;  background-color: white")
            self.lineEdit_17.setFont(QtGui.QFont('Consolas', 20))
            self.lineEdit_26.setStyleSheet("color: black;  background-color: white")
            self.lineEdit_26.setFont(QtGui.QFont('Consolas', 16))
            self.lineEdit_18.setStyleSheet("color: red;  background-color: white")
            self.lineEdit_18.setFont(QtGui.QFont('Consolas', 16))
            if (warn*auto_enabled) and (auto_enabled==1):
                self.auto_on()
                warn = 0

    def start_mod(self):
        digital_output.StartTask()
        ddata[0] = 0
        ddata[1] = 1 
        digital_output.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata,None,None)
        time.sleep(0.5)
        ddata[0] = 0
        ddata[1] = 0
        digital_output.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata,None,None)
        digital_output.StopTask()    
    
    def stop_mod(self):
        digital_output.StartTask()
        ddata[0] = 1
        ddata[1] = 0 
        digital_output.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata,None,None)
        time.sleep(0.5)
        ddata[0] = 0
        ddata[1] = 0
        digital_output.WriteDigitalLines(1,1,10.0,daqmx.DAQmx_Val_GroupByChannel,ddata,None,None)
        digital_output.StopTask()    
        
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = Ui()
    sys.exit(app.exec_())
