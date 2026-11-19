@echo off
rem Ustaz Portfolio: update/start script. Double-click or run: start.bat
cd /d "%~dp0"
if exist secrets.bat call secrets.bat
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
echo [1/5] Installing requirements...
python -m pip install -r requirements.txt
echo [2/5] Creating migrations...
python manage.py makemigrations portfolio
echo [3/5] Applying migrations...
python manage.py migrate
echo [4/5] Loading categories (safe to repeat)...
python manage.py seed
echo [5/5] Starting server: http://127.0.0.1:8000/
python manage.py runserver
pause
