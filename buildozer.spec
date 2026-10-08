[app]
android.accept_sdk_license = True

title = RAMBO AI
icon.filename = %(source.dir)s/icon.png

package.name = businessdashboard

package.domain = org.businessdashboard

source.dir = .

source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt

version = 1.5.8

requirements = python3==3.11.5,hostpython3==3.11.5,kivy

orientation = portrait

fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,CAMERA,RECORD_AUDIO,WAKE_LOCK,RECEIVE_BOOT_COMPLETED,QUERY_ALL_PACKAGES,REQUEST_INSTALL_PACKAGES,REQUEST_INSTALL_PACKAGES,com.android.alarm.permission.SET_ALARM,POST_NOTIFICATIONS,FOREGROUND_SERVICE,FOREGROUND_SERVICE_DATA_SYNC

android.api = 33
android.ndk = 25b

android.minapi = 24

android.archs = arm64-v8a

android.allow_backup = True

android.add_src = java

android.add_resources = res

android.extra_manifest_application_xml = %(source.dir)s/manifest_service.xml

[buildozer]

log_level = 2

warn_on_root = 1

android.ndk_api = 24