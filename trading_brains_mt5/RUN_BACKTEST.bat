@echo off
setlocal
call venv\Scripts\activate
python -m src.main backtest --months 3
endlocal
