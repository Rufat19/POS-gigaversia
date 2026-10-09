# RoBo POS for Android

The Android app opens the POS server in a WebView. On first launch, enter the server URL; it is saved in the app's private preferences on that device and reused on later launches. To change it, open the app menu and choose **Server ünvanını dəyiş**.

The app requires Android 6.0 (API 23) or later and an internet connection. The URL must include `http://` or `https://`. HTTPS is recommended. HTTP is available for trusted local servers. Links to other sites open in the device browser. Receipt printing uses Android's system print dialog; choose a compatible printer there.

## Build the APK with Android Studio

1. Install Android Studio and its Android SDK Platform 36 and Build Tools.
2. Open this `android` folder as a project and allow Gradle sync to finish. Use JDK 17 for Gradle (in Android Studio: **Settings > Build, Execution, Deployment > Build Tools > Gradle > Gradle JDK**). Newer JDK releases may not be supported by the pinned Gradle version.
3. Select **Build > Build Bundle(s) / APK(s) > Build APK(s)**.
4. The debug APK is created at `android\app\build\outputs\apk\debug\app-debug.apk`. For a quick test, copy it to the Android tablet and install it. Android may ask to allow installation from that file manager.

The debug APK is for testing. For a distributable release, create a signed APK from **Build > Generate Signed Bundle / APK** in Android Studio and keep the signing key private. Upload the APK to the Railway persistent volume and set `ANDROID_APK_PATH` to its full path so the admin page can serve it.
