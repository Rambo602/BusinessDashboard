import sys, shutil, py_compile
P = "main.py"; B = "main.py.bak79"
src = open(P).read()
if "V79_STOPFIX" in src:
    print("v79 already applied"); sys.exit(0)
shutil.copy(P, B)
E = [
('        if low in ("stop goal", "cancel goal"):\n            self._v75_stop = True\n',
 '        if low in ("stop goal", "cancel goal") or (getattr(self, "_v78_on", False) and low in ("stop", "stop task", "stop auto running", "stop running", "cancel")):  # V79_STOPFIX\n            self._v75_stop = True\n            self._v78_on = False\n'),
('        self._v78_stat("Tapping Send in Claude")\n        for lab in ("Send message", "Send"):\n',
 '        try:  # V79_SHARE\n            from jnius import autoclass as _ac79\n            _scr = str(_ac79("org.rambo.acc.RamboAccService").screenText() or "")\n            if "Send to" in _scr:\n                self._v78_stat("Choosing New chat in Claude")\n                self.acc_run("acc tap New chat")\n                time.sleep(3)\n        except Exception:\n            pass\n        self._v78_stat("Tapping Send in Claude")\n        for lab in ("Send message", "Send"):\n'),
]
try:
    for old, new in E:
        n = src.count(old)
        if n != 1:
            raise Exception("anchor found %d times: %r" % (n, old[:50]))
        src = src.replace(old, new)
    open(P, "w").write(src)
    py_compile.compile(P, doraise=True)
    print("v79 applied OK")
except Exception as e:
    shutil.copy(B, P)
    print("FAILED, restored backup:", e)
