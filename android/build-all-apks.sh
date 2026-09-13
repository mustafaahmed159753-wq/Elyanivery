#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "      ELYANIVERY - BUILD ALL 5 APKs VIA CLI/TERMINAL"
echo "=========================================================="
echo ""
echo "Links included:"
echo " 1. Customer: /customer"
echo " 2. Courier:  /courier"
echo " 3. Partner:  /partner"
echo " 4. Admin:    /admin"
echo " 5. Support:  /support"
echo ""

chmod +x gradlew 2>/dev/null || true

echo "Compiling all 5 product flavors..."
./gradlew assembleDebug

mkdir -p ../dist-apks

cp -f "app/build/outputs/apk/customer/debug/app-customer-debug.apk" "../dist-apks/Elyanivery-Customer.apk" 2>/dev/null || true
cp -f "app/build/outputs/apk/courier/debug/app-courier-debug.apk" "../dist-apks/Elyanivery-Courier.apk" 2>/dev/null || true
cp -f "app/build/outputs/apk/partner/debug/app-partner-debug.apk" "../dist-apks/Elyanivery-Partner.apk" 2>/dev/null || true
cp -f "app/build/outputs/apk/admin/debug/app-admin-debug.apk" "../dist-apks/Elyanivery-Admin.apk" 2>/dev/null || true
cp -f "app/build/outputs/apk/support/debug/app-support-debug.apk" "../dist-apks/Elyanivery-Support.apk" 2>/dev/null || true

echo "All 5 APKs generated in ../dist-apks/ :"
ls -lh ../dist-apks/
