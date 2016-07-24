.. image:: resources/slidewords-feature.png
   :align: center

SlideWords 0.3.2
================

A challenging word search game for 1 or 2 players.

Building for Android
====================

Assumes you are running all commands from the root of the source directory (i.e. where you found this INSTALL file).

Pre-req: Install buildozer (and its dependencies)
-------------------------------------------------

See https://github.com/kivy/buildozer

Pre-req: Google play services
-----------------------------

Run::

    ~/.buildozer/android/platform/android-sdk-20/tools/android) to get the google-play-services_lib from extras

Then::

    cp -r ~/.buildozer/android/platform/android-sdk-20/extras/google/google_play_services/libproject/google-play-services_lib libs
    ~/.buildozer/android/platform/android-sdk-20/tools/android update lib-project --path libs/google-play-services_lib --target 1

Also copy from google extras Android Support::

    cp -r ~/.buildozer/android/platform/android-sdk-20/extras/android/support/v4/android-support-v4.jar


To build for the google play store
----------------------------------

(NOTE: You may need to install jarsigner as well)

Before you will be able to make a successful build make sure the google play service ID's are read into the app (the destination folder won't exist until you have run "buildozer android [debug/release]" at least one time)::

    rsync -rav ./google_play_ids.xml .buildozer/android/platform/python-for-android/dist/slidewords/res/values/

Then run::

    buildozer android release
    jarsigner -verbose -sigalg SHA1withRSA -digestalg SHA1 -keystore ~/SlideWordsKey.keystore bin/SlideWords-0.3.2-release-unsigned.apk slidewords
    ~/.buildozer/android/platform/android-sdk-20/tools/zipalign -v 4 bin/SlideWords-0.3.2-release-unsigned.apk bin/SlideWords-0.3.2-release.apk

To generate a new key::

    keytool -genkey -v -keystore SlideWordsKey.keystore -alias slidewords -keyalg RSA -keysize 2048 -validity 10000

Alternatively, this script will sign and align the APK for you and then deploy it to the device (assuming it is plugged in with developer mode enabled)::

    ./test_android_release

