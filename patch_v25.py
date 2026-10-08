import shutil, sys
P = "main.py"
s = open(P, encoding="utf-8").read()

old1 = '''        sv, c = self._scroll()
        self._head(c, "NEW PROJECT", MAGENTA)
'''
new1 = '''        sv, c = self._scroll()
        self.proj_sv = sv
        self._head(c, "NEW PROJECT", MAGENTA)
'''

old2 = '''        self.proj_note = mk_input("Add a note, or answer its question", multiline=True, height=90)
        c.add_widget(self.proj_note)
        self._btn(c, "SPEAK NOTE / ANSWER", self.speak_note, GREEN)
        self._btn(c, "ADD NOTE / ANSWER", self.add_note, CYAN)
        self._btn(c, "MARK DONE", self.mark_done, MAGENTA)

        self._head(c, "PROJECT LOG", AMBER)
        self.proj_log = autosize(Label(text="", color=TXT))
        c.add_widget(self.proj_log)
'''
new2 = '''
        self._head(c, "PROJECT LOG", AMBER)
        self.proj_log = autosize(Label(text="", color=TXT))
        c.add_widget(self.proj_log)
        self.proj_note = mk_input("Add a note, or answer its question", multiline=True, height=90)
        c.add_widget(self.proj_note)
        self._btn(c, "SPEAK NOTE / ANSWER", self.speak_note, GREEN)
        self._btn(c, "ADD NOTE / ANSWER", self.add_note, CYAN)
        self._btn(c, "MARK DONE", self.mark_done, MAGENTA)
'''

old3 = '''            self.proj_log.text = "\\n\\n".join(lines) if lines else "No log yet."
'''
new3 = '''            newlog = "\\n\\n".join(lines) if lines else "No log yet."
            changed = newlog != self.proj_log.text
            self.proj_log.text = newlog
            if changed:
                Clock.schedule_once(lambda dt: setattr(self.proj_sv, "scroll_y", 0), 0.4)
'''

for name, o in (("1", old1), ("2", old2), ("3", old3)):
    if s.count(o) != 1:
        print("ABORT: block " + name + " not found exactly once")
        sys.exit(1)

shutil.copy(P, P + ".bak25")
s = s.replace(old1, new1).replace(old2, new2).replace(old3, new3)
open(P, "w", encoding="utf-8").write(s)
print("PATCH_V25_OK")
