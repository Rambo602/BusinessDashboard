#!/usr/bin/env python3
# patch_v32.py - RAMBO AI accessibility service (see the screen, tap, type)
# Run from ~/BusinessDashboard:  python patch_v32.py
# Backs up main.py and buildozer.spec first. Aborts if an anchor is missing.
import os, sys, shutil, py_compile

ROOT = os.getcwd()
MAIN = os.path.join(ROOT, "main.py")
SPEC = os.path.join(ROOT, "buildozer.spec")


def die(msg):
    print("STOPPED: " + msg)
    sys.exit(1)


if not os.path.exists(MAIN) or not os.path.exists(SPEC):
    die("run this from ~/BusinessDashboard (main.py / buildozer.spec not found)")

main = open(MAIN).read()
spec = open(SPEC).read()

if "def acc_route" in main:
    die("patch already applied")

A1 = "CRASH_PATH = [None]\n"
A2 = '    def local_route(self, text, low):\n        if low.startswith("pc:"):\n'
if main.count(A1) != 1:
    die("anchor 1 (CRASH_PATH) missing in main.py")
if main.count(A2) != 1:
    die("anchor 2 (local_route) missing in main.py")
if "android.allow_backup = True" not in spec:
    die("anchor in buildozer.spec missing (android.allow_backup)")

