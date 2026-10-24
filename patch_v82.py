p = "/data/data/com.termux/files/home/BusinessDashboard/main.py"
s = open(p).read()

A1 = '"done: arg is the final answer for the user. Never use rm -rf'
N1 = ('"open: arg is an app name or package to open (e.g. chrome or com.android.chrome); returns what is on its screen. '
      'tap: arg is a button label to tap in the current app; returns the new screen. '
      'read: returns the current screen text. home: returns to RAMBO AI. '
      'For multi-app goals: open the app, tap or read, then home, then done. "\n                '
      + A1)

A2 = '                elif act == "claude" and arg:\n                    out = self._v75_claude(arg)\n'
N2 = A2 + ('                elif act == "open" and arg:\n                    out = self._v82_open(arg)\n'
           '                elif act == "tap" and arg:\n                    out = self._v82_tap(arg)\n'
           '                elif act == "read":\n                    out = self._v82_read()\n'
           '                elif act == "home":\n                    out = self._v82_home()\n')

A3 = '                    self._v75_say("DONE: " + arg[:1500])\n                    return'
N3 = '                    self._v82_log(goal, hist, arg)\n' + A3

A4 = '    def _v75_thread(self, goal):'
N4 = '''    def _v82_log(self, goal, steps, result):
        try:
            import os, json, time
            f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rambo_log.json")
            try:
                data = json.load(open(f))
            except Exception:
                data = []
            data.append({"time": time.time(), "goal": goal, "steps": steps, "result": result})
            json.dump(data, open(f, "w"), indent=2)
        except Exception as e:
            self.err("v82 log", e)

    def _v82_read(self):
        try:
            from jnius import autoclass
            S = getattr(self, "_v81_S", None) or autoclass("org.rambo.acc.RamboAccService")
            pk = str(S.currentPackage() or "")
            tx = str(S.screenText() or "").replace("\\n", " | ")
            return "[%s] %s" % (pk, tx[:1200])
        except Exception as e:
            return "Could not read screen: " + str(e)[:100]

    def _v82_open(self, name):
        try:
            from jnius import autoclass
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            Intent = autoclass("android.content.Intent")
            pm = act.getPackageManager()
            pkg = name.strip()
            if "." not in pkg:
                low, found = pkg.lower(), ""
                apps = pm.getInstalledApplications(0)
                for i in range(apps.size()):
                    ai = apps.get(i)
                    try:
                        lab = str(pm.getApplicationLabel(ai)).lower()
                    except Exception:
                        continue
                    if low in lab and pm.getLaunchIntentForPackage(ai.packageName):
                        found = str(ai.packageName)
                        break
                if not found:
                    return "App not found: " + name + ". Try the package name."
                pkg = found
            li = pm.getLaunchIntentForPackage(pkg)
            if li is None:
                return "Cannot launch " + pkg
            li.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            self._v78_stat("Opening " + pkg)
            act.startActivity(li)
            time.sleep(4)
            return self._v82_read()
        except Exception as e:
            return "Open failed: " + str(e)[:100]

    def _v82_tap(self, label):
        self._v78_stat("Tapping " + label[:30])
        short, _f = self.acc_run("acc tap " + label)
        time.sleep(2)
        return str(short) + " | " + self._v82_read()

    def _v82_home(self):
        self._v75_front()
        time.sleep(2)
        return "Back in RAMBO AI"

''' + A4

for a in (A1, A2, A3, A4):
    if s.count(a) != 1:
        raise SystemExit("ANCHOR PROBLEM, nothing changed: " + a[:50])
s = s.replace(A1, N1).replace(A2, N2).replace(A3, N3).replace(A4, N4)
open(p, "w").write(s)
print("patched")
