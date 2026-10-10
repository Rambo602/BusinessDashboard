import os, sys, shutil, py_compile
F = "main.py"
src = open(F, encoding="utf-8").read()
if "def _rb_needs_gemini" in src:
    sys.exit("Already patched (v59).")
shutil.copy(F, F + ".bak59")
notes = []

def swap(s, old, new, label, must):
    n = s.count(old)
    if n != 1:
        if must:
            raise Exception("anchor " + label + " count=" + str(n))
        notes.append("skipped " + label + " (" + str(n) + ")")
        return s
    return s.replace(old, new, 1)

METHOD = r'''    def _rb_needs_gemini(self, low):
        try:
            if not self.gem_ok():
                return False
        except Exception:
            return False
        try:
            if needs_live(low):
                return True
        except Exception:
            pass
        keys = ("python", "script", "debug", "write code", "write a program",
                "research", "regex", "javascript", "html", "sql")
        return any(k in low for k in keys)

'''
try:
    s = src
    s = swap(s, "    def ask_gemini(self, text):\n", METHOD + "    def ask_gemini(self, text):\n", "method", True)
    s = swap(s, 'hard = low.startswith("gemini") or len(text) > 1500',
             'hard = low.startswith("gemini") or len(text) > 1500 or self._rb_needs_gemini(low)', "route", True)
    s = swap(s, "            out = acc.strip()\n",
             "            out = acc.strip()\n"
             "            if out.upper().startswith(\"ESCALATE\") and self.gem_ok():\n"
             "                Clock.schedule_once(lambda dt: (self._stream_clear(), self._ask_cloud(text)), 0)\n"
             "                return\n", "escalate", False)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
    if os.path.exists("rambo_profile.py"):
        p = open("rambo_profile.py", encoding="utf-8").read()
        old = "do not guess: tell him to type: ask claude <question>. "
        if old in p:
            p = p.replace(old, "do not guess: reply with only the single word ESCALATE. ", 1)
            open("rambo_profile.py", "w", encoding="utf-8").write(p)
        elif "ESCALATE" not in p:
            notes.append("skipped profile edit (text not found)")
    else:
        notes.append("skipped profile edit (rambo_profile.py missing, run v58 first)")
except Exception as e:
    shutil.copy(F + ".bak59", F)
    sys.exit("STOPPED and rolled back: " + str(e))
for n in notes:
    print(n)
print("PATCHED v59 OK")
