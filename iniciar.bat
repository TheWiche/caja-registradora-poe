@echo off
rem Inicia el Sistema de Caja Registradora Didáctica sin ventana de consola.
cd /d "%~dp0"
start "" pythonw -m caja.main
