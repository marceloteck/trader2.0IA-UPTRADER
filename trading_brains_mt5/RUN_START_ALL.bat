@echo off
REM ════════════════════════════════════════════════════════════════════════════
REM RUN_START_ALL.bat - Inicia dashboard + live-sim automaticamente
REM ════════════════════════════════════════════════════════════════════════════

if not exist venv (
  echo ERROR: Ambiente virtual não encontrado. Rode INSTALL.bat primeiro.
  pause
  exit /b 1
)

call venv\Scripts\activate.bat

echo ✅ Iniciando Dashboard e Live SIM...
echo    (Para parar, crie data\STOP.txt)

start "Trading Brains - Dashboard" cmd /k RUN_DASHBOARD.bat
start "Trading Brains - Live SIM" cmd /k RUN_LIVE_SIM.bat

echo ✅ Serviços iniciados.
pause
