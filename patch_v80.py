import sys, shutil, py_compile
P = "main.py"; B = "main.py.bak80"
src = open(P).read()
if "V80_SHARE" in src:
    print("v80 already applied"); sys.exit(0)
shutil.copy(P, B)
OLD1 = '''        try:  # V79_SHARE
            from jnius import autoclass as _ac79
            _scr = str(_ac79("org.rambo.acc.RamboAccService").screenText() or "")
            if "Send to" in _scr:
                self._v78_stat("Choosing New chat in Claude")
                self.acc_run("acc tap New chat")
                time.sleep(3)
        except Exception:
            pass
'''
NEW1 = '''        try:  # V80_SHARE
            from jnius import autoclass as _ac80
            _S80 = _ac80("org.rambo.acc.RamboAccService")
            _pk = str(_S80.currentPackage() or "")
            _scr = str(_S80.screenText() or "")
            self._v75_say("DEBUG screen: pkg=%s text=%s" % (_pk, _scr[:150].replace("\\n", " | ")))
            if _pk == "com.anthropic.claude":
                if "Send to" in _scr:
                    self._v78_stat("Choosing New chat in Claude")
                    _s, _f = self.acc_run("acc tap New chat")
                    if not str(_s).startswith("Tapped"):
                        self.acc_run("acc tapxy 540 393")
                    time.sleep(3)
                elif not _scr.strip():
                    self._v78_stat("Screen unreadable, tapping New chat spot")
                    self.acc_run("acc tapxy 540 393")
                    time.sleep(3)
        except Exception as e:
            self._v75_say("DEBUG share error: " + str(e)[:100])
'''
OLD2 = 'return "Claude did not reply in time, or Send was not found."'
NEW2 = 'return "Claude did not reply (it may be stuck). Do NOT ask Claude again. Use done and tell the user Claude did not answer."  # V80_NOREASK'
try:
    for old, new in ((OLD1, NEW1), (OLD2, NEW2)):
        n = src.count(old)
        if n != 1:
            raise Exception("anchor found %d times: %r" % (n, old[:50]))
        src = src.replace(old, new)
    open(P, "w").write(src)
    py_compile.compile(P, doraise=True)
    print("v80 applied OK")
except Exception as e:
    shutil.copy(B, P)
    print("FAILED, restored backup:", e)
