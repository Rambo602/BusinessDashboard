import os, sys, shutil, py_compile
F = "main.py"
src = open(F, encoding="utf-8").read()
if "ESCALATE_CLAUDE" in src:
    sys.exit("Already patched (v61).")
if "def rb_send" not in src:
    sys.exit("STOPPED: v58 is missing, run v58 first")
shutil.copy(F, F + ".bak61")
NEW = ('            out = acc.strip()\n'
       '            if out.upper().startswith("ESCALATE"):  # ESCALATE_CLAUDE\n'
       '                if self.gem_ok():\n'
       '                    Clock.schedule_once(lambda dt: (self._stream_clear(), self._ask_cloud(text)), 0)\n'
       '                else:\n'
       '                    Clock.schedule_once(lambda dt: (self._stream_clear(), self.reply(self.rb_send("claude", text))), 0)\n'
       '                return\n')
OLD = ('            out = acc.strip()\n'
       '            if out.upper().startswith("ESCALATE") and self.gem_ok():\n'
       '                Clock.schedule_once(lambda dt: (self._stream_clear(), self._ask_cloud(text)), 0)\n'
       '                return\n')
BASE = '            out = acc.strip()\n'
try:
    s = src
    if s.count(OLD) == 1:
        s = s.replace(OLD, NEW, 1)
    elif s.count(BASE) == 1:
        s = s.replace(BASE, NEW, 1)
    else:
        raise Exception("anchor not found (%d)" % s.count(BASE))
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak61", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v61 OK")
