import sys, shutil, py_compile
F = "main.py"
s = open(F, encoding="utf-8").read()
if "V75_HOLDCOPY" in s:
    sys.exit("Already patched (v75).")
shutil.copy(F, F + ".bak75")
H = r'''    def _v75_install(self):  # V75_HOLDCOPY
        if getattr(self, "_v75_done", False):
            return
        self._v75_done = True
        self._v75_ev = None
        self._v75_pos = (0, 0)
        self._v75_open = False
        try:
            from kivy.core.window import Window
            Window.bind(on_touch_down=self._v75_down, on_touch_up=self._v75_up, on_touch_move=self._v75_move)
        except Exception as e:
            self.err("v75 install", e)

    def _v75_cancel(self):
        try:
            if self._v75_ev is not None:
                self._v75_ev.cancel()
        except Exception:
            pass
        self._v75_ev = None

    def _v75_down(self, win, touch):
        try:
            self._v75_cancel()
            x, y = touch.x, touch.y
            self._v75_pos = (x, y)
            self._v75_ev = Clock.schedule_once(lambda dt: self._v75_fire(x, y), 0.7)
        except Exception:
            pass
        return False

    def _v75_move(self, win, touch):
        try:
            if abs(touch.x - self._v75_pos[0]) > 25 or abs(touch.y - self._v75_pos[1]) > 25:
                self._v75_cancel()
        except Exception:
            pass
        return False

    def _v75_up(self, win, touch):
        self._v75_cancel()
        return False

    def _v75_find(self, w, x, y):
        from kivy.uix.label import Label
        from kivy.uix.behaviors import ButtonBehavior
        try:
            if getattr(w, "opacity", 1) == 0:
                return None
            for c in list(w.children):
                r = self._v75_find(c, x, y)
                if r is not None:
                    return r
            if isinstance(w, Label) and not isinstance(w, ButtonBehavior) and (w.text or "").strip():
                x0, y0 = w.to_window(w.x, w.y)
                x1, y1 = w.to_window(w.right, w.top)
                if min(x0, x1) <= x <= max(x0, x1) and min(y0, y1) <= y <= max(y0, y1):
                    return w
        except Exception:
            pass
        return None

    def _v75_fire(self, x, y):
        self._v75_ev = None
        if self._v75_open:
            return
        try:
            from kivy.core.window import Window
            for top in list(Window.children):
                w = self._v75_find(top, x, y)
                if w is not None:
                    t = re.sub(r"\[/?[a-z]+(=[^\]]*)?\]", "", w.text or "")
                    self._v75_popup(t)
                    return
        except Exception as e:
            self.err("v75 fire", e)

    def _v75_popup(self, text):
        from kivy.uix.modalview import ModalView
        from kivy.uix.textinput import TextInput
        mv = ModalView(size_hint=(0.96, 0.8))
        box = BoxLayout(orientation="vertical", spacing=6, padding=8)
        ti = TextInput(text=text, readonly=True, font_size="16sp",
                       background_color=(0.04, 0.05, 0.12, 1), foreground_color=(1, 1, 1, 1))
        box.add_widget(ti)
        def cp(*a):
            try:
                from kivy.core.clipboard import Clipboard
                Clipboard.copy(text)
                self.flash("Copied")
            except Exception as e:
                self.err("v75 copy", e)
        box.add_widget(self._v68_row([("COPY ALL", cp, GREEN), ("CLOSE", lambda *a: mv.dismiss(), AMBER)]))
        mv.add_widget(box)
        mv.bind(on_dismiss=lambda *a: setattr(self, "_v75_open", False))
        self._v75_open = True
        mv.open()

    def _v75_say(self, m):
        Clock.schedule_once(lambda dt: self.reply(m), 0)
        self._v72_status(m.replace("\n", " ")[:55])

    def _v75_goal(self, goal):
        self._v75_stop = False
        self._v75_ok = False
        self.reply("Goal started: " + goal[:200] + "\nType stop goal to cancel.")
        threading.Thread(target=self._v75_thread, args=(goal,), daemon=True).start()

    def _v75_plan(self, key, prompt):
        sysm = ("You are the planner for RAMBO AI, an Android assistant. The user gives a goal. Each turn reply with ONLY JSON: "
                "{\"say\": \"short status for the user\", \"action\": \"termux or claude or done\", \"arg\": \"...\"}. "
                "termux: arg is ONE shell command for Termux (Linux, no root, use pkg not apt). Read-only commands run at once, others need the user's approval. "
                "claude: arg is a question or task for the Claude app. It is slow, so use it only for hard research or when stuck. "
                "done: arg is the final answer for the user. Never use rm -rf, dd or mkfs. Use the step results shown to decide the next step. Use done as soon as the goal is met.")
        body = json.dumps({"systemInstruction": {"parts": [{"text": sysm}]},
                           "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                           "generationConfig": {"temperature": 0.3}}).encode()
        code, raw = gemini_try(key, body)
        if code != 200:
            return None
        try:
            t = json.loads(raw)["candidates"][0]["content"]["parts"][0]["text"]
            t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.M).strip()
            m = re.search(r"\{.*\}", t, re.S)
            return json.loads(m.group(0)) if m else None
        except Exception:
            return None

    def _v75_term(self, cmd):
        if self.V72_BAD.search(cmd):
            return "BLOCKED: destructive command"
        if self._auto_risky(cmd) or not self._v72_is_safe(cmd):
            ev = threading.Event()
            self._v75_ev_ok = ev
            self._v75_ok = False
            self._v75_say("Needs your OK: " + cmd[:200] + "\nType approve within 2 minutes, or stop goal.")
            ev.wait(120)
            if not self._v75_ok:
                return "NOT APPROVED (no approval, so it was not run)"
        self._v75_say("Running in Termux: " + cmd[:100])
        return self._v72_run_termux(cmd)

    def _v75_front(self):
        try:
            from jnius import autoclass
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            Intent = autoclass("android.content.Intent")
            li = act.getPackageManager().getLaunchIntentForPackage(act.getPackageName())
            li.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
            act.startActivity(li)
        except Exception as e:
            self.err("v75 front", e)

    def _v75_claude(self, q):
        self._v75_say("Asking Claude: " + q[:120])
        Clock.schedule_once(lambda dt: self.rb_send("claude", q), 0)
        time.sleep(8)
        for lab in ("Send message", "Send"):
            short, _f = self.acc_run("acc tap " + lab)
            if short.startswith("Tapped"):
                break
        S = None
        try:
            from jnius import autoclass
            S = autoclass("org.rambo.acc.RamboAccService")
        except Exception:
            pass
        prev, reply, t0 = "", "", time.time()
        while not self._v75_stop and time.time() - t0 < 150:
            time.sleep(5)
            cur = ""
            try:
                if S is not None and str(S.currentPackage() or "") == "com.anthropic.claude":
                    cur = str(S.screenText() or "")
            except Exception:
                cur = ""
            if cur and cur == prev and len(cur) > len(q) + 80:
                reply = cur
                break
            prev = cur
        self._rb_wait = None
        self._v75_front()
        if not reply:
            return "Claude did not reply in time, or Send was not found."
        k = reply.rfind(q[-40:])
        if k >= 0:
            reply = reply[k + len(q[-40:]):]
        return reply.strip()[:1500]

    def _v75_thread(self, goal):
        self.ka(True)
        try:
            try:
                key = open(self.key_path).read().strip()
            except Exception:
                key = ""
            if not key:
                self._v75_say("I need a Gemini key first. Type: setkey YOUR_KEY")
                return
            hist = []
            for n in range(1, 11):
                if self._v75_stop:
                    self._v75_say("Goal stopped.")
                    return
                prompt = "GOAL: " + goal + "\n"
                if hist:
                    prompt += "STEPS SO FAR:\n" + "\n".join(hist[-8:]) + "\n"
                prompt += "Now: " + datetime.now().strftime("%A %B %d %Y %I:%M %p") + ". Give the next step as JSON."
                d = self._v75_plan(key, prompt)
                if d is None:
                    self._v75_say("The planner failed (Gemini and Groq both). Stopping.")
                    return
                act = str(d.get("action", "")).lower().strip()
                arg = str(d.get("arg", "")).strip()
                self._v75_say("Step %d: %s" % (n, (str(d.get("say", "")) or act)[:160]))
                if act == "done":
                    self._v75_say("DONE: " + arg[:1500])
                    return
                if act == "termux" and arg:
                    out = self._v75_term(arg)
                elif act == "claude" and arg:
                    out = self._v75_claude(arg)
                else:
                    out = "Unknown or empty action"
                hist.append("%d. %s %s -> %s" % (n, act, arg[:300], out[:900]))
            self._v75_say("Stopped after 10 steps without finishing.")
        except Exception as e:
            self.err("v75 goal", e)
            self._v75_say("Goal stopped by an error: " + str(e)[:120])
        finally:
            self.ka(False)

'''
A1 = "    def flash(self, msg):\n"
N1 = A1 + "        try:\n            self._v75_install()\n        except Exception:\n            pass\n"
A2 = "    def _v72_approve(self):\n"
N2 = A2 + ("        _ev = getattr(self, \"_v75_ev_ok\", None)\n"
           "        if _ev is not None and not _ev.is_set():\n"
           "            self._v75_ok = True\n"
           "            _ev.set()\n"
           "            self.reply(\"Approved.\")\n"
           "            return\n")
A3 = '        if low in ("save", "save this", "save to memory"):  # ASK_FIRST_V63\n'
N3 = ('        try:\n'
      '            self._v75_install()\n'
      '        except Exception:\n'
      '            pass\n'
      '        if low in ("stop goal", "cancel goal"):\n'
      '            self._v75_stop = True\n'
      '            _ev = getattr(self, "_v75_ev_ok", None)\n'
      '            if _ev is not None:\n'
      '                _ev.set()\n'
      '            self.reply("Stopping the goal.")\n'
      '            return\n'
      '        if low.startswith("goal ") or low.startswith("goal:"):\n'
      '            self._v75_goal(re.sub(r"^goal\\s*:?\\s*", "", text, flags=re.I))\n'
      '            return\n') + A3
A4 = "    def _v72_newproj(self, *a):\n"
try:
    for a in (A1, A2, A3, A4):
        if s.count(a) != 1:
            raise Exception("anchor count %d for %r" % (s.count(a), a.strip()[:50]))
    s = s.replace(A1, N1, 1).replace(A2, N2, 1).replace(A3, N3, 1).replace(A4, H + A4, 1)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak75", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v75 OK")
