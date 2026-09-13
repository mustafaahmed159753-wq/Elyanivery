@echo off
setlocal
echo ==========================================================
echo       ELYANIVERY - FIX ANDROID SDK LOCATION
echo ==========================================================
echo.

cd /d "%~dp0"

echo Checking SDK from previous version or standard Windows locations...

if exist "..\elyanivery\android\local.properties" (
    copy /Y "..\elyanivery\android\local.properties" "local.properties" >nul
    echo [OK] Copied local.properties from previous version folder: ..\elyanivery\android\
    goto test_sdk
)

if exist "C:\Users\%USERNAME%\Desktop\elyanivery\android\local.properties" (
    copy /Y "C:\Users\%USERNAME%\Desktop\elyanivery\android\local.properties" "local.properties" >nul
    echo [OK] Copied local.properties from Desktop\elyanivery\android\
    goto test_sdk
)

if exist "%LOCALAPPDATA%\Android\Sdk" (
    set "ESCAPED_SDK=%LOCALAPPDATA:\=\\%\\Android\\Sdk"
    echo sdk.dir=%ESCAPED_SDK%> local.properties
    echo [OK] Generated local.properties pointing to: %LOCALAPPDATA%\Android\Sdk
    goto test_sdk
)

if exist "C:\Users\%USERNAME%\AppData\Local\Android\Sdk" (
    echo sdk.dir=C\:\\Users\\%USERNAME%\\AppData\\Local\\Android\\Sdk> local.properties
    echo [OK] Generated local.properties pointing to: C:\Users\%USERNAME%\AppData\Local\Android\Sdk
    goto test_sdk
)

echo [!] Writing default Android SDK path into local.properties...
echo sdk.dir=C\:\\Users\\%USERNAME%\\AppData\\Local\\Android\\Sdk> local.properties

:test_sdk
echo.
echo Contents of local.properties:
type local.properties
echo.
echo [DONE] You can now run:
echo   build-all-apks.bat
echo   or
echo   gradlew.bat assembleRelease
echo.
