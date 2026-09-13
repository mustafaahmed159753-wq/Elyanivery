@echo off
setlocal
cd /d "%~dp0"
echo Restoring app\build.gradle.kts...

if exist "..\elyanivery\android\app\build.gradle.kts" (
    copy /Y "..\elyanivery\android\app\build.gradle.kts" "app\build.gradle.kts" >nul
    echo Restored from ..\elyanivery\android\app\build.gradle.kts
)

echo.
echo Checking file size:
for %%I in ("app\build.gradle.kts") do echo Size: %%~zI bytes
echo.
