[app]

title = Business Command Center

package.name = businessdashboard

package.domain = org.businessdashboard

source.dir = .

source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt

version = 0.1.0

requirements = python3,kivy

orientation = portrait

fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE

android.api = 35

android.minapi = 23

android.archs = arm64-v8a

android.allow_backup = True

[buildozer]

log_level = 2

warn_on_root = 1
