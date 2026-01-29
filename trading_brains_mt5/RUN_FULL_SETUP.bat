@echo off
REM ════════════════════════════════════════════════════════════════════════════
REM RUN_FULL_SETUP.bat - Instalação completa + testes + healthcheck
REM ════════════════════════════════════════════════════════════════════════════

call INSTALL.bat
if errorlevel 1 (
  echo ❌ Falha na instalação.
  pause
  exit /b 1
)

call RUN_TESTS.bat
if errorlevel 1 (
  echo ❌ Testes falharam.
  pause
  exit /b 1
)

call RUN_HEALTHCHECK.bat
if errorlevel 1 (
  echo ❌ Healthcheck falhou.
  pause
  exit /b 1
)

echo ✅ Setup completo finalizado.
pause
