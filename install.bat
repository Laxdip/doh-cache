@echo off
title Prasad's DOH Cache Installer
setlocal enabledelayedexpansion

:: ============================================================================
:: Prasad's Advanced DOH Cache - Installer for Windows
:: ============================================================================

:: Colors for Windows (using color codes)
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "RESET=[0m"

:: Print colored message (Windows compatible)
call :print_banner

:: Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo %RED%[!] This installer requires Administrator privileges!%RESET%
    echo %YELLOW%[!] Please run as Administrator%RESET%
    echo.
    pause
    exit /b 1
)

echo %GREEN%[+] Running with Administrator privileges%RESET%
echo.

:: Check Python installation
call :check_python
if %errorLevel% neq 0 exit /b 1

:: Check pip
call :check_pip

:: Create directories
call :create_directories

:: Install dependencies
call :install_dependencies

:: Create startup script
call :create_startup_script

:: Create firewall rule
call :create_firewall_rule

:: Create Windows Service (optional)
call :create_windows_service

:: Test installation
call :test_installation

:: Show next steps
call :show_next_steps

pause
exit /b 0

:: ============================================================================
:: Functions
:: ============================================================================

:print_banner
echo %BLUE%╔══════════════════════════════════════════════════════════════╗%RESET%
echo %BLUE%║                                                              ║%RESET%
echo %BLUE%║   ██████╗  ██████╗ ██╗  ██╗                                  ║%RESET%
echo %BLUE%║   ██╔══██╗██╔═══██╗██║  ██║                                  ║%RESET%
echo %BLUE%║   ██║  ██║██║   ██║███████║                                  ║%RESET%
echo %BLUE%║   ██║  ██║██║   ██║██╔══██║                                  ║%RESET%
echo %BLUE%║   ██████╔╝╚██████╔╝██║  ██║                                  ║%RESET%
echo %BLUE%║   ╚═════╝  ╚═════╝ ╚═╝  ╚═╝                                  ║%RESET%
echo %BLUE%║                                                              ║%RESET%
echo %BLUE%║   ██████╗  █████╗  ██████╗██╗  ██╗███████╗                   ║%RESET%
echo %BLUE%║  ██╔════╝ ██╔══██╗██╔════╝██║  ██║██╔════╝                   ║%RESET%
echo %BLUE%║  ██║      ███████║██║     ███████║█████╗                     ║%RESET%
echo %BLUE%║  ██║      ██╔══██║██║     ██╔══██║██╔══╝                     ║%RESET%
echo %BLUE%║  ╚██████╗ ██║  ██║╚██████╗██║  ██║███████╗                   ║%RESET%
echo %BLUE%║   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝                   ║%RESET%
echo %BLUE%║                                                              ║%RESET%
echo %BLUE%║        Advanced DNS-over-HTTPS Cache Installer               ║%RESET%
echo %BLUE%║                Created by Prasad v1.0                        ║%RESET%
echo %BLUE%╚══════════════════════════════════════════════════════════════╝%RESET%
echo.
goto :eof

:check_python
echo %YELLOW%[+] Checking Python installation...%RESET%

python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo %RED%[!] Python not found!%RESET%
    echo %YELLOW%[!] Please install Python 3.7 or higher from https://python.org%RESET%
    echo %YELLOW%[!] Make sure to check 'Add Python to PATH' during installation%RESET%
    exit /b 1
)

python --version
echo %GREEN%[+] Python found successfully%RESET%
echo.
goto :eof

:check_pip
echo %YELLOW%[+] Checking pip...%RESET%

pip --version >nul 2>&1
if %errorLevel% neq 0 (
    echo %YELLOW%[!] pip not found, installing...%RESET%
    python -m ensurepip --upgrade
)

echo %GREEN%[+] pip is ready%RESET%
echo.
goto :eof

:create_directories
echo %YELLOW%[+] Creating directories...%RESET%

if not exist "logs" mkdir logs
if not exist "data" mkdir data

echo %GREEN%[+] Directories created%RESET%
echo.
goto :eof

:install_dependencies
echo %YELLOW%[+] Installing Python dependencies...%RESET%
echo %YELLOW%[!] This may take a few minutes...%RESET%

if exist "requirements.txt" (
    pip install --upgrade pip
    pip install -r requirements.txt
    
    if %errorLevel% equ 0 (
        echo %GREEN%[+] Dependencies installed successfully%RESET%
    ) else (
        echo %RED%[!] Failed to install dependencies%RESET%
        exit /b 1
    )
) else (
    echo %RED%[!] requirements.txt not found!%RESET%
    exit /b 1
)
echo.
goto :eof

:create_startup_script
echo %YELLOW%[+] Creating startup scripts...%RESET%

:: Create run_with_python.bat
(
echo @echo off
echo title Prasad's DOH Cache Server
echo cd /d "%~dp0"
echo python run.py
echo pause
) > run_with_python.bat

