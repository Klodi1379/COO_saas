@echo off
echo Creating virtual environment for COO SaaS Platform...

REM Create virtual environment
python -m venv venv

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Upgrade pip
python -m pip install --upgrade pip

REM Install requirements
pip install -r requirements.txt

echo.
echo Virtual environment created successfully!
echo.
echo To activate the environment, run: venv\Scripts\activate.bat
echo To deactivate, run: deactivate
echo.
echo Next steps:
echo 1. Activate the environment: venv\Scripts\activate.bat
echo 2. Run: python manage.py migrate
echo 3. Create superuser: python manage.py createsuperuser
echo 4. Run server: python manage.py runserver
