@echo off
setlocal
cd /d "%~dp0"

echo Outputting all built APKs to dist-apks...
if not exist "dist-apks" mkdir "dist-apks"

copy /Y "app\build\outputs\apk\customer\release\app-customer-release.apk" "dist-apks\Elyanivery-Customer-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\courier\release\app-courier-release.apk" "dist-apks\Elyanivery-Courier-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\partner\release\app-partner-release.apk" "dist-apks\Elyanivery-Partner-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\admin\release\app-admin-release.apk" "dist-apks\Elyanivery-Admin-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\support\release\app-support-release.apk" "dist-apks\Elyanivery-Support-signed.apk" >nul 2>&1

copy /Y "app\build\outputs\apk\customer\debug\app-customer-debug.apk" "dist-apks\Elyanivery-Customer-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\courier\debug\app-courier-debug.apk" "dist-apks\Elyanivery-Courier-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\partner\debug\app-partner-debug.apk" "dist-apks\Elyanivery-Partner-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\admin\debug\app-admin-debug.apk" "dist-apks\Elyanivery-Admin-signed.apk" >nul 2>&1
copy /Y "app\build\outputs\apk\support\debug\app-support-debug.apk" "dist-apks\Elyanivery-Support-signed.apk" >nul 2>&1

echo.
echo ==========================================================
echo  APKs are ready in android\dist-apks:
echo ==========================================================
dir /b dist-apks\*.apk
echo.
