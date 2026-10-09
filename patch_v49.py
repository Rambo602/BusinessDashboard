# patch_v49: copy out of RAMBO AI. Double-tap any chat bubble to copy it; COPY button (top bar)
# copies the recent chat so you can paste it to Claude. Additive. Backup: main.py.bak49.
# Run inside ~/BusinessDashboard. Undo: cp main.py.bak49 main.py
import os, sys, shutil, py_compile

F = "main.py"
if not os.path.exists(F):
    sys.exit("STOPPED: main.py not found (run this inside ~/BusinessDashboard)")
src = open(F, encoding="utf-8").read()
if "def copy_chat" in src:
    sys.exit("Already patched (v49). Nothing to do.")
shutil.copy(F, F + ".bak49")


def swap(s, old, new, label):
    if s.count(old) != 1:
        raise Exception("anchor not unique or missing: " + label + " (%d)" % s.count(old))
    return s.replace(old, new, 1)


BUBBLE = '''
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and getattr(touch, "is_double_tap", False):
            try:
                from kivy.core.clipboard import Clipboard
                from kivy.app import App
                Clipboard.copy(self.text)
                App.get_running_app().flash("Copied this message")
            except Exception:
                pass
            return True
        return super().on_touch_down(touch)
'''

METHODS = '''    def copy_chat(self):
        try:
            from kivy.core.clipboard import Clipboard
            rows = self.db.recent_chat(40)
            out = []
            for role, text in rows:
                out.append(("You: " if role == "user" else "RAMBO AI: ") + str(text))
            if not out:
                self.flash("Nothing to copy yet")
                return
            Clipboard.copy("\\n\\n".join(out))
            self.flash("Copied the last %d messages. Paste them to Claude." % len(out))
        except Exception as e:
            self.err("copy chat", e)
            self.flash("Copy failed")

'''

try:
    s = src
    s = swap(s, "            self._rect.size = self.size\n\n\nfrom kivy.graphics import Line\n",
             "            self._rect.size = self.size\n" + BUBBLE + "\n\nfrom kivy.graphics import Line\n", "bubble")
    s = swap(s, "        top.add_widget(newb)\n",
             "        cpb = NeonButton(glow=GREEN, text=\"COPY\", size_hint_x=0.22, font_size=\"12sp\")\n"
             "        cpb.bind(on_press=lambda *a: self.copy_chat())\n"
             "        top.add_widget(cpb)\n        top.add_widget(newb)\n", "button")
    s = swap(s, "    def hide_chips(self):\n", METHODS + "    def hide_chips(self):\n", "methods")
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak49", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v49 OK: double-tap a message to copy it; COPY button copies the recent chat")
print("UNDO: cd ~/BusinessDashboard && cp main.py.bak49 main.py")
