@echo off
cd /d "%~dp0"
echo Запуск WowAlerter в фоновом режиме...
start "" ".\.venv\Scripts\pythonw.exe" "game_alerter.py"
exit
