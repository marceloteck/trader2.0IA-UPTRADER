@echo off
REM RUN_LIVE_SIM.bat - Run system in paper trading mode
REM Safe mode for testing live configuration without real money

echo.
echo ====================================================
echo LIVE SIMULATOR - Paper Trading Mode (No Risk)
echo ====================================================
echo.
echo This mode allows you to:
echo - Test the live trading pipeline
echo - Verify MT5 connection
echo - Check order execution (filled at simulated prices)
echo - Monitor position sizing and risk management
echo - WITHOUT exposing real money
echo.

REM Verify environment
if not exist .env (
    echo ERROR: .env file not found!
    echo Please copy .env.example to .env and configure.
    pause
    exit /b 1
)

REM Set LIVE_MODE to SIM
set LIVE_MODE=SIM

echo Configuration:
echo - LIVE_MODE=SIM (Paper Trading)
echo - REQUIRE_LIVE_OK_FILE=true (ignored in SIM mode)
echo.

REM Run the system
echo Starting Live Simulator...
setlocal
call venv\Scripts\activate
python -m src.main live-sim
endlocal

if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Live simulator failed with exit code %ERRORLEVEL%
    pause
)
