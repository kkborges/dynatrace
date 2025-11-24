@echo off
REM Dynatrace Metrics Dashboard Starter for Windows

color 02
echo.
echo ========================================
echo Dynatrace Metrics Dashboard Starter
echo ========================================
echo.

REM Check if .env file exists
if not exist ".env" (
    echo WARNING: .env file not found!
    echo Creating .env from .env.example...
    copy .env.example .env
    echo.
    echo Please edit .env with your Dynatrace credentials and run this script again.
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if Node is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if npm is installed
npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: npm is not installed or not in PATH
    pause
    exit /b 1
)

echo OK: Python, Node.js, and npm are installed
echo.

REM Install backend dependencies if needed
if not exist "backend\venv" (
    echo Installing backend dependencies...
    cd backend
    pip install -q -r requirements.txt
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install backend dependencies
        pause
        exit /b 1
    )
    cd ..
    echo OK: Backend dependencies installed
    echo.
)

REM Install frontend dependencies if needed
if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    cd frontend
    call npm install -q
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install frontend dependencies
        pause
        exit /b 1
    )
    cd ..
    echo OK: Frontend dependencies installed
    echo.
)

echo ========================================
echo Starting Application
echo ========================================
echo.
echo Starting backend server...
echo URL: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.

REM Start backend in new window
cd backend
start "Dynatrace Backend" /WAIT python main.py
cd ..
