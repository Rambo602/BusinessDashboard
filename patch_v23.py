import shutil
import sys

P = ".github/workflows/build.yml"
lines = open(P, encoding="utf-8").read().split("\n")

if any("Re-sign APK" in ln for ln in lines):
    print("ABORT: already patched")
    sys.exit(1)

up = None
for i, ln in enumerate(lines):
    if "actions/upload-artifact" in ln:
        up = i
        break
if up is None:
    print("ABORT: upload-artifact step not found")
    sys.exit(1)

j = up
while j >= 0 and not lines[j].lstrip().startswith("- "):
    j -= 1
if j < 0:
    print("ABORT: could not find start of upload step")
    sys.exit(1)

step = [
    "      - name: Re-sign APK with permanent key",
    "        run: |",
    "          set -e",
    "          KS=$HOME/.android/debug.keystore",
    "          keytool -list -keystore $KS -storepass android | grep -q 'F8:34:B8:F4' || { echo WRONG-KEYSTORE-IN-SECRET; keytool -list -keystore $KS -storepass android | grep SHA256; exit 1; }",
    "          AS=$(find $HOME/.buildozer -type f -name apksigner -path '*build-tools*' | sort | tail -1)",
    "          echo using $AS",
    "          for f in bin/*.apk; do $AS sign --ks $KS --ks-pass pass:android --key-pass pass:android --ks-key-alias androiddebugkey $f; $AS verify --print-certs $f | grep SHA-256; done",
]

shutil.copy(P, P + ".bak23")
lines[j:j] = step
open(P, "w", encoding="utf-8").write("\n".join(lines))
print("PATCH_V23_OK")
