import os, sys, shutil, py_compile
F = "main.py"
src = open(F, encoding="utf-8").read()
if "def rb_send" in src:
    sys.exit("Already patched (v58).")
if not os.path.exists("rambo_profile.py"):
    sys.exit("STOPPED: rambo_profile.py is missing")
shutil.copy(F, F + ".bak58")
notes = []

def swap(s, old, new, label, must):
    n = s.count(old)
    if n != 1:
        if must:
            raise Exception("anchor " + label + " count=" + str(n))
        notes.append("skipped " + label + " (" + str(n) + ")")
        return s
    return s.replace(old, new, 1)

def drop(s, old):
    n = s.count(old)
    if n == 1:
        return s.replace(old, "", 1)
    if n > 1:
        notes.append("skipped drop '" + old[:30] + "' (" + str(n) + ")")
    return s

HELP = '''from kivy.metrics import dp as _dp

try:
    import rambo_profile as RP
except Exception:
    RP = None


def _rp_profile():
    try:
        return RP.PROFILE
    except Exception:
        return "You are RAMBO AI, a smart, friendly assistant on the user's Android phone. "


def _rp_extra(t):
    try:
        e = RP.extra(t)
        return (" " + e) if e else ""
    except Exception:
        return ""
'''

METHODS = r'''    RB_APPS = {"claude": ("com.anthropic.claude", "Claude"),
               "chatgpt": ("com.openai.chatgpt", "ChatGPT"),
               "grok": ("ai.x.grok", "Grok"),
               "gemini": ("com.google.android.apps.bard", "Gemini")}

    def rb_send(self, key, text, pid=None):
        import time as _t
        pkg, label = self.RB_APPS[key]
        try:
            brief = RP.CLAUDE_BRIEF
        except Exception:
            brief = ""
        out = (brief + text).strip()
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(out)
        except Exception:
            pass
        self._rb_wait = {"label": label, "sent": out, "t": _t.time(), "pid": pid}
        try:
            Clock.unschedule(self._rb_poll)
        except Exception:
            pass
        Clock.schedule_interval(self._rb_poll, 1.5)
        tail = " Tap copy on its answer, then come back here and I will grab it."
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            JString = autoclass("java.lang.String")
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            i = Intent()
            i.setAction(Intent.ACTION_SEND)
            i.setType("text/plain")
            i.setPackage(pkg)
            i.putExtra(Intent.EXTRA_TEXT, JString(out[:90000]))
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            act.startActivity(i)
            return "Sent to " + label + "." + tail
        except Exception as e:
            self.err("send " + key, e)
        try:
            from jnius import autoclass
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            li = act.getPackageManager().getLaunchIntentForPackage(pkg)
            if li is None:
                self._rb_wait = None
                return label + " is not installed. Text copied."
            act.startActivity(li)
            return "Opened " + label + ". Paste the text in." + tail
        except Exception as e:
            self.err("open " + key, e)
            self._rb_wait = None
            return "Could not open " + label + ". Text copied: paste it there."

    def _rb_poll(self, dt):
        import time as _t
        w = getattr(self, "_rb_wait", None)
        if not w or _t.time() - w["t"] > 1800:
            self._rb_wait = None
            return False
        try:
            from kivy.core.clipboard import Clipboard
            c = (Clipboard.paste() or "").strip()
        except Exception:
            return True
        if len(c) < 20 or c[:40] == w["sent"][:40]:
            return True
        self._rb_wait = None
        self._rb_last = c
        if w.get("pid") is not None:
            try:
                self.db.add_plog(w["pid"], "pal", w["label"] + " replied: " + c[:3000])
                self.update_proj_view()
            except Exception as e:
                self.err("rb log", e)
            self.flash(w["label"] + " reply added to the project")
        else:
            self.reply(w["label"] + " replied:\n" + c[:3000])
        return False

    def _rb_cmd(self, text):
        m = re.match(r"^(?:ask|tell|send(?: this)? to|to)\s+(claude|chat\s?gpt|grok|gemini)\s*[:,]?\s*(.*)$",
                     text.strip(), re.I | re.S)
        if not m:
            return None
        key = m.group(1).lower().replace(" ", "")
        msg = m.group(2).strip()
        if not msg:
            last = [t for r, t in self.hist if r == "model"]
            msg = last[-1] if last else ""
        if not msg:
            return "Type: ask claude <your question>"
        return self.rb_send(key, msg)

    def proj_to_app(self, key):
        title, text = self._proj_export()
        if not text:
            return
        self.flash(self.rb_send(key, title + "\n\n" + text, self.cur_proj))

'''

BTN2 = ('        self._btn(c, "SEND TO CLAUDE (brings the reply back)", lambda *a: self.proj_to_app("claude"), CYAN, 56)\n'
        '        self._btn(c, "SEND TO CHATGPT", lambda *a: self.proj_to_app("chatgpt"), GREEN)\n')
ROUTE = ('            rc = self._rb_cmd(text)\n'
         '            if rc:\n'
         '                self.reply(rc)\n'
         '                return\n')
try:
    s = src
    s = swap(s, "from kivy.metrics import dp as _dp\n", HELP, "helpers", True)
    s = swap(s, "    def proj_copy(self, *a):\n", METHODS + "    def proj_copy(self, *a):\n", "methods", True)
    s = swap(s, "            ac = self._chat_app_cmd(text)\n", "            ac = None\n", "oldcmd", False)
    done = False
    for a in ('            qt = self._quick_time(text)\n', '            qc = self._quick_calc(text)\n'):
        if s.count(a) == 1:
            s = s.replace(a, ROUTE + a, 1)
            done = True
            break
    if not done:
        raise Exception("chat anchor not found")
    if "SEND TO CLAUDE" not in s:
        base = '        self._btn(c, "SHARE RESULT (Claude, ChatGPT, Grok, Gemini...)", self.proj_share2, CYAN, 56)\n'
        for a in (base, base.replace("proj_share2", "proj_share")):
            if s.count(a) == 1:
                s = s.replace(a, a + BTN2, 1)
                break
        else:
            notes.append("skipped project buttons")
    s = swap(s, '"You are RAMBO AI, a smart, friendly assistant on the user\'s Android phone. "',
             "_rp_profile() +", "profile", False)
    s = drop(s, "Answer in one to three short sentences. ")
    s = drop(s, "Answer clearly and accurately in two to five practical sentences. ")
    s = drop(s, "For safety topics put the warning first. ")
    s = swap(s, '            sysm = {"role": "system", "content": sp}\n',
             '            sp += _rp_extra(text)\n            sysm = {"role": "system", "content": sp}\n', "extra", False)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak58", F)
    sys.exit("STOPPED and rolled back: " + str(e))
for n in notes:
    print(n)
print("PATCHED v58 OK")
