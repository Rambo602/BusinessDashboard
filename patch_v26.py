import shutil, sys
P = "main.py"
s = open(P, encoding="utf-8").read()

old1 = '''        self.update_proj_view()
        if p and p[3] == "waiting":
            self.auto_start()
'''
new1 = '''        self.update_proj_view()
        if p and p[3] != "done":
            self.auto_start()
'''

old2 = '''        self._btn(c, "SPEAK NOTE / ANSWER", self.speak_note, GREEN)
        self._btn(c, "ADD NOTE / ANSWER", self.add_note, CYAN)
'''
new2 = '''        self._btn(c, "SEND ANSWER", self.add_note, CYAN, 56)
        self._btn(c, "SPEAK ANSWER (MIC)", self.speak_note, GREEN)
'''

for name, o in (("1", old1), ("2", old2)):
    if s.count(o) != 1:
        print("ABORT: block " + name + " not found exactly once")
        sys.exit(1)

shutil.copy(P, P + ".bak26")
s = s.replace(old1, new1).replace(old2, new2)
open(P, "w", encoding="utf-8").write(s)
print("PATCH_V26_OK")
