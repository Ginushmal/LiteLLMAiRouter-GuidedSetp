@echo off
rem One-click refresh: fetch today's provider data, re-score it, and open the
rem tier report in the default browser. Never touches LiteLLM (no populate).
rem Fails loudly: on any error the window stays open and no report is shown,
rem so a stale report is never presented as current.
cd /d "%~dp0"
if exist "certs\ca-bundle.pem" set "SSL_CERT_FILE=%~dp0certs\ca-bundle.pem"
uv run model-pipeline refresh
if errorlevel 1 (
  echo.
  echo refresh FAILED - not opening the report. Fix the error above and retry.
  pause
  exit /b 1
)
start "" "output\tier-report.html"
