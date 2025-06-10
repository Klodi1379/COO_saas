@echo off
echo.
echo ======================================
echo     COO Platform - Reset Demo Data
echo ======================================
echo.

REM Activate virtual environment
echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat

REM Reset and repopulate demo data
echo [2/3] Resetting and repopulating demo data...
python manage.py populate_demo_data --reset

REM Apply migrations if needed
echo [3/3] Ensuring database is up to date...
python manage.py migrate --noinput

echo.
echo ======================================
echo     Demo Data Reset Complete!
echo ======================================
echo.
echo You can now start the server with:
echo   start_server.bat
echo.
echo Or manually:
echo   python manage.py runserver 0.0.0.0:49000
echo.
pause