@echo off
setlocal
echo ==========================================================
echo       ELYANIVERY - AUTO-INSTALL ANDROID SDK VIA CMD
echo ==========================================================
echo.

set "SDK_DIR=%LOCALAPPDATA%\Android\Sdk"
set "CMDLINE_DIR=%SDK_DIR%\cmdline-tools\latest"

echo Installing Android SDK to: %SDK_DIR%
echo.

if not exist "%SDK_DIR%" mkdir "%SDK_DIR%"
if not exist "%CMDLINE_DIR%" mkdir "%CMDLINE_DIR%"

set "ZIP_FILE=%TEMP%\cmdline-tools.zip"
set "TOOLS_URL=https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"

echo [1/4] Downloading official Google Android Command Line Tools...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%TOOLS_URL%', '%ZIP_FILE%')"

if not exist "%ZIP_FILE%" (
    echo Failed to download Android command-line tools.
    echo Please install Android Studio via winget:
    echo   winget install Google.AndroidStudio
    pause
    exit /b 1
)

echo [2/4] Extracting Android Command Line Tools...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%TEMP%\cmdline-temp' -Force"
xcopy /E /Y /I "%TEMP%\cmdline-temp\cmdline-tools\*" "%CMDLINE_DIR%\" >nul 2>&1
rmdir /S /Q "%TEMP%\cmdline-temp" >nul 2>&1
del /F /Q "%ZIP_FILE%" >nul 2>&1

echo [3/4] Installing Android 34 platforms and build-tools (Accepting licenses)...
set "PATH=%CMDLINE_DIR%\bin;%PATH%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "cmd /c 'echo y| %CMDLINE_DIR%\bin\sdkmanager.bat --sdk_root=%SDK_DIR% \"platform-tools\" \"platforms;android-34\" \"build-tools;34.0.0\"'"

echo [4/4] Generating local.properties with SDK path...
cd /d "%~dp0"
set "ESCAPED_SDK=%SDK_DIR:\=\\%"
echo sdk.dir=%ESCAPED_SDK%> local.properties

echo.
echo ==========================================================
echo  SUCCESS! Android SDK has been installed and configured!
echo  sdk.dir is written to local.properties
echo ==========================================================
echo.
echo Now you can run: build-all-apks.bat
pause
