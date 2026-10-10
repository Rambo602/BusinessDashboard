import sys, shutil, py_compile
F = "main.py"
s = open(F, encoding="utf-8").read()
if "BIGBTN_V71" in s:
    sys.exit("Already patched (v71).")
shutil.copy(F, F + ".bak71")
A1 = '        top.height = 48\n'
N1 = ('        top.height = 72  # BIGBTN_V71\n'
      '        top.font_size = "18sp"\n')
A2 = ('        c.add_widget(self.proj_list)\n'
      '        self.proj_title = autosize(Label(text="None selected."')
N2 = ('        c.add_widget(self.proj_list)\n'
      '        self.proj_list.bind(children=lambda *a: Clock.schedule_once(self._v71_big, 0))\n'
      '        Clock.schedule_once(self._v71_big, 0.3)\n'
      '        self.proj_title = autosize(Label(text="None selected."')
A3 = '    def _v69_menu(self, *a):\n'
N3 = ('    def _v71_big(self, *a):\n'
      '        try:\n'
      '            for w in list(self.proj_list.children):\n'
      '                w.size_hint_y = None\n'
      '                w.height = 68\n'
      '                try:\n'
      '                    w.font_size = "18sp"\n'
      '                except Exception:\n'
      '                    pass\n'
      '        except Exception as e:\n'
      '            self.err("v71 big", e)\n\n') + A3
try:
    for a in (A1, A2, A3):
        if s.count(a) != 1:
            raise Exception("anchor count %d for %r" % (s.count(a), a[:40]))
    s = s.replace(A1, N1, 1).replace(A2, N2, 1).replace(A3, N3, 1)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak71", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v71 OK")
