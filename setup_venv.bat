@echo off
REM setup_venv.bat
REM Interactive script to create a virtual environment for Super Secretary (Windows)
REM Detects available tools and guides user through setup

setlocal enabledelayedexpansion

echo ==========================================
echo Virtual Environment Setup
echo Super Secretary
echo ==========================================
echo.

REM Project configuration
set PROJECT_NAME=super-secretary
set PYTHON_VERSION=3.10.0
set VENV_DIR=venv

REM Detect available tools
echo Detecting available Python environment tools...
echo.

REM Check for Python
set PYTHON_AVAILABLE=false
set PYTHON_CMD=

python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PYTHON_CMD=python
    set PYTHON_AVAILABLE=true
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION_STR=%%i
    echo [+] Python detected: !PYTHON_VERSION_STR!
) else (
    python3 --version >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set PYTHON_CMD=python3
        set PYTHON_AVAILABLE=true
        for /f "tokens=*" %%i in ('python3 --version 2^>^&1') do set PYTHON_VERSION_STR=%%i
        echo [+] Python detected: !PYTHON_VERSION_STR!
    )
)

if "%PYTHON_AVAILABLE%"=="false" (
    echo [X] No Python installation found!
    echo.
    echo Please install Python 3.10 or higher from:
    echo     https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM Check if venv module is available
%PYTHON_CMD% -m venv --help >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] Python venv module not available!
    echo.
    echo Please ensure Python is properly installed with the venv module.
    echo.
    pause
    exit /b 1
)

echo.
echo Setting up with Python venv...
echo.

REM Check if venv directory already exists
if exist "%VENV_DIR%" (
    echo [!] Virtual environment directory '%VENV_DIR%' already exists.
    set /p RECREATE="Would you like to delete and recreate it? [y/N]: "
    
    if /i "!RECREATE!"=="y" (
        echo Deleting existing virtual environment...
        rmdir /s /q "%VENV_DIR%"
        set SKIP_CREATION=false
    ) else (
        echo Using existing virtual environment.
        set SKIP_CREATION=true
    )
) else (
    set SKIP_CREATION=false
)

REM Create virtual environment
if "!SKIP_CREATION!"=="false" (
    echo Creating virtual environment in '%VENV_DIR%'...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    
    if %ERRORLEVEL% NEQ 0 (
        echo [X] Failed to create virtual environment!
        pause
        exit /b 1
    )
)

echo.
echo [+] Virtual environment created successfully!
echo.
echo ==========================================
echo To activate the virtual environment:
echo ==========================================
echo.
echo     %VENV_DIR%\Scripts\activate
echo.
echo ==========================================
echo To deactivate:
echo ==========================================
echo.
echo     deactivate
echo.
echo ==========================================
echo Next Steps:
echo ==========================================
echo.
echo 1. Activate the virtual environment (see command above)
echo.
echo 2. Install dependencies:
echo      pip install -r requirements.txt
echo    Or:
echo      pip install boto3 python-docx python-dotenv PyYAML
echo.
echo 3. Confirm AWS credential setup:
echo    - Recommended: install/configure go-aws-sso; the app runs it automatically when credentials are missing or expired
echo    - Optional: set AWS_PROFILE or create .env with real AWS credentials
echo.
echo 4. Run the application:
echo      python super_secretary.py transcripts/
echo.
echo ==========================================
echo.
pause
