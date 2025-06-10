@echo off
echo.
echo ======================================
echo     COO Platform - Quick Start
echo ======================================
echo.

REM Activate virtual environment
echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat

REM Apply any pending migrations
echo [2/3] Applying database migrations...
python manage.py migrate --noinput

REM Start the development server
echo [3/3] Starting development server...
echo.
echo ======================================
echo     Server Starting...
echo ======================================
echo.
echo Dashboard: http://127.0.0.1:49000/dashboard/
echo KPIs:      http://127.0.0.1:49000/kpis/
echo Projects:  http://127.0.0.1:49000/projects/
echo Admin:     http://127.0.0.1:49000/admin/
echo.
echo Demo Users: *@techcorp.demo / demo123
echo Admin User: klodjanvathi@gmail.com
echo.
echo Press Ctrl+C to stop the server
echo ======================================
echo.

python manage.py runserver 0.0.0.0:49000