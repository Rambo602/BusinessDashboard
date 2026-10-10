import sys, shutil, py_compile
F = "main.py"
s = open(F, encoding="utf-8").read()
if "PROJ_LAYOUT_V68" in s:
    sys.exit("Already patched (v68).")
shutil.copy(F, F + ".bak68")
try:
    a1 = s.index('        self._btn(c, "SPEAK PROJECT (name + goal)"')
    e1 = '        self._btn(c, "CREATE AND AUTO RUN", self.create_run, GREEN)\n'
    b1 = s.index(e1) + len(e1)
    a2 = s.index('        self._btn(c, "SEND ANSWER"')
    e2 = '        self._btn(c, "TIDY WITH GEMMA (clean summary)", self.proj_tidy, MAGENTA, 56)\n'
    b2 = s.index(e2) + len(e2)
    if not (a1 < b1 < a2 < b2):
        raise Exception("order")
    old1 = s[a1:b1]
    old2 = s[a2:b2]
    CALL2 = ('        try:  # PROJ_LAYOUT_V68\n'
             '            for _x in self._v68_ctl():\n'
             '                c.add_widget(_x)\n'
             '        except Exception as e:\n'
             '            self.err("v68 ctl", e)\n'
             '            self._v68_old_ctl(c)\n')
    CALL1 = ('        try:\n'
             '            for _x in self._v68_create():\n'
             '                c.add_widget(_x)\n'
             '        except Exception as e:\n'
             '            self.err("v68 create", e)\n'
             '            self._v68_old_create(c)\n')
    s = s[:a2] + CALL2 + s[b2:]
    s = s[:a1] + CALL1 + s[b1:]
    H = '''    def _v68_old_create(self, c):
''' + old1 + '''
    def _v68_old_ctl(self, c):
''' + old2 + '''
    def _v68_btn(self, t, cb, g):
        bt = NeonButton(glow=g, text=t, font_size="14sp")
        bt.bind(on_release=cb)
        return bt

    def _v68_row(self, items):
        r = BoxLayout(orientation="horizontal", spacing=6, size_hint_y=None, height=56)
        for t, cb, g in items:
            r.add_widget(self._v68_btn(t, cb, g))
        return r

    def _v68_fold(self, label, items, glow):
        n = len(items)
        full = n * 56 + (n - 1) * 6
        box = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None, height=0, opacity=0)
        box.disabled = True
        for t, cb, g in items:
            b = self._v68_btn(t, cb, g)
            b.size_hint_y = None
            b.height = 56
            box.add_widget(b)
        top = self._v68_btn(label + "  (tap to open)", None, glow)
        top.size_hint_y = None
        top.height = 56
        def tog(*a):
            o = box.height == 0
            box.height = full if o else 0
            box.opacity = 1 if o else 0
            box.disabled = not o
        top.bind(on_release=tog)
        return [top, box]

    def _v68_create(self):
        return [self._v68_row([("SPEAK", self.speak_project, GREEN),
                               ("CREATE", self.new_project, MAGENTA),
                               ("CREATE+RUN", self.create_run, GREEN)])]

    def _v68_ctl(self):
        out = [self._v68_row([("SEND", self.add_note, CYAN), ("MIC", self.speak_note, GREEN)]),
               self._v68_row([("RUN", self.auto_start, GREEN),
                              ("PAUSE", lambda *a: self.auto_stop("Paused."), AMBER),
                              ("DONE", self.mark_done, MAGENTA)]),
               self._v68_row([("CLAUDE", lambda *a: self.proj_to_app("claude"), CYAN),
                              ("SAVE MEM", self.proj_mem, AMBER)])]
        out += self._v68_fold("RESULT MENU", [
            ("SHARE (any app)", self.proj_share2, CYAN),
            ("SEND TO CHATGPT", lambda *a: self.proj_to_app("chatgpt"), GREEN),
            ("SAVE PDF", self.proj_pdf, GREEN), ("SAVE TEXT", self.proj_txt, GREEN),
            ("COPY RESULT", self.proj_copy, CYAN),
            ("TIDY WITH GEMMA", self.proj_tidy, MAGENTA)], CYAN)
        out += self._v68_fold("MORE", [("DELETE PROJECT (tap twice)", self.proj_delete, AMBER)], AMBER)
        return out

'''
    A = "    def _proj_export(self):\n"
    if s.count(A) != 1:
        raise Exception("export anchor %d" % s.count(A))
    s = s.replace(A, H + A, 1)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak68", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v68 OK")
