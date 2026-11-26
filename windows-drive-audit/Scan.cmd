@echo off
setlocal
where py.exe >nul 2>&1
if not errorlevel 1 (
    py -3 -B "%~dp0scripts\drive_audit.py" %*
) else (
    python -B "%~dp0scripts\drive_audit.py" %*
)
set "audit_exit=%errorlevel%"
if not "%audit_exit%"=="0" (
    echo Run the portable WindowsDriveAudit.exe or install Python 3.12+ for the source version.
    pause
)
exit /b %audit_exit%
