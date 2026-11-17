@echo off
chcp 65001 >nul
rem Фейковый стенд: своя база Tango + устройства rf2/1e2, rf3/1e3, rf4/1e4.
rem Окружение .venv_fake (PyTango 10) создаётся при первом запуске само.
cd /d "%~dp0\.."

rem окружение уже есть и в нём всё на месте - сразу запускаем
if exist .venv_fake\Scripts\python.exe (
    .venv_fake\Scripts\python -c "import tango, gevent" 2>nul && goto run
)

echo Создаю окружение .venv_fake (PyTango 10) ...
if exist .venv_fake rmdir /s /q .venv_fake
py -3.12 -m venv .venv_fake || goto fail
rem numpy берём готовый из .venv программы, чтобы не скачивать (в сети ИЯФ pip его не находит)
if exist .venv\Lib\site-packages\numpy (
    echo Копирую numpy из .venv ...
    xcopy /E /I /Q /Y .venv\Lib\site-packages\numpy .venv_fake\Lib\site-packages\numpy >nul
    if exist .venv\Lib\site-packages\numpy.libs xcopy /E /I /Q /Y .venv\Lib\site-packages\numpy.libs .venv_fake\Lib\site-packages\numpy.libs >nul
    for /d %%d in (.venv\Lib\site-packages\numpy-*.dist-info) do xcopy /E /I /Q /Y "%%d" ".venv_fake\Lib\site-packages\%%~nxd" >nul
)
.venv_fake\Scripts\python -m pip install --timeout 60 --retries 5 -r fake_server\requirements_fake.txt || goto fail

:run
.venv_fake\Scripts\python fake_server\fake_rf.py %*
pause
exit /b

:fail
echo.
echo Не получилось поставить PyTango 10 в .venv_fake (смотри ошибку выше).
echo Недоделанное окружение удаляю - следующий запуск попробует заново.
if exist .venv_fake rmdir /s /q .venv_fake
pause
exit /b 1
