@echo off
chcp 65001 >nul
rem Фейковый EPICS-стенд: IOC на caproto с резонаторами RF2, RF3, RF4 (только на этом компьютере).
rem Работает в окружении программы .venv (caproto - чистый Python, ставится сам при первом запуске).
cd /d "%~dp0\.."
if not exist .venv\Scripts\python.exe (
    echo Нет окружения .venv. Сначала:  py -3.12 -m venv .venv  и  .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
.venv\Scripts\python -c "import caproto" 2>nul || .venv\Scripts\python -m pip install -r fake_server\requirements_fake_epics.txt || (
    echo Не удалось поставить caproto - смотри ошибку выше
    pause
    exit /b 1
)
.venv\Scripts\python fake_server\fake_epics.py %*
pause
