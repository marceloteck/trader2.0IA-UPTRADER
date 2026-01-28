@echo off
REM ════════════════════════════════════════════════════════════════════════════
REM RUN_TESTS.bat - Run test suite
REM ════════════════════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion

cls
echo.
echo ╔════════════════════════════════════════════════════════════════════════╗
echo ║          TRADING BRAINS MT5 - TEST SUITE                              ║
echo ║                        VERSION 5.0.0                                  ║
echo ╚════════════════════════════════════════════════════════════════════════╝
echo.

if not exist venv (
    echo ERROR: Virtual environment not found. Run INSTALL.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo.
echo 🧪 Running tests...
echo.

python -m pytest tests/ -v --tb=short

if errorlevel 1 (
    echo.
    echo ❌ Some tests failed!
    pause
    exit /b 1
)

echo.
echo ✅ All tests passed!
echo.

pause
