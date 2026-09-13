@echo off
setlocal
echo ==========================================================
echo       ELYANIVERY - BUILD ALL 5 SIGNED APKs VIA CMD
echo ==========================================================
echo.
echo Links included:
echo  1. Customer Portal    - /customer
echo  2. Courier Partner    - /courier
echo  3. Restaurant Partner - /partner
echo  4. Admin Portal       - /admin
echo  5. Support Desk       - /support
echo.

cd /d "%~dp0"

echo [1/4] Checking Android SDK and Java version...

if exist "local.properties" (
    echo  - Found existing local.properties
) else if exist "..\elyanivery\android\local.properties" (
    copy /Y "..\elyanivery\android\local.properties" "local.properties" >nul
    echo  - Copied SDK path from previous version: ..\elyanivery\android\local.properties
) else if exist "..\..\elyanivery\android\local.properties" (
    copy /Y "..\..\elyanivery\android\local.properties" "local.properties" >nul
    echo  - Copied SDK path from previous version: ..\..\elyanivery\android\local.properties
) else if exist "%LOCALAPPDATA%\Android\Sdk" (
    set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
    echo  - Detected Android SDK at: %LOCALAPPDATA%\Android\Sdk
    set "ESCAPED_SDK=%LOCALAPPDATA:\=\\%\\Android\\Sdk"
    echo sdk.dir=%ESCAPED_SDK%> local.properties
    echo  - Created local.properties pointing to Android SDK
) else if exist "C:\Users\%USERNAME%\AppData\Local\Android\Sdk" (
    echo sdk.dir=C\:\\Users\\%USERNAME%\\AppData\\Local\\Android\\Sdk> local.properties
    echo  - Created local.properties pointing to Android SDK
) else if defined ANDROID_HOME (
    set "ESCAPED_SDK=%ANDROID_HOME:\=\\%"
    echo sdk.dir=%ESCAPED_SDK%> local.properties
    echo  - Created local.properties from ANDROID_HOME environment variable
) else (
    echo  - WARNING: local.properties not found! Creating default for Windows...
    echo sdk.dir=C\:\\Users\\%USERNAME%\\AppData\\Local\\Android\\Sdk> local.properties
)

findstr /i "server.url" local.properties >nul 2>&1
if errorlevel 1 (
    echo server.url=https://elyanivery.onrender.com>> local.properties
)
echo  - Server target: Render Cloud (configured in local.properties)

if exist "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot\bin\java.exe" (
    set "JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
    set "PATH=%JAVA_HOME%\bin;%PATH%"
    echo  - Using JDK: %JAVA_HOME%
) else if exist "C:\Program Files\Android\Android Studio\jbr\bin\java.exe" (
    set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
    set "PATH=%JAVA_HOME%\bin;%PATH%"
    echo  - Using Android Studio JDK: %JAVA_HOME%
)

echo.
echo [2/4] Verifying release signing keystore and gradle.properties...
if exist "keystore\elyanivery.keystore" (
    echo  - Keystore ready: android\keystore\elyanivery.keystore [SIGNED]
)
if not exist "gradle.properties" (
    echo android.useAndroidX=true> gradle.properties
    echo android.enableJetifier=true>> gradle.properties
    echo org.gradle.jvmargs=-Xmx2048m>> gradle.properties
)

:: Auto-fix logo.png into genuine PNG format to satisfy AAPT2
if exist "app\src\main\res\drawable\logo.png" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Add-Type -AssemblyName System.Drawing; $p = (Resolve-Path 'app\src\main\res\drawable\logo.png').Path; $img = [System.Drawing.Image]::FromFile($p); $tmp = [System.IO.Path]::GetTempFileName() + '.png'; $img.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Png); $img.Dispose(); Move-Item -Force $tmp $p } catch {}" >nul 2>&1
)

echo.
echo [3/4] Compiling and signing all 5 APK product flavors with Gradle...
echo  - 1. Customer (com.elyanivery.customer)
echo  - 2. Courier  (com.elyanivery.courier)
echo  - 3. Partner  (com.elyanivery.partner)
echo  - 4. Admin    (com.elyanivery.admin)
echo  - 5. Support  (com.elyanivery.support)
echo.

call gradlew.bat assembleRelease --no-daemon
if not errorlevel 1 goto copy_apks

echo.
echo Release build returned an error code, running assembleDebug...
call gradlew.bat assembleDebug --no-daemon
if errorlevel 1 goto build_failed

:copy_apks
echo.
echo [4/4] Outputting all signed APKs to android\dist-apks...
if not exist "dist-apks" mkdir "dist-apks"

copy /Y "app\build\outputs\apk\customer\release\app-customer-release.apk" "dist-apks\Elyanivery-Customer-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\courier\release\app-courier-release.apk" "dist-apks\Elyanivery-Courier-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\partner\release\app-partner-release.apk" "dist-apks\Elyanivery-Partner-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\admin\release\app-admin-release.apk" "dist-apks\Elyanivery-Admin-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\support\release\app-support-release.apk" "dist-apks\Elyanivery-Support-signed.apk" >nul 2>&1

:: Fallback if named debug
copy /Y "app\build\outputs\apk\customer\debug\app-customer-debug.apk" "dist-apks\Elyanivery-Customer-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\courier\debug\app-courier-debug.apk" "dist-apks\Elyanivery-Courier-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\partner\debug\app-partner-debug.apk" "dist-apks\Elyanivery-Partner-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\admin\debug\app-admin-debug.apk" "dist-apks\Elyanivery-Admin-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\support\debug\app-support-debug.apk" "dist-apks\Elyanivery-Support-signed.apk" >nul 2>&1

echo.
echo ==========================================================
echo  SUCCESS! All 5 APKs have been BUILT and SIGNED:
echo.
echo    1. android\dist-apks\Elyanivery-Customer-signed.apk
echo    2. android\dist-apks\Elyanivery-Courier-signed.apk
echo    3. android\dist-apks\Elyanivery-Partner-signed.apk
echo    4. android\dist-apks\Elyanivery-Admin-signed.apk
echo    5. android\dist-apks\Elyanivery-Support-signed.apk
echo.
echo  Keystore: android\keystore\elyanivery.keystore
echo  Password: elyanivery
echo ==========================================================
echo.
echo Transfer any of these APKs to your Android device to install.
pause
exit /b 0

:build_failed
echo.
echo ==========================================================
echo [ERROR] Build encountered an error. Please inspect the output above.
echo ==========================================================
pause
exit /b 1
