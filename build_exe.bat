@echo off
rem Сборка Training.exe (Windows). Результат: dist\Training\Training.exe
pip install pyinstaller
pyinstaller --noconfirm training.spec
echo.
echo Готово: dist\Training\Training.exe  (папку dist\Training можно копировать целиком)
pause
