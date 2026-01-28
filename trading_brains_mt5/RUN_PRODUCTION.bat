@echo off
REM ════════════════════════════════════════════════════════════════════════════
REM RUN_PRODUCTION.bat - Production mode with automatic restarts
REM ════════════════════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion

cls
echo.
echo ╔════════════════════════════════════════════════════════════════════════╗
echo ║        TRADING BRAINS MT5 - PRODUCTION MODE                           ║
echo ║                        VERSION 5.0.0                                  ║
echo ╚════════════════════════════════════════════════════════════════════════╝
echo.

if not exist venv (
    echo ERROR: Virtual environment not found. Run INSTALL.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

REM Check configuration
if not exist .env (
    echo ERROR: .env not found. Run SETUP_WIZARD.bat first.
    pause
    exit /b 1
)

REM Determine mode
set MODE=live-sim
echo Checking configuration...

for /f "tokens=1,* delims==" %%A in (.env) do (
    if "%%A"=="LIVE_MODE" (
        if "%%B"=="REAL" (
            set MODE=live-real
        )
    )
)

echo Mode: %MODE%
echo.

if "%MODE%"=="live-real" (
    echo ⚠️  LIVE TRADING MODE DETECTED
    echo.
    if not exist data\LIVE_OK.txt (
        echo ❌ ERROR: ./data/LIVE_OK.txt not found
        echo.
        echo To enable live trading:
        echo 1. Create file: data\LIVE_OK.txt
        echo 2. Verify .env configuration
        echo 3. Run RUN_HEALTHCHECK.bat
        echo 4. Run this script again
        echo.
        pause
        exit /b 1
    )
    echo ✅ Safety file found. Proceeding with live trading.
)

echo.
echo Starting production loop (restarts enabled)...
echo Press Ctrl+C to stop
echo.

set RESTART_COUNT=0

:LOOP

echo.
echo [%date% %time%] Starting trading engine (restart #%RESTART_COUNT%)...
python -m src.main %MODE%

set EXIT_CODE=!ERRORLEVEL!

if !EXIT_CODE! equ 0 (
    echo.
    echo ✅ Clean exit detected. Stopping.
    exit /b 0
)

echo.
echo ⚠️  Process exited with code !EXIT_CODE!. Restarting in 10 seconds...
echo Press Ctrl+C to stop automatic restarts.
echo.

set /a RESTART_COUNT+=1

REM Wait 10 seconds
timeout /t 10 /nobreak

goto LOOP