# ---------------- Java service ----------------
JAVA = r'''package org.rambo.acc;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Path;
import android.graphics.Rect;
import android.os.Bundle;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;
import java.util.ArrayList;
import java.util.List;

public class RamboAccService extends AccessibilityService {
    public static volatile RamboAccService inst = null;

    @Override
    protected void onServiceConnected() {
        inst = this;
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
    }

    @Override
    public void onInterrupt() {
    }

    @Override
    public boolean onUnbind(Intent intent) {
        inst = null;
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        inst = null;
        super.onDestroy();
    }

    public static boolean isOn() {
        return inst != null;
    }

    private static List<AccessibilityNodeInfo> roots() {
        List<AccessibilityNodeInfo> out = new ArrayList<AccessibilityNodeInfo>();
        RamboAccService s = inst;
        if (s == null) {
            return out;
        }
        try {
            AccessibilityNodeInfo r = s.getRootInActiveWindow();
            if (r != null) {
                out.add(r);
                return out;
            }
            List<AccessibilityWindowInfo> ws = s.getWindows();
            if (ws != null) {
                for (AccessibilityWindowInfo w : ws) {
                    AccessibilityNodeInfo n = w.getRoot();
                    if (n != null) {
                        out.add(n);
                    }
                }
            }
        } catch (Exception e) {
        }
        return out;
    }

    public static String currentPackage() {
        for (AccessibilityNodeInfo r : roots()) {
            CharSequence p = r.getPackageName();
            if (p != null) {
                return p.toString();
            }
        }
        return "";
    }

    public static String screenText() {
        StringBuilder sb = new StringBuilder();
        for (AccessibilityNodeInfo r : roots()) {
            dump(r, sb, 0);
        }
        return sb.toString();
    }

    private static void dump(AccessibilityNodeInfo n, StringBuilder sb, int depth) {
        if (n == null || sb.length() > 8000 || depth > 40) {
            return;
        }
        if (!n.isVisibleToUser()) {
            return;
        }
        String line = "";
        if (!n.isPassword()) {
            CharSequence t = n.getText();
            CharSequence d = n.getContentDescription();
            if (t != null && t.length() > 0) {
                line = t.toString();
            } else if (d != null && d.length() > 0) {
                line = d.toString();
            }
        }
        if (line.length() > 300) {
            line = line.substring(0, 300);
        }
        if (line.length() > 0) {
            String tag = n.isEditable() ? "[input] " : (n.isClickable() ? "[tap] " : "");
            sb.append(tag).append(line.replace("\n", " ")).append("\n");
        } else if (n.isEditable()) {
            sb.append("[input] (empty)\n");
        }
        int cnt = n.getChildCount();
        for (int i = 0; i < cnt; i++) {
            dump(n.getChild(i), sb, depth + 1);
        }
    }

    private static AccessibilityNodeInfo find(AccessibilityNodeInfo n, String q, boolean exact, int depth) {
        if (n == null || depth > 40) {
            return null;
        }
        String t = n.getText() == null ? "" : n.getText().toString().toLowerCase();
        String d = n.getContentDescription() == null ? "" : n.getContentDescription().toString().toLowerCase();
        boolean hit = exact ? (t.equals(q) || d.equals(q)) : (t.contains(q) || d.contains(q));
        if (hit && n.isVisibleToUser()) {
            return n;
        }
        int cnt = n.getChildCount();
        for (int i = 0; i < cnt; i++) {
            AccessibilityNodeInfo r = find(n.getChild(i), q, exact, depth + 1);
            if (r != null) {
                return r;
            }
        }
        return null;
    }

    private static AccessibilityNodeInfo firstEditable(AccessibilityNodeInfo n, int depth) {
        if (n == null || depth > 40) {
            return null;
        }
        if (n.isEditable() && n.isVisibleToUser()) {
            return n;
        }
        int cnt = n.getChildCount();
        for (int i = 0; i < cnt; i++) {
            AccessibilityNodeInfo r = firstEditable(n.getChild(i), depth + 1);
            if (r != null) {
                return r;
            }
        }
        return null;
    }

    private static AccessibilityNodeInfo findScrollable(AccessibilityNodeInfo n, int depth) {
        if (n == null || depth > 40) {
            return null;
        }
        if (n.isScrollable() && n.isVisibleToUser()) {
            return n;
        }
        int cnt = n.getChildCount();
        for (int i = 0; i < cnt; i++) {
            AccessibilityNodeInfo r = findScrollable(n.getChild(i), depth + 1);
            if (r != null) {
                return r;
            }
        }
        return null;
    }

    private static boolean clickNode(AccessibilityNodeInfo n) {
        AccessibilityNodeInfo p = n;
        int guard = 0;
        while (p != null && guard < 8) {
            if (p.isClickable() && p.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                return true;
            }
            p = p.getParent();
            guard++;
        }
        Rect rc = new Rect();
        n.getBoundsInScreen(rc);
        return tap(rc.centerX(), rc.centerY());
    }

    public static boolean clickText(String q) {
        String low = q.toLowerCase().trim();
        for (AccessibilityNodeInfo r : roots()) {
            AccessibilityNodeInfo hit = find(r, low, true, 0);
            if (hit == null) {
                hit = find(r, low, false, 0);
            }
            if (hit != null) {
                return clickNode(hit);
            }
        }
        return false;
    }

    private static AccessibilityNodeInfo inputNode() {
        for (AccessibilityNodeInfo r : roots()) {
            AccessibilityNodeInfo f = r.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
            if (f == null || !f.isEditable()) {
                f = firstEditable(r, 0);
            }
            if (f != null) {
                return f;
            }
        }
        return null;
    }

    public static boolean typeText(String s) {
        AccessibilityNodeInfo f = inputNode();
        if (f == null) {
            return false;
        }
        f.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        Bundle b = new Bundle();
        b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, s);
        return f.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, b);
    }

    public static boolean pasteText() {
        AccessibilityNodeInfo f = inputNode();
        if (f == null) {
            return false;
        }
        f.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        return f.performAction(AccessibilityNodeInfo.ACTION_PASTE);
    }

    public static boolean setClip(String s) {
        RamboAccService x = inst;
        if (x == null) {
            return false;
        }
        try {
            ClipboardManager cm = (ClipboardManager) x.getSystemService(Context.CLIPBOARD_SERVICE);
            cm.setPrimaryClip(ClipData.newPlainText("rambo", s));
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    public static boolean tap(int x, int y) {
        RamboAccService s = inst;
        if (s == null) {
            return false;
        }
        Path p = new Path();
        p.moveTo(x, y);
        GestureDescription.Builder b = new GestureDescription.Builder();
        b.addStroke(new GestureDescription.StrokeDescription(p, 0, 80));
        return s.dispatchGesture(b.build(), null, null);
    }

    public static boolean back() {
        RamboAccService s = inst;
        return s != null && s.performGlobalAction(GLOBAL_ACTION_BACK);
    }

    public static boolean home() {
        RamboAccService s = inst;
        return s != null && s.performGlobalAction(GLOBAL_ACTION_HOME);
    }

    public static boolean scroll(boolean forward) {
        for (AccessibilityNodeInfo r : roots()) {
            AccessibilityNodeInfo sc = findScrollable(r, 0);
            if (sc != null) {
                return sc.performAction(forward
                        ? AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
                        : AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD);
            }
        }
        return false;
    }
}
'''

