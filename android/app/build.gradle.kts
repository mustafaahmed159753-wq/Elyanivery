plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.elyanivery.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.elyanivery.app"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildFeatures {
        buildConfig = true
    }

    flavorDimensions += "portal"
    productFlavors {
        create("customer") {
            dimension = "portal"
            applicationId = "com.elyanivery.customer"
            manifestPlaceholders["appName"] = "Elyanivery"
            buildConfigField("String", "APP_URL", "\"https://ais-dev-eko535lqz7wwumxkhgzonp-524208193732.europe-west2.run.app/customer\"")
        }
        create("courier") {
            dimension = "portal"
            applicationId = "com.elyanivery.courier"
            manifestPlaceholders["appName"] = "Elyanivery Courier"
            buildConfigField("String", "APP_URL", "\"https://ais-dev-eko535lqz7wwumxkhgzonp-524208193732.europe-west2.run.app/courier\"")
        }
        create("partner") {
            dimension = "portal"
            applicationId = "com.elyanivery.partner"
            manifestPlaceholders["appName"] = "Elyanivery Partner"
            buildConfigField("String", "APP_URL", "\"https://ais-dev-eko535lqz7wwumxkhgzonp-524208193732.europe-west2.run.app/partner\"")
        }
        create("admin") {
            dimension = "portal"
            applicationId = "com.elyanivery.admin"
            manifestPlaceholders["appName"] = "Elyanivery Admin"
            buildConfigField("String", "APP_URL", "\"https://ais-dev-eko535lqz7wwumxkhgzonp-524208193732.europe-west2.run.app/admin\"")
        }
        create("support") {
            dimension = "portal"
            applicationId = "com.elyanivery.support"
            manifestPlaceholders["appName"] = "Elyanivery Support"
            buildConfigField("String", "APP_URL", "\"https://ais-dev-eko535lqz7wwumxkhgzonp-524208193732.europe-west2.run.app/support\"")
        }
    }

    signingConfigs {
        create("release") {
            val ksFile = rootProject.file("keystore/elyanivery.keystore")
            if (ksFile.exists()) {
                storeFile = ksFile
                storePassword = "elyanivery"
                keyAlias = "elyanivery"
                keyPassword = "elyanivery"
                enableV1Signing = true
                enableV2Signing = true
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }

    kotlinOptions {
        jvmTarget = "1.8"
    }

    lint {
        checkReleaseBuilds = false
        abortOnError = false
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.activity:activity-ktx:1.8.2")
}
