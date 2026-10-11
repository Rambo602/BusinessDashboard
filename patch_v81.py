import sys, shutil, py_compile
P = "main.py"; B = "main.py.bak81"
src = open(P).read()
if "V81_CLS" in src:
    print("v81 already applied"); sys.exit(0)
shutil.copy(P, B)
E = [
('            S = autoclass("org.rambo.acc.RamboAccService")\n        except Exception as e:\n            return ("Accessibility code is not in this build.", None)\n',
 '            S = getattr(self, "_v81_S", None) or autoclass("org.rambo.acc.RamboAccService")  # V81_CLS\n            self._v81_S = S\n        except Exception as e:\n            return ("Accessibility code is not in this build.", None)\n'),
('        self._v75_stop = False\n        self._v75_ok = False\n        self.reply("Goal started: "',
 '        try:  # V81_CACHE\n            from jnius import autoclass as _ac81\n            self._v81_S = _ac81("org.rambo.acc.RamboAccService")\n        except Exception:\n            pass\n        self._v75_stop = False\n        self._v75_ok = False\n        self.reply("Goal started: "'),
('_S80 = _ac80("org.rambo.acc.RamboAccService")',
 '_S80 = getattr(self, "_v81_S", None) or _ac80("org.rambo.acc.RamboAccService")'),
('            S = autoclass("org.rambo.acc.RamboAccService")\n        except Exception:\n            pass\n        prev, reply, t0 = "", "", time.time()',
 '            S = getattr(self, "_v81_S", None) or autoclass("org.rambo.acc.RamboAccService")\n        except Exception:\n            pass\n        prev, reply, t0 = "", "", time.time()'),
]
try:
    for old, new in E:
        n = src.count(old)
        if n != 1:
            raise Exception("anchor found %d times: %r" % (n, old[:60]))
        src = src.replace(old, new)
    open(P, "w").write(src)
    py_compile.compile(P, doraise=True)
    print("v81 applied OK")
except Exception as e:
    shutil.copy(B, P)
    print("FAILED, restored backup:", e)
