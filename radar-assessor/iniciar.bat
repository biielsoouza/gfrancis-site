@echo off
chcp 65001 >nul
title Radar do Assessor
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale em https://www.python.org/downloads/ e marque "Add Python to PATH".
  pause
  exit /b 1
)

if not exist ".venv" (
  echo Preparando o ambiente pela primeira vez, aguarde...
  python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)

echo Abrindo o Radar do Assessor no navegador...
echo Para encerrar, feche esta janela.
python app.py
