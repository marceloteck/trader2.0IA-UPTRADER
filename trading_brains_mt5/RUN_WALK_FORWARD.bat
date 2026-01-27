@echo off
setlocal
call venv\Scripts\activate
python -m src.main walk-forward
endlocal
