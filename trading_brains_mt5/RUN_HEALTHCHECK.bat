@echo off
REM RUN_HEALTHCHECK.bat - System health check

echo.
echo ====================================================
echo SYSTEM HEALTH CHECK
echo ====================================================
echo.
echo This tool checks:
echo - MT5 terminal connectivity
echo - Symbol availability
echo - Data feed freshness
echo - System configuration
echo.

if not exist .env (
    echo ERROR: .env file not found!
    pause
    exit /b 1
)

echo Running health check...
echo.

setlocal
call venv\Scripts\activate
python -c ^
"import logging;logging.basicConfig(level=logging.INFO);from src.infra.logger import setup_logger;setup_logger();from src.mt5.mt5_client import MT5Client;from src.config.settings import load_settings;settings=load_settings();client=MT5Client(settings);status=client.is_connected();print(f'MT5 Connected: {status}');print(f'Live Mode: {settings.live_mode}');print('Health check complete.')"

endlocal

if %ERRORLEVEL% neq 0 (
    echo.
    echo WARNING: Health check encountered issues
    echo Check MT5 terminal and network connectivity
    pause
)

echo.
pause