CONFIG_XML = '''<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:accessibilityEventTypes="typeWindowStateChanged"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:accessibilityFlags="flagDefault|flagRetrieveInteractiveWindows|flagIncludeNotImportantViews"
    android:canRetrieveWindowContent="true"
    android:canPerformGestures="true"
    android:notificationTimeout="100"
    android:description="@string/rambo_acc_desc" />
'''

STRINGS_XML = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="rambo_acc_desc">Lets RAMBO AI read the screen and tap or type for you when you ask. Password fields are never read.</string>
</resources>
'''

MANIFEST_XML = '''<service android:name="org.rambo.acc.RamboAccService"
    android:exported="true"
    android:label="RAMBO AI"
    android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE">
    <intent-filter>
        <action android:name="android.accessibilityservice.AccessibilityService" />
    </intent-filter>
    <meta-data android:name="android.accessibilityservice"
        android:resource="@xml/rambo_acc_config" />
</service>
'''

# ---------------- Python additions ----------------
ACC_HELP_CONST = '''CRASH_PATH = [None]

ACC_HELP = ("Accessibility commands: acc settings | acc status | acc screen | "
            "acc tap <text> | acc tapxy <x> <y> | acc type <text> | acc clip <text> | "
            "acc paste | acc scroll down | acc scroll up | acc back | acc home. "
            "Add 'in 5' in front to wait 5 seconds so you can switch apps first, "
            "for example: in 5 acc screen")
