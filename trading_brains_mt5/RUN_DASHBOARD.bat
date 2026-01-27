@echo off
setlocal
call venv\Scripts\activate
python -m src.main dashboard
start http://localhost:8000
endlocal
