import sys, shutil, py_compile
F = "main.py"
s = open(F, encoding="utf-8").read()
if "V78_STICKY" in s:
    sys.exit("Already patched (v78).")
shutil.copy(F, F + ".bak78")
H = r'''    def _v78_stat(self, msg):  # V78_STICKY
        self._v78_msg = str(msg).replace("\n", " ")[:55]

    def _v78_start(self):
        self._v78_on = True
        self._v78_msg = "starting"
        threading.Thread(target=self._v78_loop, daemon=True).start()

    def _v78_loop(self):
        try:
            from jnius import autoclass
            from android.runnable import run_on_ui_thread
            Toast = autoclass("android.widget.Toast")
            JS = autoclass("java.lang.String")
            act = autoclass("org.kivy.android.PythonActivity").mActivity
        except Exception as e:
            self.err("v78 toast", e)
            return
        box = {"t": None}

        @run_on_ui_thread
        def show(m):
            try:
                if box["t"] is not None:
                    box["t"].cancel()
                box["t"] = Toast.makeText(act, JS(m), 1)
                box["t"].show()
            except Exception:
                pass

        while getattr(self, "_v78_on", False):
            show("AUTO RUNNING: " + getattr(self, "_v78_msg", "working"))
            time.sleep(3)
        show("AUTO: finished")

'''
A1 = "    def _v72_status(self, msg):\n"
N1 = A1 + '        self._v78_msg = str(msg).replace("\\n", " ")[:55]\n'
A2 = "    def _v75_thread(self, goal):\n        self.ka(True)\n"
N2 = "    def _v75_thread(self, goal):\n        self.ka(True)\n        self._v78_start()\n"
A3 = ('            self._v75_say("Goal stopped by an error: " + str(e)[:120])\n'
      '        finally:\n'
      '            self.ka(False)\n')
N3 = A3 + '            self._v78_on = False\n'
A4 = '        time.sleep(8)\n        for lab in ("Send message", "Send"):\n'
N4 = '        time.sleep(8)\n        self._v78_stat("Tapping Send in Claude")\n        for lab in ("Send message", "Send"):\n'
A5 = '        while not self._v75_stop and time.time() - t0 < 150:\n            time.sleep(5)\n'
N5 = A5 + '            self._v78_stat("Waiting for Claude (%ds)" % int(time.time() - t0))\n'
A6 = "    def _v75_front(self):\n"
try:
    for a in (A1, A2, A3, A4, A5, A6):
        if s.count(a) != 1:
            raise Exception("anchor count %d for %r" % (s.count(a), a.strip()[:50]))
    s = (s.replace(A1, N1, 1).replace(A2, N2, 1).replace(A3, N3, 1)
          .replace(A4, N4, 1).replace(A5, N5, 1).replace(A6, H + A6, 1))
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak78", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v78 OK")
