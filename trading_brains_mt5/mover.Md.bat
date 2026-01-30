@echo off
setlocal EnableExtensions

echo Digite o caminho completo da pasta onde estao os arquivos .md:
set /p PASTA_ORIGEM=

if not exist "%PASTA_ORIGEM%" (
    echo Pasta nao encontrada.
    pause
    exit /b
)

cd /d "%PASTA_ORIGEM%"

if not exist "Filestxt" (
    mkdir "Files"
)

echo Movendo arquivos .md apenas desta pasta...

for %%F in (*.txt) do (
    move "%%F" "Filestxt\"
)

echo.
echo Concluido!
pause
