plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "mk.scgpilot.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "mk.scgpilot.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    buildFeatures { buildConfig = true }

    buildTypes.all {
        val configuredUrl = providers.gradleProperty("scgPilotUrl")
            .orElse("https://scg-pilot.onrender.com/")
        buildConfigField("String", "SCG_PILOT_URL", "\"${configuredUrl.get()}\"")
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-ktx:1.10.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
}
