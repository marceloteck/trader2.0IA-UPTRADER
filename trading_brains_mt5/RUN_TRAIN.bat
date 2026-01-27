@echo off
setlocal
call venv\Scripts\activate
python -m src.main train --replay 3
endlocal
