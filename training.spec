# Сборка exe:  pyinstaller training.spec   ->  dist/Training/Training.exe
# (собирать на Windows: exe получается под ту систему, на которой собирали)
a = Analysis(
    ["main.py"],
    datas=[("ui/app.ico", "ui")],          # иконка окна внутри сборки
    hiddenimports=["tango"],               # PyTango подгружается только для type "tango"
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
