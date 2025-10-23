@echo off
REM Windows MAC Address Changer Batch Script
REM This script provides an easy way to run the Python MAC changer on Windows

echo ========================================
echo Windows MAC Address Changer
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check if arguments are provided
if "%~1"=="" (
    echo Usage: run_mac_changer_windows.bat ^<pcapng_file^> ^<interface_name^>
    echo.
    echo Example: run_mac_changer_windows.bat capture.pcapng "Wi-Fi"
    echo.
    echo Available network interfaces:
    powershell -Command "Get-NetAdapter | Select-Object Name, Status | Format-Table -AutoSize"
    pause
    exit /b 1
)

if "%~2"=="" (
    echo ERROR: Interface name is required
    echo.
    echo Available network interfaces:
    powershell -Command "Get-NetAdapter | Select-Object Name, Status | Format-Table -AutoSize"
    pause
    exit /b 1
)

REM Check if pcapng file exists
if not exist "%~1" (
    echo ERROR: File "%~1" does not exist
    pause
    exit /b 1
)

echo Starting Windows MAC Address Changer...
echo PCAPNG File: %~1
echo Interface: %~2
echo.

REM Run the Python script
python arp_mac_changer_windows.py "%~1" "%~2"

echo.
echo Script execution completed.
pause
