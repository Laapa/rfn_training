@echo off
chcp 65001 >nul
rem Фейковый стенд: своя база Tango + устройства rf2/1e2, rf3/1e3, rf4/1e4.
rem Окружение .venv_fake (PyTango 10) создаётся при первом запуске само.
cd /d "%~dp0\.."
if not exist .venv_fake (
    echo Первый запуск: создаю окружение .venv_fake ...
    py -3.12 -m venv .venv_fake
    .venv_fake\Scripts\python -m pip install --upgrade pip
    .venv_fake\Scripts\pip install -r fake_server\requirements_fake.txt
)
.venv_fake\Scripts\python fake_server\fake_rf.py %*
pause
