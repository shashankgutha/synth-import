@echo off
echo ========================================
echo Kibana Synthetics Export - Local Setup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ and try again
    pause
    exit /b 1
)

echo Python is installed:
python --version
echo.

REM Install dependencies
echo Installing Python dependencies...
pip install -r .github\scripts\requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed successfully!
echo.

REM Check environment variables
if "%KIBANA_URL%"=="" (
    echo WARNING: KIBANA_URL environment variable is not set
    echo.
    set /p KIBANA_URL_INPUT="Enter your Kibana URL (e.g., https://your-kibana.example.com): "
    set KIBANA_URL=%KIBANA_URL_INPUT%
)

if "%KIBANA_API_KEY%"=="" (
    echo WARNING: KIBANA_API_KEY environment variable is not set
    echo.
    set /p KIBANA_API_KEY_INPUT="Enter your Kibana API Key: "
    set KIBANA_API_KEY=%KIBANA_API_KEY_INPUT%
)

echo.
echo Current configuration:
echo KIBANA_URL: %KIBANA_URL%
echo KIBANA_API_KEY: [HIDDEN]
echo.

echo ========================================
echo Running local test...
echo ========================================

REM Set environment variables for this session and run the test
set KIBANA_URL=%KIBANA_URL%
set KIBANA_API_KEY=%KIBANA_API_KEY%
python test-local.py

echo.
echo ========================================
echo Test completed!
echo ========================================
pause