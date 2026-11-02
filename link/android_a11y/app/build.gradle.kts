plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
  namespace = "org.royaltiger.link"; compileSdk = 34
  defaultConfig { applicationId = "org.royaltiger.link"; minSdk = 26; targetSdk = 34; versionCode = 3; versionName = "0.3" }
  kotlinOptions { jvmTarget = "17" }
  compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}
dependencies { implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1") }
