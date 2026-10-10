import sys, shutil, py_compile
F = "main.py"
s = open(F, encoding="utf-8").read()
if "PROJ_LAYOUT_V65" in s:
    sys.exit("Already patched (v65).")
shutil.copy(F, F + ".bak65")
try:
    # 1) create buttons -> one row
    a = s.index('        self._btn(c, "SPEAK PROJECT (name + goal)"')
    b0 = '        self._btn(c, "CREATE AND AUTO RUN", self.create_run, GREEN)\n'
    b = s.index(b0) + len(b0)
    s = s[:a] + (
        '        self._row(c, [("SPEAK", self.speak_project, GREEN), ("CREATE", self.new_project, MAGENTA),\n'
        '                      ("CREATE+RUN", self.create_run, GREEN)])  # PROJ_LAYOUT_V65\n') + s[b:]
    # 2) answer / run / result buttons -> rows and folds
    a = s.index('        self._btn(c, "SEND ANSWER"')
    e0 = '        self._btn(c, "TIDY WITH GEMMA (clean summary)", self.proj_tidy, MAGENTA, 56)\n'
    b = s.index(e0) + len(e0)
    NEW = (
        '        self._row(c, [("SEND", self.add_note, CYAN), ("MIC", self.speak_note, GREEN)])\n'
        '        self._row(c, [("RUN", self.auto_start, GREEN), ("PAUSE", lambda *a: self.auto_stop("Paused."), AMBER),\n'
        '                      ("DONE", self.mark_done, MAGENTA)])\n'
        '        self._row(c, [("CLAUDE", lambda *a: self.proj_to_app("claude"), CYAN),\n'
        '                      ("SAVE MEM", self.proj_mem, AMBER)])\n'
        '        self._fold(c, "RESULT MENU", [\n'
        '            ("SHARE (any app)", self.proj_share2, CYAN),\n'
        '            ("SEND TO CHATGPT", lambda *a: self.proj_to_app("chatgpt"), GREEN),\n'
        '            ("SAVE PDF", self.proj_pdf, GREEN), ("SAVE TEXT", self.proj_txt, GREEN),\n'
        '            ("COPY RESULT", self.proj_copy, CYAN),\n'
        '            ("TIDY WITH GEMMA", self.proj_tidy, MAGENTA)], CYAN)\n'
        '        self._fold(c, "MORE", [("DELETE PROJECT (tap twice)", self.proj_delete, AMBER)], AMBER)\n')
    s = s[:a] + NEW + s[b:]
    # 3) helper methods
    A = "    def _proj_export(self):\n"
    if s.count(A) != 1:
        raise Exception("export anchor %d" % s.count(A))
    H = (
        '    def _row(self, parent, items):\n'
        '        r = BoxLayout(orientation="horizontal", spacing=6, size_hint_y=None, height=56)\n'
        '        for t, cb, g in items:\n'
        '            bt = NeonButton(glow=g, text=t, font_size="14sp")\n'
        '            bt.bind(on_release=cb)\n'
        '            r.add_widget(bt)\n'
        '        parent.add_widget(r)\n\n'
        '    def _fold(self, parent, label, items, glow):\n'
        '        n = len(items)\n'
        '        full = n * 56 + (n - 1) * 6\n'
        '        box = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None, height=0, opacity=0)\n'
        '        box.disabled = True\n'
        '        for t, cb, g in items:\n'
        '            bt = NeonButton(glow=g, text=t, size_hint_y=None, height=56, font_size="14sp")\n'
        '            bt.bind(on_release=cb)\n'
        '            box.add_widget(bt)\n'
        '        top = NeonButton(glow=glow, text=label + "  (tap to open)", size_hint_y=None, height=56, font_size="14sp")\n'
        '        def tog(*a):\n'
        '            o = box.height == 0\n'
        '            box.height = full if o else 0\n'
        '            box.opacity = 1 if o else 0\n'
        '            box.disabled = not o\n'
        '        top.bind(on_release=tog)\n'
        '        parent.add_widget(top)\n'
        '        parent.add_widget(box)\n\n')
    s = s.replace(A, H + A, 1)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak65", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v65 OK")
