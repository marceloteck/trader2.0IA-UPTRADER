@echo off
REM ════════════════════════════════════════════════════════════════════════════
REM RUN_MAINTENANCE.bat - Database and system maintenance
REM ════════════════════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion

cls
echo.
echo ╔════════════════════════════════════════════════════════════════════════╗
echo ║          TRADING BRAINS MT5 - MAINTENANCE                             ║
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
echo 🔧 MAINTENANCE TASKS
echo ═══════════════════════
echo.
echo 1. Database integrity check
echo 2. Database backup
echo 3. Database optimization (VACUUM)
echo 4. Log rotation
echo 5. Generate daily report
echo 6. Generate weekly report
echo 7. All of above
echo.

set /p CHOICE="Select task (1-7): "

if "%CHOICE%"=="1" goto INTEGRITY
if "%CHOICE%"=="2" goto BACKUP
if "%CHOICE%"=="3" goto VACUUM
if "%CHOICE%"=="4" goto LOGS
if "%CHOICE%"=="5" goto DAILY
if "%CHOICE%"=="6" goto WEEKLY
if "%CHOICE%"=="7" goto ALL
echo Invalid choice
exit /b 1

:ALL
echo.
echo Running all maintenance tasks...
goto INTEGRITY

:INTEGRITY
echo.
echo 🔍 Database Integrity Check...
python -m src.main integrity-check
if errorlevel 1 (
    echo ❌ Integrity check failed!
    pause
    exit /b 1
)
echo ✅ Database OK
if "%CHOICE%"=="1" goto END
goto BACKUP

:BACKUP
echo.
echo 💾 Database Backup...
python -m src.main backup-db
echo ✅ Backup completed
if "%CHOICE%"=="2" goto END
goto VACUUM

:VACUUM
echo.
echo 🗜️  Database Optimization...
python -m src.main maintenance
echo ✅ Optimization completed
if "%CHOICE%"=="3" goto END
goto LOGS

:LOGS
echo.
echo 📋 Log Rotation...
if exist data\logs (
    REM Simple rotation: keep last 10 files
    for /f "skip=10 tokens=*" %%f in ('dir /b /o-d data\logs\*.log 2^>nul') do (
        del /q "data\logs\%%f" 2>nul
    )
    echo ✅ Old logs removed
)
if "%CHOICE%"=="4" goto END
goto DAILY

:DAILY
echo.
echo 📊 Generating Daily Report...
python -m src.main daily-report
echo ✅ Daily report generated
if "%CHOICE%"=="5" goto END
goto WEEKLY

:WEEKLY
echo.
echo 📈 Generating Weekly Report...
python -m src.main weekly-report
echo ✅ Weekly report generated

:END
echo.
echo ✅ Maintenance complete!
echo.
pause
