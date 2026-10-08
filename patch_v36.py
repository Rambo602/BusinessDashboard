#!/usr/bin/env python3
# patch_v36.py - undo the overlay-activity route from v35 (it broke the assistant picker)
# and instead start the mic as soon as the hold button opens the main app.
# Run from ~/BusinessDashboard AFTER v35:  python patch_v36.py
import os, re, sys, shutil, py_compile

ROOT = os.getcwd()
MAIN = os.path.join(ROOT, "main.py")
SPEC = os.path.join(ROOT, "buildozer.spec")
MANI = os.path.join(ROOT, "manifest_service.xml")
IFIL = os.path.join(ROOT, "intent_filters.xml")
JAVA = os.path.join(ROOT, "java/org/rambo/acc/AssistOverlayActivity.java")


def die(msg):
    print("STOPPED: " + msg)
    sys.exit(1)


for p in (MAIN, SPEC, MANI):
    if not os.path.exists(p):
        die("run this from ~/BusinessDashboard (missing " + os.path.basename(p) + ")")
main, spec, mani = open(MAIN).read(), open(SPEC).read(), open(MANI).read()

if "_rambo_assist_hook" not in main:
    die("apply patch_v35.py first")
if "def _rambo_intent" in main:
    die("patch v36 already applied")

A1 = "            activity.bind(on_new_intent=self._rambo_say_check)\n"
A2 = "            return self._rambo_say_check(PA.mActivity.getIntent())\n"
A3 = "    def _rambo_assist_hook(self):\n"
for n, a in (("bind line", A1), ("getIntent line", A2), ("hook def", A3)):
    if main.count(a) != 1:
        die("anchor missing or not unique in main.py: " + n)

NEW = r'''    def _rambo_intent(self, intent):
        # hold button = ASSIST intent: open the mic right away
        try:
            if intent is None:
                return False
            if self._rambo_say_check(intent):
                return True
            act = intent.getAction()
            if act is None or str(act) != "android.intent.action.ASSIST":
                return False
            if int(intent.getFlags()) & 0x00100000:
                return False  # restored from recents, not a fresh hold
            if time.time() - getattr(self, "_as_t", 0) < 4:
                return False
            self._as_t = time.time()
            Clock.schedule_once(lambda dt: self.on_mic(None), 0.5)
            return True
        except Exception as e:
            self.err("assist intent", e)
            return False

'''

for p in (MAIN, SPEC, MANI):
    shutil.copy(p, p + ".bak36p")

new = main.replace(A1, "            activity.bind(on_new_intent=self._rambo_intent)\n", 1)
new = new.replace(A2, "            return self._rambo_intent(PA.mActivity.getIntent())\n", 1)
new = new.replace(A3, NEW + A3, 1)
open(MAIN, "w").write(new)
try:
    py_compile.compile(MAIN, doraise=True, cfile="_main_check.pyc")
except Exception as e:
    shutil.copy(MAIN + ".bak36p", MAIN)
    die("main.py failed to compile, restored backup: " + str(e)[:300])
try:
    os.remove("_main_check.pyc")
except Exception:
    pass

# put the assist filter back on the main screen (known to list RAMBO AI)
if not os.path.exists(IFIL) or "android.intent.action.ASSIST" not in open(IFIL).read():
    open(IFIL, "w").write('<intent-filter><action android:name="android.intent.action.ASSIST"/>'
                          '<category android:name="android.intent.category.DEFAULT"/></intent-filter>\n')
if not re.search(r"^android\.manifest\.intent_filters", spec, re.M):
    if re.search(r"^android\.allow_backup = True", spec, re.M):
        spec = re.sub(r"^(android\.allow_backup = True\n?)",
                      r"\1android.manifest.intent_filters = intent_filters.xml\n", spec, count=1, flags=re.M)
    else:
        spec = spec.rstrip("\n") + "\nandroid.manifest.intent_filters = intent_filters.xml\n"
    open(SPEC, "w").write(spec)
if not re.search(r"^android\.manifest\.intent_filters", open(SPEC).read(), re.M):
    shutil.copy(MAIN + ".bak36p", MAIN)
    die("could not restore the assist line in buildozer.spec")

# remove the overlay activity so it cannot compete
mani2 = re.sub(r'<activity android:name="org\.rambo\.acc\.AssistOverlayActivity".*?</activity>\n?',
               "", mani, flags=re.S)
open(MANI, "w").write(mani2)
if os.path.exists(JAVA):
    os.remove(JAVA)

print("OK_PATCHED_V36")
print("Assist filter is back on the main screen; overlay activity removed.")
