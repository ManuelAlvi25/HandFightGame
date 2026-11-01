@echo off
rem Inicia Gesture Fighter. Crea el entorno virtual e instala dependencias la primera vez.
rem Argumentos opcionales se pasan al juego, p. ej.:  run.bat --no-camera   run.bat --demo
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual con Python 3.11...
    py -3.11 -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se encontro Python 3.11. Instalelo desde https://www.python.org/downloads/release/python-3119/
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Fallo la instalacion de dependencias.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" main.py %*
if errorlevel 1 pause
