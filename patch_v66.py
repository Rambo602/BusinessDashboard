import sys, shutil, py_compile
F = "main.py"
s = open(F, encoding="utf-8").read()
if "SAVE_VISIBLE_V66" in s:
    sys.exit("Already patched (v66).")
shutil.copy(F, F + ".bak66")
A = "    def save_last_mem(self, *a):\n"
B = "    def new_chat(self):\n"
NEW = (
'    def save_last_mem(self, *a):  # SAVE_VISIBLE_V66\n'
'        def say(m):\n'
'            try:\n'
'                self.add_msg(m, False)\n'
'            except Exception:\n'
'                pass\n'
'            try:\n'
'                self.flash(m)\n'
'            except Exception:\n'
'                pass\n'
'        try:\n'
'            last = [t for r, t in self.hist if r == "model"]\n'
'            txt = last[-1] if last else ""\n'
'            if not txt.strip():\n'
'                try:\n'
'                    from kivy.core.clipboard import Clipboard\n'
'                    txt = Clipboard.paste() or ""\n'
'                except Exception:\n'
'                    txt = ""\n'
'            txt = txt.strip()[:6000]\n'
'            if not txt:\n'
'                say("SAVE: nothing to save yet.")\n'
'                return\n'
'            self.db.add_memory(txt)\n'
'            n = len(self.db.memories(1000))\n'
'            say("SAVED to memory (%d characters). Memory now holds %d entries." % (len(txt), n))\n'
'        except Exception as e:\n'
'            self.err("save mem", e)\n'
'            say("SAVE FAILED: " + str(e)[:150])\n\n')
try:
    if s.count(A) != 1 or s.count(B) != 1:
        raise Exception("anchors %d/%d" % (s.count(A), s.count(B)))
    a = s.index(A)
    b = s.index(B)
    if b < a:
        raise Exception("order")
    s = s[:a] + NEW + s[b:]
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak66", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v66 OK")
