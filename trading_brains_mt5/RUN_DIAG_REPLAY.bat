@echo off
REM RUN_DIAG_REPLAY.bat - Diagnostics and decision replay

echo.
echo ====================================================
echo DIAGNOSTICS & REPLAY - Post-Failure Analysis
echo ====================================================
echo.
echo This tool helps diagnose issues after a failure or crash.
echo It replays recent trading decisions and compares outcomes.
echo.

if not exist .env (
    echo ERROR: .env file not found!
    pause
    exit /b 1
)

echo Running diagnostic replay on last 200 decisions...
echo (This may take a few moments)
echo.

setlocal
call venv\Scripts\activate
python -m src.main replay-last --n 200
endlocal

if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Replay failed
    pause
)

echo.
echo Diagnostic report saved to ./data/logs/replay_report.json
echo Review this file for divergences and issues.
echo.
pause
