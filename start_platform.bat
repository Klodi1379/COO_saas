@echo off
REM Windows batch script to start the COO SaaS platform

echo Starting COO SaaS Platform...
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Error: Virtual environment not found!
    echo Please run setup_env.bat first.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check for .env file
if not exist ".env" (
    echo Warning: .env file not found!
    echo Creating default .env file...
    copy .env.example .env >nul 2>&1
)

REM Apply migrations if needed
echo Checking for database updates...
python manage.py migrate --check >nul 2>&1
if errorlevel 1 (
    echo Applying database migrations...
    python manage.py migrate
)

REM Create demo user if needed
echo Checking demo user setup...
python create_demo_user.py

REM Start the development server
echo.
echo ========================================
echo COO SaaS Platform Development Server
echo ========================================
echo.
echo Server will start at: http://127.0.0.1:8000
echo Admin panel at: http://127.0.0.1:8000/admin
echo.
echo Demo credentials:
echo   Username: admin
echo   Password: admin123
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

python manage.py runserver 8000

echo.
echo Server stopped.
pause
