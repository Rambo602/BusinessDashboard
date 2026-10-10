import sys, shutil, py_compile
F = "main.py"
s = open(F, encoding="utf-8").read()
if "SAVE_REAL_V67" in s:
    sys.exit("Already patched (v67).")
shutil.copy(F, F + ".bak67")
A = ('            last = [t for r, t in self.hist if r == "model"]\n'
     '            txt = last[-1] if last else ""\n')
N = ('            last = [t for r, t in self.hist if r == "model"]  # SAVE_REAL_V67\n'
     '            txt = last[-1] if last else ""\n'
     '            if txt.startswith(("Sent to", "SAVED", "SAVE")):\n'
     '                txt = ""\n'
     '            elif " replied:\\n" in txt[:40]:\n'
     '                txt = txt.split("\\n", 1)[1]\n')
try:
    if s.count(A) != 1:
        raise Exception("anchor %d" % s.count(A))
    s = s.replace(A, N, 1)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak67", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v67 OK")
