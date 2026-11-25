# Сборка exe:  pyinstaller training.spec   ->  dist/Training/Training.exe
# (собирать на Windows: exe получается под ту систему, на которой собирали)
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs, copy_metadata

a = Analysis(
    ["main.py"],
    # иконка окна + файлы и «паспорт» Taurus (он ищет свои модули по нему)
    datas=[("ui/app.ico", "ui")] + collect_data_files("taurus") + copy_metadata("taurus") + copy_metadata("pint")
          + collect_data_files("epics"),   # EPICS: библиотека Channel Access (ca.dll, Com.dll) внутри pyepics
    # PyTango и Taurus подгружаются по ходу работы - перечисляем явно
    binaries=collect_dynamic_libs("epics"),   # .dll/.so библиотеки CA - иначе PyInstaller их пропускает
    hiddenimports=["tango", "epics"] + collect_submodules("taurus.core") + collect_submodules("taurus.qt.qtgui.display"),
    excludes=["PyQt5.QtWebEngineWidgets", "PyQt5.QtWebEngineCore", "matplotlib", "scipy"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Training",
    icon="ui/app.ico",                     # иконка exe
    console=False,                         # без чёрного окна консоли
)
coll = COLLECT(exe, a.binaries, a.datas, name="Training")
