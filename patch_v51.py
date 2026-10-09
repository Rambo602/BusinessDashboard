# patch_v51: bigger buttons (raw pixels -> dp). Backup: main.py.bak51. Undo: cp main.py.bak51 main.py
import os, sys, shutil, py_compile
F = "main.py"
if not os.path.exists(F):
    sys.exit("STOPPED: run this inside ~/BusinessDashboard")
src = open(F, encoding="utf-8").read()
if "_dp(" in src:
    sys.exit("Already patched (v51).")
shutil.copy(F, F + ".bak51")
notes = []

def swap(s, old, new, label, must):
    n = s.count(old)
    if n != 1:
        if must:
            raise Exception("anchor " + label + " count=" + str(n))
        notes.append("skipped " + label + " (" + str(n) + ")")
        return s
    return s.replace(old, new, 1)

REQ = [
 ("def mk_input(hint, multiline=False, height=45, **kw):",
  "from kivy.metrics import dp as _dp\n\n\ndef mk_input(hint, multiline=False, height=45, **kw):"),
 ("bar = BoxLayout(size_hint_y=None, height=54, spacing=6)",
  "bar = BoxLayout(size_hint_y=None, height=_dp(56), spacing=6)"),
 ("pill = BoxLayout(size_hint_y=None, height=58, spacing=4,",
  "pill = BoxLayout(size_hint_y=None, height=_dp(60), spacing=4,"),
 ('width=46, font_size="26sp"', 'width=_dp(54), font_size="26sp"'),
 ('width=62, font_size="14sp"', 'width=_dp(68), font_size="14sp"'),
 ('width=68, font_size="14sp"', 'width=_dp(76), font_size="14sp"'),
]
OPT = [
 ("size_hint_y=None, height=height, **style_in(kw))", "size_hint_y=None, height=_dp(height), **style_in(kw))"),
 ("top = BoxLayout(size_hint_y=None, height=44, spacing=6)", "top = BoxLayout(size_hint_y=None, height=_dp(46), spacing=6)"),
 ("self.chips_row = BoxLayout(size_hint_y=None, height=40, spacing=6)", "self.chips_row = BoxLayout(size_hint_y=None, height=_dp(42), spacing=6)"),
 ("height=26, shorten=True", "height=_dp(24), shorten=True"),
 ("b = NeonButton(glow=col, text=t, size_hint_y=None, height=h)", "b = NeonButton(glow=col, text=t, size_hint_y=None, height=_dp(h))"),
 ("r = BoxLayout(size_hint_y=None, height=48, spacing=6)", "r = BoxLayout(size_hint_y=None, height=_dp(50), spacing=6)"),
 ("row = BoxLayout(size_hint_y=None, height=46, spacing=6)", "row = BoxLayout(size_hint_y=None, height=_dp(50), spacing=6)"),
 ("height=4 * 56 + 3 * 8", "height=_dp(4 * 56 + 3 * 8)"),
 ("r = BoxLayout(size_hint_y=None, height=56, spacing=5)", "r = BoxLayout(size_hint_y=None, height=_dp(56), spacing=5)"),
 ('width=52, font_size="20sp"', 'width=_dp(56), font_size="20sp"'),
]
try:
    s = src
    for i, (a, b) in enumerate(REQ):
        s = swap(s, a, b, "req%d" % i, True)
    for i, (a, b) in enumerate(OPT):
        s = swap(s, a, b, "opt%d" % i, False)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak51", F)
    sys.exit("STOPPED and rolled back: " + str(e))
for n in notes:
    print(n)
print("PATCHED v51 OK: buttons and input are density-scaled")