:: Create silent_start.vbs (runs in background)
(
echo Set WshShell = CreateObject("WScript.Shell")
echo WshShell.Run "cmd /c cd /d ""%CD%"" ^&^& python run.py", 0, False
echo Set WshShell = Nothing
) > silent_start.vbs

echo %GREEN%[+] Startup scripts created%RESET%
echo.
goto :eof

:create_firewall_rule
echo %YELLOW%[+] Creating Windows Firewall rule...%RESET%

set "RULE_NAME=Prasad DOH Cache"
set "PORT=5353"

netsh advfirewall firewall show rule name="%RULE_NAME%" >nul 2>&1
if %errorLevel% equ 0 (
    netsh advfirewall firewall delete rule name="%RULE_NAME%" >nul 2>&1
    echo %YELLOW%[!] Existing rule removed%RESET%
)

netsh advfirewall firewall add rule name="%RULE_NAME%" dir=in action=allow protocol=TCP localport=%PORT% >nul 2>&1
netsh advfirewall firewall add rule name="%RULE_NAME%" dir=in action=allow protocol=UDP localport=%PORT% >nul 2>&1

if %errorLevel% equ 0 (
    echo %GREEN%[+] Firewall rule created for port %PORT%%RESET%
) else (
    echo %YELLOW%[!] Could not create firewall rule (may require manual configuration)%RESET%
)
echo.
goto :eof

:create_windows_service
echo %YELLOW%[+] Setting up Windows Service...%RESET%

set /p create_service="Do you want to install as a Windows Service? (y/n): "
if /i "!create_service!"=="y" (
    echo %YELLOW%[!] Creating Windows Service using NSSM...%RESET%
    
    :: Check if NSSM exists
    if not exist "nssm.exe" (
        echo %YELLOW%[!] Downloading NSSM (Non-Sucking Service Manager)...%RESET%
        powershell -Command "Invoke-WebRequest -Uri 'https://nssm.cc/release/nssm-2.24.zip' -OutFile 'nssm.zip'"
        powershell -Command "Expand-Archive -Path 'nssm.zip' -DestinationPath '.'"
        copy "nssm-2.24\win64\nssm.exe" "nssm.exe" >nul 2>&1
        rmdir /s /q "nssm-2.24" >nul 2>&1
        del "nssm.zip" >nul 2>&1
    )
    
    :: Install service
    nssm.exe stop "PrasadDOHCache" >nul 2>&1
    nssm.exe remove "PrasadDOHCache" confirm >nul 2>&1
    
    set "CURRENT_DIR=%CD%"
    set "CURRENT_DIR=!CURRENT_DIR:\=\\!"
    
    nssm.exe install "PrasadDOHCache" "%CD%\python.exe" "%CD%\run.py"
    nssm.exe set "PrasadDOHCache" AppDirectory "%CD%"
    nssm.exe set "PrasadDOHCache" Start SERVICE_AUTO_START
    nssm.exe set "PrasadDOHCache" DisplayName "Prasad's DOH Cache"
    nssm.exe set "PrasadDOHCache" Description "Advanced DNS-over-HTTPS Cache Server"
    
    if %errorLevel% equ 0 (
        echo %GREEN%[+] Windows Service created successfully%RESET%
        echo %YELLOW%   Commands: %RESET%
        echo   - Start: net start PrasadDOHCache
        echo   - Stop: net stop PrasadDOHCache
        echo   - Status: sc query PrasadDOHCache
    ) else (
        echo %RED%[!] Failed to create Windows Service%RESET%
    )
) else (
    echo %YELLOW%[!] Skipping Windows Service installation%RESET%
)
echo.
goto :eof

:test_installation
echo %YELLOW%[+] Testing installation...%RESET%

python -c "import dns, httpx, yaml, cachetools" >nul 2>&1
if %errorLevel% equ 0 (
    echo %GREEN%[+] All modules imported successfully%RESET%
) else (
    echo %YELLOW%[!] Warning: Some modules may be missing%RESET%
)
echo.
goto :eof

:show_next_steps
echo.
echo %GREEN%╔══════════════════════════════════════════════════════════════╗%RESET%
echo %GREEN%║                    INSTALLATION COMPLETE!                    ║%RESET%
echo %GREEN%╚══════════════════════════════════════════════════════════════╝%RESET%
echo.
echo %YELLOW%Next steps:%RESET%
echo.
echo 1. Configure your DNS settings:
echo    - Edit config.yaml to customize settings
echo    - Set your system DNS to 127.0.0.1:5353
echo.
echo 2. Run the server:
echo    Double-click run_with_python.bat
echo.
echo 3. Or run in background:
echo    Double-click silent_start.vbs
echo.
echo 4. Or run manually:
echo    python run.py --port 5353
echo.
echo 5. Test with nslookup:
echo    nslookup google.com 127.0.0.1
echo.
echo 6. Check logs:
echo    Check logs folder for doh-cache.log
echo.
echo 7. To stop the server:
echo    Close the command prompt window
echo.
goto :eof
