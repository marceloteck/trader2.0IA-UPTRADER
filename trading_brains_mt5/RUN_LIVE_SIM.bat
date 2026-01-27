@echo off
setlocal
call venv\Scripts\activate
python -m src.main live-sim
endlocal
