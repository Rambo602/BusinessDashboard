import sys, shutil, py_compile, re
F = "main.py"
src = open(F, encoding="utf-8").read()
if "ASK_FIRST_V63" in src:
    sys.exit("Already patched (v63).")
shutil.copy(F, F + ".bak63")
try:
    s = src
    # 1) ask claude runs before the "ask " strip, plus typed save command
    A1 = '        force_ai = False\n        if low.startswith(("ask ", "do ")):\n'
    N1 = ('        if low in ("save", "save this", "save to memory"):  # ASK_FIRST_V63\n'
          '            self.save_last_mem()\n'
          '            return\n'
          '        try:\n'
          '            r_rb = self._rb_cmd(text)\n'
          '        except Exception as e:\n'
          '            self.err("ask first v63", e)\n'
          '            r_rb = "Could not open the app: " + str(e)[:150]\n'
          '        if r_rb is not None:\n'
          '            self.reply(r_rb)\n'
          '            return\n') + A1
    if s.count(A1) != 1:
        raise Exception("force_ai anchor count %d" % s.count(A1))
    s = s.replace(A1, N1, 1)
    # 2) save_last_mem method
    A2 = '    def new_chat(self):\n'
    N2 = ('    def save_last_mem(self, *a):\n'
          '        try:\n'
          '            last = [t for r, t in self.hist if r == "model"]\n'
          '            if not last:\n'
          '                self.flash("Nothing to save yet")\n'
          '                return\n'
          '            self.add_memory(last[-1][:6000])\n'
          '            self.flash("Saved to memory")\n'
          '        except Exception as e:\n'
          '            self.err("save mem", e)\n'
          '            self.flash("Save failed")\n\n') + A2
    if s.count(A2) != 1:
        raise Exception("new_chat anchor count %d" % s.count(A2))
    s = s.replace(A2, N2, 1)
    # 3) SAVE button beside COPY
    m = re.search(r'^( *)cpb = NeonButton\(glow=GREEN, text="COPY"[^\n]*\)\n', s, re.M)
    if not m or len(re.findall(r'cpb = NeonButton\(glow=GREEN, text="COPY"', s)) != 1:
        raise Exception("COPY button anchor not found")
    ind = m.group(1)
    N3 = (ind + 'svb = NeonButton(glow=AMBER, text="SAVE", size_hint_x=0.2, font_size="12sp")\n' +
          ind + 'svb.bind(on_release=lambda *a: self.save_last_mem())\n' +
          ind + 'Clock.schedule_once(lambda dt: cpb.parent.add_widget(svb) if cpb.parent else None, 0.5)\n')
    s = s[:m.end()] + N3 + s[m.end():]
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak63", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v63 OK")
