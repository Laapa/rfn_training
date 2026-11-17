@echo off
chcp 65001 >nul
rem Сборка Training.exe (Windows). Результат: dist\Training\Training.exe
rem Собирается тем же окружением .venv, в котором работает программа (python main.py).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Нет окружения .venv. Сначала:  py -3.12 -m venv .venv  и  .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
.venv\Scripts\python -c "import tango, taurus, PyQt5, pyqtgraph" || (
    echo В .venv не хватает пакетов. Сначала:  .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
.venv\Scripts\python -m PyInstaller --version >nul 2>&1 || .venv\Scripts\python -m pip install pyinstaller || (
    echo Не удалось поставить PyInstaller - смотри ошибку выше
    pause
    exit /b 1
)
.venv\Scripts\python -m PyInstaller --noconfirm training.spec || (
    echo Сборка не удалась - смотри ошибку выше
    pause
    exit /b 1
)
echo.
echo Готово: dist\Training\Training.exe  (папку dist\Training можно копировать целиком)
pause
