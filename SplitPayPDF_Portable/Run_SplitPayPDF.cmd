@echo off
rem ============================================================
rem  SplitPayPDF portable launcher
rem  Runs the app with the bundled Python runtime.
rem  No installation, no admin rights, no internet required.
rem ============================================================
setlocal
title SplitPayPDF
set "ROOT=%~dp0"

if not exist "%ROOT%python\python.exe" (
    echo [ERROR] Bundled Python runtime not found:
    echo         %ROOT%python\python.exe
    echo.
    echo Make sure you copied the ENTIRE SplitPayPDF_Portable folder,
    echo including the "python" subfolder, and that you are not running
    echo this file from inside a ZIP archive.
    echo.
    pause
    exit /b 1
)

if not exist "%ROOT%app\SplitPayPDF.py" (
    echo [ERROR] Application file not found:
    echo         %ROOT%app\SplitPayPDF.py
    echo.
    echo Make sure you copied the ENTIRE SplitPayPDF_Portable folder,
    echo including the "app" subfolder.
    echo.
    pause
    exit /b 1
)

rem Point the bundled runtime at its own Tcl/Tk (needed for the GUI).
for /d %%i in ("%ROOT%python\tcl\tcl8*") do set "TCL_LIBRARY=%%i"
for /d %%i in ("%ROOT%python\tcl\tk8*") do set "TK_LIBRARY=%%i"

echo Starting SplitPayPDF... (keep this window open while the app runs)
"%ROOT%python\python.exe" "%ROOT%app\SplitPayPDF.py"

if errorlevel 1 (
    echo.
    echo [ERROR] SplitPayPDF exited with an error. Exit code: %errorlevel%
    echo The message above this line usually explains the cause.
    echo App log: %APPDATA%\SplitPayPDF\app_log.txt
    echo.
    pause
    exit /b %errorlevel%
)

endlocal
