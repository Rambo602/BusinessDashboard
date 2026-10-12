[app]
p4a.source_dir = ./p4a-src
android.accept_sdk_license = True

title = RAMBO AI
icon.filename = %(source.dir)s/icon.png

package.name = businessdashboard

package.domain = org.businessdashboard

source.dir = .

source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt

version = 1.6.67
requirements = python3==3.11.5,hostpython3==3.11.5,kivy,sqlite3,certifi,openssl

orientation = portrait

fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,CAMERA,RECORD_AUDIO,WAKE_LOCK,RECEIVE_BOOT_COMPLETED,QUERY_ALL_PACKAGES,REQUEST_INSTALL_PACKAGES,REQUEST_INSTALL_PACKAGES,com.android.alarm.permission.SET_ALARM,POST_NOTIFICATIONS,FOREGROUND_SERVICE,FOREGROUND_SERVICE_DATA_SYNC,com.termux.permission.RUN_COMMAND

android.api = 33
android.ndk = 25b

android.minapi = 24

android.archs = arm64-v8a

android.allow_backup = True
android.manifest.intent_filters = intent_filters.xml

android.add_src = java
android.add_activities = org.rambo.acc.AssistOverlayActivity

android.add_resources = res


[buildozer]

log_level = 2

warn_on_root = 1

android.ndk_api = 24