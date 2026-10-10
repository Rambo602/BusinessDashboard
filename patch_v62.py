import sys, shutil, py_compile
F = "main.py"
src = open(F, encoding="utf-8").read()
if "ASK_FIRST_V62" in src:
    sys.exit("Already patched (v62).")
if "def _rb_cmd" not in src:
    sys.exit("STOPPED: _rb_cmd missing")
shutil.copy(F, F + ".bak62")
ANCHOR = "    def local_route(self, text, low):\n"
NEW = (ANCHOR +
       "        try:  # ASK_FIRST_V62\n"
       "            r_first = self._rb_cmd(text)\n"
       "        except Exception as e:\n"
       "            self.err('ask first', e)\n"
       "            r_first = 'Could not open the app: ' + str(e)[:150]\n"
       "        if r_first is not None:\n"
       "            return r_first\n")
try:
    if src.count(ANCHOR) != 1:
        raise Exception("anchor count %d" % src.count(ANCHOR))
    open(F, "w", encoding="utf-8").write(src.replace(ANCHOR, NEW, 1))
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak62", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v62 OK")
