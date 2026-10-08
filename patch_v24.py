import shutil
import sys

P = "main.py"
s = open(P, encoding="utf-8").read()


def rep(s, old, new):
    if s.count(old) != 1:
        raise ValueError("anchor not unique or missing: " + old[:60])
    return s.replace(old, new)


try:
    # 1. Controls: move AUTO RUN and PAUSE down next to the reply buttons
    s = rep(s, '        self._btn(c, "AUTO RUN", self.auto_start, GREEN, 56)\n'
               '        self._btn(c, "PAUSE", lambda *a: self.auto_stop("Paused."), AMBER)\n\n', "\n")
    s = rep(s, '        self._btn(c, "SPEAK ANSWER (MIC)", self.speak_note, GREEN)\n',
               '        self._btn(c, "SPEAK ANSWER (MIC)", self.speak_note, GREEN)\n'
               '        self._btn(c, "START AUTO RUN", self.auto_start, GREEN, 56)\n'
               '        self._btn(c, "PAUSE", lambda *a: self.auto_stop("Paused."), AMBER)\n')

    # 2. Retry on lost connection or temporary Gemini errors, instead of stopping
    s = rep(s, '        if err:\n'
               '            self.err("auto net", err)\n'
               '            self.auto_stop("No connection. Paused.")\n'
               '            return\n',
               '        if err or code in (408, 500, 502, 503, 504):\n'
               '            self.err("auto net", err or str(code))\n'
               '            self.auto_fail = getattr(self, "auto_fail", 0) + 1\n'
               '            wait = min(10 * (2 ** (self.auto_fail - 1)), 60)\n'
               '            self.auto_note = ("No connection, retrying in %d s (try %d)." % (wait, self.auto_fail)\n'
               '                              if err else "Gemini busy, retrying in %d s (try %d)." % (wait, self.auto_fail))\n'
               '            if self.auto_fail == 8:\n'
               '                self.notify("RAMBO AI: still offline", "Auto run keeps retrying. Open the app if you want to stop it.")\n'
               '            self.update_proj_view()\n'
               '            Clock.schedule_once(self.auto_next, wait)\n'
               '            return\n')
    s = rep(s, '        note, cmds, question, done = "", [], "", False\n',
               '        self.auto_fail = 0\n'
               '        self.auto_note = ""\n'
               '        note, cmds, question, done = "", [], "", False\n')

    # 3. Show the retry message in the project status line
    s = rep(s, '(\"  (auto run ON)\" if self.auto_on else \"\")',
               '(\"  (auto run ON)\" if self.auto_on else \"\") + '
               '((\"\\n\" + self.auto_note) if getattr(self, \"auto_note\", \"\") and self.auto_on else \"\")')

    # 4. A fresh start clears old retry state
    s = rep(s, '        self.auto_on = True\n        self.auto_steps = 0\n',
               '        self.auto_on = True\n        self.auto_steps = 0\n        self.auto_fail = 0\n        self.auto_note = ""\n')

    # 5. Name in the needs-you notification
    s = rep(s, 'self.notify("Pocket Pal needs you: " + pname, question)',
               'self.notify("RAMBO AI needs you: " + pname, question)')
except ValueError as e:
    print("ABORT: " + str(e))
    sys.exit(1)

shutil.copy(P, "main.py.bak24")
open(P, "w", encoding="utf-8").write(s)
print("PATCH_V24_OK")
