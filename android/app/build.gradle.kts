plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.jawaadalah.youragent"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.jawaadalah.youragent"
        minSdk = 24
        targetSdk = 35
        versionCode = 100
        versionName = "1.0.0"
    }

    // Tanda tangan debug TETAP (sejak v12.1): keystore yang sama di setiap
    // build membuat APK bisa dipasang sebagai UPDATE tanpa uninstall dulu.
    // Ini keystore khusus debug (bukan untuk rilis Play Store).
    signingConfigs {
        create("fixedDebug") {
            storeFile = rootProject.file("debug.p12")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
            storeType = "PKCS12"
        }
    }

    buildTypes {
        debug {
            signingConfig = signingConfigs.getByName("fixedDebug")
            // Optimasi APK (v12.3): R8 memangkas & mengoptimalkan kode,
            // shrinkResources membuang resource tak terpakai — APK jauh
            // lebih kecil & lebih cepat, fungsi tetap sama.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
}
