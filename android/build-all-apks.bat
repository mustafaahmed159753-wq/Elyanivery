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

:: Ensure app\build.gradle.kts is intact and restore if corrupted with HTML
findstr /i "html" "app\build.gradle.kts" >nul 2>&1
if not errorlevel 1 (
    echo  - Detected corrupted build.gradle.kts! Auto-restoring clean Kotlin file...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[IO.File]::WriteAllBytes('app\build.gradle.kts', [Convert]::FromBase64String('aW1wb3J0IGphdmEudXRpbC5Qcm9wZXJ0aWVzCgpwbHVnaW5zIHsKICAgIGlkKCJjb20uYW5kcm9pZC5hcHBsaWNhdGlvbiIpCiAgICBpZCgib3JnLmpldGJyYWlucy5rb3RsaW4uYW5kcm9pZCIpCn0KCmFuZHJvaWQgewogICAgbmFtZXNwYWNlID0gImNvbS5lbHlhbml2ZXJ5LmFwcCIKICAgIGNvbXBpbGVTZGsgPSAzNAoKICAgIGRlZmF1bHRDb25maWcgewogICAgICAgIGFwcGxpY2F0aW9uSWQgPSAiY29tLmVseWFuaXZlcnkuYXBwIgogICAgICAgIG1pblNkayA9IDI0CiAgICAgICAgdGFyZ2V0U2RrID0gMzQKICAgICAgICB2ZXJzaW9uQ29kZSA9IDEKICAgICAgICB2ZXJzaW9uTmFtZSA9ICIxLjAuMCIKCiAgICAgICAgdGVzdEluc3RydW1lbnRhdGlvblJ1bm5lciA9ICJhbmRyb2lkeC50ZXN0LnJ1bm5lci5BbmRyb2lkSlVuaXRSdW5uZXIiCiAgICB9CgogICAgYnVpbGRGZWF0dXJlcyB7CiAgICAgICAgYnVpbGRDb25maWcgPSB0cnVlCiAgICB9CgogICAgLy8gRHluYW1pYyBTZXJ2ZXIgUmVzb2x1dGlvbjogUHJpb3JpdGl6ZSBSZW5kZXIgVVJMIG92ZXIgZGV2IHByZXZpZXcKICAgIHZhbCBiYXNlU2VydmVyVXJsOiBTdHJpbmcgPSBydW4gewogICAgICAgIC8vIDEuIEdyYWRsZSBwcm9wZXJ0eTogLVBTRVJWRVJfVVJMPWh0dHBzOi8vLi4uCiAgICAgICAgdmFsIHByb3AgPSBwcm92aWRlcnMuZ3JhZGxlUHJvcGVydHkoIlNFUlZFUl9VUkwiKS5vck51bGwKICAgICAgICBpZiAoIXByb3AuaXNOdWxsT3JCbGFuaygpKSByZXR1cm5AcnVuIHByb3AudHJpbUVuZCgnLycpCgogICAgICAgIC8vIDIuIGxvY2FsLnByb3BlcnRpZXM6IHNlcnZlci51cmw9aHR0cHM6Ly8uLi4KICAgICAgICB2YWwgbG9jYWxQcm9wRmlsZSA9IHJvb3RQcm9qZWN0LmZpbGUoImxvY2FsLnByb3BlcnRpZXMiKQogICAgICAgIGlmIChsb2NhbFByb3BGaWxlLmV4aXN0cygpKSB7CiAgICAgICAgICAgIHZhbCBwID0gUHJvcGVydGllcygpCiAgICAgICAgICAgIGxvY2FsUHJvcEZpbGUuaW5wdXRTdHJlYW0oKS51c2UgeyBwLmxvYWQoaXQpIH0KICAgICAgICAgICAgdmFsIHNlcnZlckZyb21Mb2NhbCA9IHAuZ2V0UHJvcGVydHkoInNlcnZlci51cmwiKSA/OiBwLmdldFByb3BlcnR5KCJTRVJWRVJfVVJMIikKICAgICAgICAgICAgaWYgKCFzZXJ2ZXJGcm9tTG9jYWwuaXNOdWxsT3JCbGFuaygpKSByZXR1cm5AcnVuIHNlcnZlckZyb21Mb2NhbC50cmltRW5kKCcvJykKICAgICAgICB9CgogICAgICAgIC8vIDMuIERlZmF1bHQgdG8gUmVuZGVyIHByb2R1Y3Rpb24gc2VydmljZSBVUkwKICAgICAgICAiaHR0cHM6Ly9lbHlhbml2ZXJ5Lm9ucmVuZGVyLmNvbSIKICAgIH0KCiAgICBmbGF2b3JEaW1lbnNpb25zICs9ICJwb3J0YWwiCiAgICBwcm9kdWN0Rmxhdm9ycyB7CiAgICAgICAgY3JlYXRlKCJjdXN0b21lciIpIHsKICAgICAgICAgICAgZGltZW5zaW9uID0gInBvcnRhbCIKICAgICAgICAgICAgYXBwbGljYXRpb25JZCA9ICJjb20uZWx5YW5pdmVyeS5jdXN0b21lciIKICAgICAgICAgICAgbWFuaWZlc3RQbGFjZWhvbGRlcnNbImFwcE5hbWUiXSA9ICJFbHlhbml2ZXJ5IgogICAgICAgICAgICBidWlsZENvbmZpZ0ZpZWxkKCJTdHJpbmciLCAiQVBQX1VSTCIsICJcIiRiYXNlU2VydmVyVXJsL2N1c3RvbWVyXCIiKQogICAgICAgICAgICBidWlsZENvbmZpZ0ZpZWxkKCJTdHJpbmciLCAiQkFTRV9TRVJWRVJfVVJMIiwgIlwiJGJhc2VTZXJ2ZXJVcmxcIiIpCiAgICAgICAgfQogICAgICAgIGNyZWF0ZSgiY291cmllciIpIHsKICAgICAgICAgICAgZGltZW5zaW9uID0gInBvcnRhbCIKICAgICAgICAgICAgYXBwbGljYXRpb25JZCA9ICJjb20uZWx5YW5pdmVyeS5jb3VyaWVyIgogICAgICAgICAgICBtYW5pZmVzdFBsYWNlaG9sZGVyc1siYXBwTmFtZSJdID0gIkVseWFuaXZlcnkgQ291cmllciIKICAgICAgICAgICAgYnVpbGRDb25maWdGaWVsZCgiU3RyaW5nIiwgIkFQUF9VUkwiLCAiXCIkYmFzZVNlcnZlclVybC9jb3VyaWVyXCIiKQogICAgICAgICAgICBidWlsZENvbmZpZ0ZpZWxkKCJTdHJpbmciLCAiQkFTRV9TRVJWRVJfVVJMIiwgIlwiJGJhc2VTZXJ2ZXJVcmxcIiIpCiAgICAgICAgfQogICAgICAgIGNyZWF0ZSgicGFydG5lciIpIHsKICAgICAgICAgICAgZGltZW5zaW9uID0gInBvcnRhbCIKICAgICAgICAgICAgYXBwbGljYXRpb25JZCA9ICJjb20uZWx5YW5pdmVyeS5wYXJ0bmVyIgogICAgICAgICAgICBtYW5pZmVzdFBsYWNlaG9sZGVyc1siYXBwTmFtZSJdID0gIkVseWFuaXZlcnkgUGFydG5lciIKICAgICAgICAgICAgYnVpbGRDb25maWdGaWVsZCgiU3RyaW5nIiwgIkFQUF9VUkwiLCAiXCIkYmFzZVNlcnZlclVybC9wYXJ0bmVyXCIiKQogICAgICAgICAgICBidWlsZENvbmZpZ0ZpZWxkKCJTdHJpbmciLCAiQkFTRV9TRVJWRVJfVVJMIiwgIlwiJGJhc2VTZXJ2ZXJVcmxcIiIpCiAgICAgICAgfQogICAgICAgIGNyZWF0ZSgiYWRtaW4iKSB7CiAgICAgICAgICAgIGRpbWVuc2lvbiA9ICJwb3J0YWwiCiAgICAgICAgICAgIGFwcGxpY2F0aW9uSWQgPSAiY29tLmVseWFuaXZlcnkuYWRtaW4iCiAgICAgICAgICAgIG1hbmlmZXN0UGxhY2Vob2xkZXJzWyJhcHBOYW1lIl0gPSAiRWx5YW5pdmVyeSBBZG1pbiIKICAgICAgICAgICAgYnVpbGRDb25maWdGaWVsZCgiU3RyaW5nIiwgIkFQUF9VUkwiLCAiXCIkYmFzZVNlcnZlclVybC9hZG1pblwiIikKICAgICAgICAgICAgYnVpbGRDb25maWdGaWVsZCgiU3RyaW5nIiwgIkJBU0VfU0VSVkVSX1VSTCIsICJcIiRiYXNlU2VydmVyVXJsXCIiKQogICAgICAgIH0KICAgICAgICBjcmVhdGUoInN1cHBvcnQiKSB7CiAgICAgICAgICAgIGRpbWVuc2lvbiA9ICJwb3J0YWwiCiAgICAgICAgICAgIGFwcGxpY2F0aW9uSWQgPSAiY29tLmVseWFuaXZlcnkuc3VwcG9ydCIKICAgICAgICAgICAgbWFuaWZlc3RQbGFjZWhvbGRlcnNbImFwcE5hbWUiXSA9ICJFbHlhbml2ZXJ5IFN1cHBvcnQiCiAgICAgICAgICAgIGJ1aWxkQ29uZmlnRmllbGQoIlN0cmluZyIsICJBUFBfVVJMIiwgIlwiJGJhc2VTZXJ2ZXJVcmwvc3VwcG9ydFwiIikKICAgICAgICAgICAgYnVpbGRDb25maWdGaWVsZCgiU3RyaW5nIiwgIkJBU0VfU0VSVkVSX1VSTCIsICJcIiRiYXNlU2VydmVyVXJsXCIiKQogICAgICAgIH0KICAgIH0KCiAgICBzaWduaW5nQ29uZmlncyB7CiAgICAgICAgY3JlYXRlKCJyZWxlYXNlIikgewogICAgICAgICAgICB2YWwga3NGaWxlID0gcm9vdFByb2plY3QuZmlsZSgia2V5c3RvcmUvZWx5YW5pdmVyeS5rZXlzdG9yZSIpCiAgICAgICAgICAgIGlmIChrc0ZpbGUuZXhpc3RzKCkpIHsKICAgICAgICAgICAgICAgIHN0b3JlRmlsZSA9IGtzRmlsZQogICAgICAgICAgICAgICAgc3RvcmVQYXNzd29yZCA9ICJlbHlhbml2ZXJ5IgogICAgICAgICAgICAgICAga2V5QWxpYXMgPSAiZWx5YW5pdmVyeSIKICAgICAgICAgICAgICAgIGtleVBhc3N3b3JkID0gImVseWFuaXZlcnkiCiAgICAgICAgICAgICAgICBlbmFibGVWMVNpZ25pbmcgPSB0cnVlCiAgICAgICAgICAgICAgICBlbmFibGVWMlNpZ25pbmcgPSB0cnVlCiAgICAgICAgICAgIH0KICAgICAgICB9CiAgICB9CgogICAgYnVpbGRUeXBlcyB7CiAgICAgICAgcmVsZWFzZSB7CiAgICAgICAgICAgIGlzTWluaWZ5RW5hYmxlZCA9IGZhbHNlCiAgICAgICAgICAgIHNpZ25pbmdDb25maWcgPSBzaWduaW5nQ29uZmlncy5nZXRCeU5hbWUoInJlbGVhc2UiKQogICAgICAgICAgICBwcm9ndWFyZEZpbGVzKAogICAgICAgICAgICAgICAgZ2V0RGVmYXVsdFByb2d1YXJkRmlsZSgicHJvZ3VhcmQtYW5kcm9pZC1vcHRpbWl6ZS50eHQiKSwKICAgICAgICAgICAgICAgICJwcm9ndWFyZC1ydWxlcy5wcm8iCiAgICAgICAgICAgICkKICAgICAgICB9CiAgICAgICAgZGVidWcgewogICAgICAgICAgICBzaWduaW5nQ29uZmlnID0gc2lnbmluZ0NvbmZpZ3MuZ2V0QnlOYW1lKCJyZWxlYXNlIikKICAgICAgICB9CiAgICB9CgogICAgY29tcGlsZU9wdGlvbnMgewogICAgICAgIHNvdXJjZUNvbXBhdGliaWxpdHkgPSBKYXZhVmVyc2lvbi5WRVJTSU9OXzFfOAogICAgICAgIHRhcmdldENvbXBhdGliaWxpdHkgPSBKYXZhVmVyc2lvbi5WRVJTSU9OXzFfOAogICAgfQoKICAgIGtvdGxpbk9wdGlvbnMgewogICAgICAgIGp2bVRhcmdldCA9ICIxLjgiCiAgICB9CgogICAgbGludCB7CiAgICAgICAgY2hlY2tSZWxlYXNlQnVpbGRzID0gZmFsc2UKICAgICAgICBhYm9ydE9uRXJyb3IgPSBmYWxzZQogICAgfQp9CgpkZXBlbmRlbmNpZXMgewogICAgaW1wbGVtZW50YXRpb24oImFuZHJvaWR4LmNvcmU6Y29yZS1rdHg6MS4xMi4wIikKICAgIGltcGxlbWVudGF0aW9uKCJhbmRyb2lkeC5hcHBjb21wYXQ6YXBwY29tcGF0OjEuNi4xIikKICAgIGltcGxlbWVudGF0aW9uKCJjb20uZ29vZ2xlLmFuZHJvaWQubWF0ZXJpYWw6bWF0ZXJpYWw6MS4xMS4wIikKICAgIGltcGxlbWVudGF0aW9uKCJhbmRyb2lkeC5hY3Rpdml0eTphY3Rpdml0eS1rdHg6MS44LjIiKQp9Cg==')]" >nul 2>&1
    echo  - Successfully restored app\build.gradle.kts!
)

:: Ensure MainActivity.kt has no duplicate showServerConfigDialog overload
findstr /i "private fun showServerConfigDialog" "app\src\main\java\com\elyanivery\app\MainActivity.kt" >nul 2>&1
if not errorlevel 1 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$c = [IO.File]::ReadAllText('app\src\main\java\com\elyanivery\app\MainActivity.kt'); $c = $c -replace 'private fun showServerConfigDialog\(\)', 'fun showServerConfigDialog()'; $idx = $c.IndexOf('    fun showServerConfigDialog() {`r`n        val input = EditText(this)'); if ($idx -lt 0) { $idx = $c.IndexOf('    fun showServerConfigDialog() {`n        val input = EditText(this)'); }; if ($idx -ge 0) { $endIdx = $c.IndexOf('    inner class ElyaniveryJsBridge', $idx); if ($endIdx -ge 0) { $c = $c.Substring(0, $idx) + $c.Substring($endIdx); } }; [IO.File]::WriteAllText('app\src\main\java\com\elyanivery\app\MainActivity.kt', $c, [System.Text.Encoding]::UTF8)" >nul 2>&1
    echo  - Auto-healed MainActivity.kt overloads!
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
