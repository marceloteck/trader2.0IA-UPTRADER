@echo off
REM RUN_LIVE_REAL.bat - Run system in REAL LIVE TRADING MODE
REM *** WARNING: THIS WILL TRADE WITH REAL MONEY ***

echo.
echo ====================================================
echo          LIVE REAL TRADING MODE - CAUTION!
echo ====================================================
echo.
echo   *** THIS WILL EXECUTE TRADES WITH REAL MONEY ***
echo.
echo SAFETY REQUIREMENTS BEFORE RUNNING:
echo.
echo 1. A file named "LIVE_OK.txt" must exist in ./data/ folder
echo    (Create it manually to confirm you understand the risks)
echo.
echo 2. Your .env file must be properly configured:
echo    - LIVE_MODE=REAL
echo    - LIVE_CONFIRM_KEY=correct_key
echo    - All risk limits configured
echo.
echo 3. You must have tested LIVE_SIM thoroughly
echo    (Run RUN_LIVE_SIM.bat first)
echo.
echo 4. MT5 terminal must be connected and running
echo    (Check: Tools > Experts > Journal for MT5 status)
echo.

REM Verify LIVE_OK.txt exists
if not exist data\LIVE_OK.txt (
    echo ERROR: ./data/LIVE_OK.txt NOT FOUND!
    echo.
    echo To enable real trading:
    echo 1. Create the file: mkdir data (if it doesn't exist)
    echo 2. Create: data\LIVE_OK.txt (empty file is fine)
    echo 3. This is your manual confirmation of understanding the risks
    echo.
    pause
    exit /b 1
)

REM Verify .env exists
if not exist .env (
    echo ERROR: .env file not found!
    echo Please copy .env.example to .env and configure.
    pause
    exit /b 1
)

REM Warn one more time
echo.
echo *** FINAL WARNING ***
echo.
echo You are about to run LIVE REAL TRADING.
echo If something goes wrong, REAL MONEY WILL BE LOST.
echo.
echo Do you want to continue? (Press Ctrl+C to abort, or Enter to proceed)
echo.
pause

echo.
echo Checking system health...
python -c "from src.config.settings import load_settings; s = load_settings(); print(f'LIVE_MODE: {s.live_mode}'); assert s.live_mode.upper() == 'REAL', 'LIVE_MODE is not REAL'"

if %ERRORLEVEL% neq 0 (
    echo ERROR: System health check failed!
    pause
    exit /b 1
)

echo.
echo Starting LIVE REAL TRADING...
echo Execution history will be logged to ./data/logs/
echo.

set LIVE_MODE=REAL
setlocal
call venv\Scripts\activate
python -m src.main live-real
endlocal

if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Live trading failed with exit code %ERRORLEVEL%
    echo Check logs in ./data/logs/ for details
    pause
)
