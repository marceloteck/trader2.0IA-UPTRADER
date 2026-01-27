@echo off
setlocal
if not exist venv (
  python -m venv venv
)
call venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
if not exist data\db mkdir data\db
if not exist data\exports\reports mkdir data\exports\reports
if not exist data\exports\models mkdir data\exports\models
if not exist data\cache\mt5 mkdir data\cache\mt5
if not exist data\logs mkdir data\logs
python -m src.main init-db
endlocal
