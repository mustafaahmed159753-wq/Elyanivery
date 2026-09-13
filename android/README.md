# Elyanivery Standalone Signed Android Apps

This project compiles 5 independent, standalone, signed APKs for each Elyanivery portal:
1. **Elyanivery-Customer-signed.apk** (`com.elyanivery.customer`) -> `/customer`
2. **Elyanivery-Courier-signed.apk** (`com.elyanivery.courier`) -> `/courier`
3. **Elyanivery-Partner-signed.apk** (`com.elyanivery.partner`) -> `/partner`
4. **Elyanivery-Admin-signed.apk** (`com.elyanivery.admin`) -> `/admin`
5. **Elyanivery-Support-signed.apk** (`com.elyanivery.support`) -> `/support`

---

## 🔑 Release Signing Key Included
All APKs are signed with the included keystore:
- **Keystore file**: `android/keystore/elyanivery.keystore`
- **Keystore password**: `elyanivery`
- **Key alias**: `elyanivery`
- **Key password**: `elyanivery`
- **Signature schemes**: v1 (JAR signing) + v2 (APK Signature Scheme v2) enabled.

---

## ⚡ How to Build in Windows Command Prompt (CMD)

### Step 1: Check your Java Version (Important!)
Android Gradle Plugin requires **Java 17** or **Java 21**.
If you saw `* What went wrong: 25.0.4.1`, that means your CMD is using an experimental **Java 25**.

To install official **Java 17** in 1 minute using Windows CMD:
```cmd
winget install EclipseAdoptium.Temurin.17.JDK
```
Or if you have Android Studio installed, it already includes Java 17 inside `C:\Program Files\Android\Android Studio\jbr`.

### Step 2: Build All 5 Signed APKs
In Windows CMD, simply run:
```cmd
cd android
build-all-apks.bat
```

Or run via Gradle wrapper directly:
```cmd
gradlew.bat assembleRelease
```

### Step 3: Collect your APKs
Once finished, all 5 APKs will be signed and ready in `dist-apks\`:
- `dist-apks\Elyanivery-Customer-signed.apk`
- `dist-apks\Elyanivery-Courier-signed.apk`
- `dist-apks\Elyanivery-Partner-signed.apk`
- `dist-apks\Elyanivery-Admin-signed.apk`
- `dist-apks\Elyanivery-Support-signed.apk`

Transfer any of these `.apk` files to your phone and install them directly!