'''

ACC_METHODS = '''    # ---------- accessibility (see the screen, tap, type) ----------

    def acc_route(self, text, low):
        m = re.match(r"^in\\s+(\\d{1,3})\\s+(acc(?:\\s.*)?)$", text, re.I)
        if m:
            secs = int(m.group(1))
            inner = m.group(2)

            def later():
                time.sleep(secs)
                try:
                    short, full = self.acc_run(inner)
                except Exception as e:
                    short, full = "acc error: " + str(e)[:120], None
                shown = full or short

                def post(dt):
                    self.add_msg(shown, False)
                    try:
                        self.notify("RAMBO AI", short[:100])
                    except Exception:
                        pass
                Clock.schedule_once(post, 0)

            threading.Thread(target=later, daemon=True).start()
            return "Okay. Running " + inner + " in %d seconds. Switch to the other app now." % secs
        if low == "acc" or low.startswith("acc "):
            short, full = self.acc_run(text)
            if full:
                self.add_msg(full, False)
            return short
        return None

    def acc_run(self, text):
        body = text.strip()[3:].strip()
        low = body.lower()
        try:
            from jnius import autoclass
            S = autoclass("org.rambo.acc.RamboAccService")
        except Exception as e:
            return ("Accessibility code is not in this build.", None)
        if low in ("", "help"):
            return (ACC_HELP, None)
        if low == "settings":
            PA = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            Settings = autoclass("android.provider.Settings")
            PA.mActivity.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            return ("Opened Accessibility settings. Find RAMBO AI and turn it on.", None)
        on = bool(S.isOn())
        if low == "status":
            return ("Accessibility is ON." if on else
                    "Accessibility is OFF. Say: acc settings, then turn on RAMBO AI.", None)
        if not on:
            return ("Accessibility is OFF. Say: acc settings, then turn on RAMBO AI.", None)
        if low == "screen":
            s = str(S.screenText() or "").strip()
            pkg = str(S.currentPackage() or "?")
            if not s:
                return ("Screen read came back empty (app: " + pkg + ").", None)
            n = len(s.splitlines())
            return ("Read %d lines from %s." % (n, pkg), "SCREEN (" + pkg + ")\\n" + s[:3500])
        if low.startswith("tapxy "):
            p = body[6:].split()
            if len(p) != 2 or not all(x.isdigit() for x in p):
                return ("Use: acc tapxy 500 900", None)
            ok = bool(S.tap(int(p[0]), int(p[1])))
            return ("Tapped." if ok else "Tap failed.", None)
        if low.startswith("tap "):
            t = body[4:].strip()
            ok = bool(S.clickText(t))
            return (("Tapped " + t + ".") if ok else ("Could not find " + t + " on screen."), None)
        if low.startswith("type "):
            ok = bool(S.typeText(body[5:]))
            return ("Typed." if ok else "No text box found on screen.", None)
        if low.startswith("clip "):
            ok = bool(S.setClip(body[5:]))
            return ("Copied to clipboard." if ok else "Clipboard failed.", None)
        if low == "paste":
            ok = bool(S.pasteText())
            return ("Pasted." if ok else "Paste failed (no text box found).", None)
        if low in ("scroll down", "scroll up"):
            ok = bool(S.scroll(low == "scroll down"))
            return ("Scrolled." if ok else "Nothing to scroll.", None)
        if low == "back":
            return ("Back." if bool(S.back()) else "Back failed.", None)
        if low == "home":
            return ("Home." if bool(S.home()) else "Home failed.", None)
        return ("Unknown acc command. Say: acc help", None)

    def local_route(self, text, low):
        r_acc = self.acc_route(text, low)
        if r_acc is not None:
            return r_acc
        if low.startswith("pc:"):
'''

# ---------------- apply ----------------
shutil.copy(MAIN, MAIN + ".bak32")
shutil.copy(SPEC, SPEC + ".bak32")

new_main = main.replace(A1, ACC_HELP_CONST, 1)
new_main = new_main.replace(A2, ACC_METHODS, 1)
with open(MAIN, "w") as f:
    f.write(new_main)
try:
    py_compile.compile(MAIN, doraise=True, cfile="_main_check.pyc")
except Exception as e:
    shutil.copy(MAIN + ".bak32", MAIN)
    die("main.py failed to compile, restored backup: " + str(e)[:200])

os.makedirs(os.path.join(ROOT, "java/org/rambo/acc"), exist_ok=True)
os.makedirs(os.path.join(ROOT, "res/xml"), exist_ok=True)
os.makedirs(os.path.join(ROOT, "res/values"), exist_ok=True)
with open(os.path.join(ROOT, "java/org/rambo/acc/RamboAccService.java"), "w") as f:
    f.write(JAVA)
with open(os.path.join(ROOT, "res/xml/rambo_acc_config.xml"), "w") as f:
    f.write(CONFIG_XML)
with open(os.path.join(ROOT, "res/values/rambo_acc_strings.xml"), "w") as f:
    f.write(STRINGS_XML)
with open(os.path.join(ROOT, "manifest_service.xml"), "w") as f:
    f.write(MANIFEST_XML)

if "android.add_src" not in spec:
    spec = spec.replace(
        "android.allow_backup = True",
        "android.allow_backup = True\n\n"
        "android.add_src = java\n\n"
        "android.add_resources = res\n\n"
        "android.extra_manifest_application_xml = %(source.dir)s/manifest_service.xml",
        1)
    with open(SPEC, "w") as f:
        f.write(spec)

print("OK_PATCHED")
print("main.py backup: main.py.bak32 | spec backup: buildozer.spec.bak32")
print("New files: java/org/rambo/acc/RamboAccService.java, res/xml, res/values, manifest_service.xml")
