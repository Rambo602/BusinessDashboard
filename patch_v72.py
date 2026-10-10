import sys, shutil, py_compile
F = "main.py"
s = open(F, encoding="utf-8").read()
if "AUTO_V72" in s:
    sys.exit("Already patched (v72).")
shutil.copy(F, F + ".bak72")
H = r'''    V72_SAFE = re.compile(r"^(ls|cat|head|tail|grep|pwd|echo|wc|find|df|du|uname|date|whoami|ps|id|which|stat|file|sort|uniq|python -m py_compile|git (status|log|diff|branch)|pip list|pkg list-installed)\b")
    V72_BAD = re.compile(r"(\brm\s+-[a-z]*[rf]|\bdd\s+if|\bmkfs|\bshutdown|\breboot|:\(\)\s*\{|>\s*/dev/|\bchmod\s+-R\s+777|\b(curl|wget)\b[^|]*\|\s*(ba)?sh)", re.I)

    def _v72_is_safe(self, cmd):
        return bool(self.V72_SAFE.match(cmd)) and not re.search(r"[;&|<>`$]", cmd)

    def _v72_status(self, msg):
        try:
            Clock.schedule_once(lambda dt: self.flash(msg), 0)
        except Exception:
            pass
        try:
            from jnius import autoclass
            from android.runnable import run_on_ui_thread
            Toast = autoclass("android.widget.Toast")
            JS = autoclass("java.lang.String")
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            @run_on_ui_thread
            def _show():
                Toast.makeText(act, JS(str(msg)[:60]), 0).show()
            _show()
        except Exception:
            pass

    def _v72_run_termux(self, cmd, wait=60):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        box = {"out": None}
        class H(BaseHTTPRequestHandler):
            def do_POST(h):
                try:
                    n = int(h.headers.get("Content-Length") or 0)
                    box["out"] = h.rfile.read(n).decode("utf-8", "replace")
                except Exception:
                    box["out"] = ""
                h.send_response(200)
                h.end_headers()
            def log_message(h, *a):
                pass
        srv = HTTPServer(("127.0.0.1", 0), H)
        srv.timeout = 1
        port = srv.server_address[1]
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            i = Intent()
            i.setClassName("com.termux", "com.termux.app.RunCommandService")
            i.setAction("com.termux.RUN_COMMAND")
            i.putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/bash")
            i.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", ["-c", "( " + cmd + " ) 2>&1 | curl -s -m 20 --data-binary @- http://127.0.0.1:%d/o" % port])
            i.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home/BusinessDashboard")
            i.putExtra("com.termux.RUN_COMMAND_BACKGROUND", True)
            act.startService(i)
        except Exception as e:
            srv.server_close()
            return "TERMUX START FAILED: " + str(e)[:200]
        t0 = time.time()
        while box["out"] is None and time.time() - t0 < wait:
            srv.handle_request()
        srv.server_close()
        if box["out"] is None:
            return "TIMEOUT: no output. Check the Termux permission for RAMBO AI and allow-external-apps."
        return box["out"].strip()[-1500:] or "(no output)"

    def _v72_bg(self, cmd, pid=None):
        self.reply("Running in Termux: " + cmd[:200])
        def go():
            out = self._v72_run_termux(cmd)
            try:
                if pid is not None:
                    self.db.add_plog(pid, "run", "TERMUX " + cmd[:200] + " -> " + out)
            except Exception:
                pass
            Clock.schedule_once(lambda dt: self.reply("Termux output:\n" + out[:1500]), 0)
        threading.Thread(target=go, daemon=True).start()

    def _v72_chat_cmd(self, cmd):
        if self.V72_BAD.search(cmd):
            self.reply("Blocked: that looks destructive.")
        elif not self._v72_is_safe(cmd):
            self._v72_pending = (cmd, None)
            self.reply("Not on the read-only list. Type approve to run: " + cmd[:200])
        else:
            self._v72_bg(cmd)

    def _v72_approve(self):
        p = getattr(self, "_v72_pending", None)
        if not p:
            self.reply("Nothing is waiting for approval.")
            return
        self._v72_pending = None
        self._v72_bg(p[0], p[1])

    def _v72_special(self, pid, cm):
        low = cm.lower()
        if low.startswith("termux "):
            cmd = cm[7:].strip()
            if not cmd:
                return
            if self.V72_BAD.search(cmd):
                self.db.add_plog(pid, "ask", "Blocked a dangerous Termux command: " + cmd[:200])
                return
            if self._auto_risky(cm) or not self._v72_is_safe(cmd):
                self._v72_pending = (cmd, pid)
                self.db.add_plog(pid, "ask", "I want to run in Termux: " + cmd[:300] + ". Type approve in chat to run it, then tap RUN again.")
                self._auto_end(pid, "waiting", None)
                return
            out = self._v72_run_termux(cmd)
            self.db.add_plog(pid, "run", "TERMUX " + cmd[:200] + " -> " + out)
            return
        q = cm[7:].strip()
        Clock.schedule_once(lambda dt: self.rb_send("claude", q), 0)
        time.sleep(7)
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
        prev = ""
        reply = ""
        t0 = time.time()
        while self.auto_on and time.time() - t0 < 150:
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
        if reply:
            k = reply.rfind(q[-40:])
            if k >= 0:
                reply = reply[k + len(q[-40:]):]
            self.db.add_plog(pid, "run", "SCREEN Claude reply: " + reply.strip()[:2500])
        else:
            self.db.add_plog(pid, "run", "SCREEN Claude did not finish in time or Send was not found. Tap Send in Claude yourself, or answer in the note box.")

    def _v72_newproj(self, *a):
        from kivy.uix.modalview import ModalView
        self.proj_name = mk_input("Project name")
        self.proj_goal = mk_input("Goal: what should it build or do?", multiline=True, height=100)
        self.proj_name.size_hint_y = None
        self.proj_name.height = 60
        self.proj_goal.size_hint_y = None
        self.proj_goal.height = 120
        mv = ModalView(size_hint=(0.94, None), height=310, pos_hint={"center_x": 0.5, "top": 0.97})
        box = BoxLayout(orientation="vertical", spacing=8, padding=10)
        box.add_widget(self.proj_name)
        box.add_widget(self.proj_goal)
        def go(cb):
            def f(inst):
                mv.dismiss()
                cb(inst)
            return f
        box.add_widget(self._v68_row([("SPEAK", self.speak_project, GREEN),
                                      ("CREATE", go(self.new_project), MAGENTA),
                                      ("CREATE+RUN", go(self.create_run), GREEN)]))
        mv.add_widget(box)
        mv.open()

    def _auto_sys(self, p):
        s = self._v72_orig_sys(p)
        return s + (" EXTRA COMMANDS: termux <one shell command> runs it in Termux (Linux shell, no root, use pkg not apt). "
                    "Read-only commands run at once; others wait for the user to approve. The output appears in the log as TERMUX lines on your next turn. "
                    "claude <question or task> asks the Claude app and returns its reply as a SCREEN line. It is slow, so use it only for hard research or when stuck. "
                    "Never use rm -rf, dd or mkfs. Use one termux or claude command per turn.")

'''
try:
    A1 = "    def _auto_sys(self, p):\n"
    A2 = "            low0 = cm.strip().lower()\n"
    A3 = '        if low in ("save", "save this", "save to memory"):  # ASK_FIRST_V63\n'
    A4 = ("        top.bind(on_release=tog)\n"
          "        c.add_widget(top)\n")
    for a in (A1, A2, A3, A4):
        if s.count(a) != 1:
            raise Exception("anchor count %d for %r" % (s.count(a), a.strip()[:40]))
    s = s.replace(A1, H + "    def _v72_orig_sys(self, p):\n", 1)
    s = s.replace(A2, A2 +
        '            self._v72_status("AUTO: " + cm.strip()[:45])  # AUTO_V72\n'
        '            if low0.startswith(("termux ", "claude ")):\n'
        '                self._v72_special(pid, cm.strip())\n'
        '                return\n', 1)
    s = s.replace(A3,
        '        if low in ("approve", "approve it", "yes run it"):\n'
        '            self._v72_approve()\n'
        '            return\n'
        '        if low.startswith("termux "):\n'
        '            self._v72_chat_cmd(text[7:].strip())\n'
        '            return\n' + A3, 1)
    s = s.replace(A4, A4.replace("on_release=tog", "on_release=self._v72_newproj"), 1)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak72", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v72 OK")
sp = "buildozer.spec"
try:
    shutil.copy(sp, sp + ".bak72")
    t = open(sp).read().split("\n")
    found = False
    for n, ln in enumerate(t):
        if ln.startswith("android.permissions"):
            found = True
            if "RUN_COMMAND" not in ln:
                t[n] = ln.rstrip() + ",com.termux.permission.RUN_COMMAND"
    if found:
        open(sp, "w").write("\n".join(t))
        print("spec permission OK")
    else:
        print("WARNING: no android.permissions line in buildozer.spec, paste: grep -n permissions buildozer.spec")
except Exception as e:
    print("spec not changed:", e)
