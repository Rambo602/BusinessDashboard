#!/usr/bin/env python3
# patch_v33.py - Gemma first, Gemini only when needed, background-safe auto run
# Run from ~/BusinessDashboard:  python patch_v33.py
# Backs up main.py and buildozer.spec first. Aborts if an anchor is missing.
import os, sys, re, shutil, py_compile

ROOT = os.getcwd()
MAIN = os.path.join(ROOT, "main.py")
SPEC = os.path.join(ROOT, "buildozer.spec")
MANI = os.path.join(ROOT, "manifest_service.xml")


def die(msg):
    print("STOPPED: " + msg)
    sys.exit(1)


for p in (MAIN, SPEC, MANI):
    if not os.path.exists(p):
        die("run this from ~/BusinessDashboard (missing " + os.path.basename(p) + ")")

main = open(MAIN).read()
spec = open(SPEC).read()
mani = open(MANI).read()

if "def gemma_chat" in main:
    die("patch already applied")

# ---------------- anchors (each must appear exactly once) ----------------
A_GEMMSG = "def gem_msg(raw):\n"

A_KEY = ('        if not os.path.exists(self.key_path):\n'
         '            self.proj_status.text = "Auto run needs a Gemini key. Save it in MORE, GEMINI KEY."\n'
         '            self.flash("Need a Gemini key first: MORE tab, GEMINI KEY.")\n'
         '            return\n')

A_START = "        Clock.schedule_once(self.auto_next, 0.5)\n"

A_AUTOCMD = "    def _auto_cmd(self, pid, cm):\n"

A_ONSTART = "    def on_start(self):\n        self.init_tts()\n"

A_HARD = ('            hard = len(text) > 220 or low.startswith("gemini") '
          'or any(w in low for w in words)\n')

A_COOL = ('        wait = int(self.cool_until - time.time())\n'
          '        if wait > 0:\n'
          '            self.reply("Gemini is resting after hitting its free limit. Try again in "\n'
          '                       + str(wait) + " seconds. Simple commands like open, search, "\n'
          '                       "timer and alarm still work.")\n'
          '            return\n')

A_GTHREAD = ('            code, raw = gemini_post(key, body)\n'
             '        except Exception as e:\n'
             '            err = str(e)\n'
             '        Clock.schedule_once(lambda dt: self.on_gemini(code, raw, err), 0)\n')

A_429 = ('        if code == 429:\n'
         '            self.cool_until = time.time() + 60\n'
         '            self.reply("Gemini\'s free limit was hit. I will rest for a minute. "\n'
         '                       "Simple commands still work.")\n'
         '            return\n')

A_OKREPLY = "        reply_text, cmds = txt, []\n"

for name, a in (("gem_msg", A_GEMMSG), ("auto key check", A_KEY),
                ("auto start", A_START), ("_auto_cmd", A_AUTOCMD),
                ("on_start", A_ONSTART), ("hard line", A_HARD),
                ("cooldown block", A_COOL), ("gemini thread", A_GTHREAD),
                ("429 block", A_429), ("reply_text", A_OKREPLY)):
    if main.count(a) != 1:
        die("anchor missing or not unique in main.py: " + name)

# ---------------- module-level functions ----------------
GEM_FUNCS = r'''def gemini_try(key, body):
    # tries Flash, then Flash-Lite; moves to the next model on 429/500/503
    code, raw = 0, ""
    for model in ("gemini-flash-latest", "gemini-flash-lite-latest"):
        u = GEMINI_URL.replace("gemini-flash-latest", model)
        for _ in range(2):
            code, raw = http_post(
                u, {"Content-Type": "application/json", "x-goog-api-key": key}, body)
            if code not in (500, 503):
                break
            time.sleep(2)
        if code not in (429, 500, 503):
            return code, raw
    return code, raw


def gemma_chat(system, user, max_tokens=300, want_json=False, timeout=170):
    # on-device Gemma through llama-server in Termux
    body = {"messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "max_tokens": max_tokens, "temperature": 0.4,
            "chat_template_kwargs": {"enable_thinking": False}}
    if want_json:
        body["response_format"] = {"type": "json_object"}
    rq = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
                                data=json.dumps(body).encode(),
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(rq, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    out = d["choices"][0]["message"]["content"].strip()
    return re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()


'''

# ---------------- class methods ----------------
METHODS = r'''    # ---------- Gemma first, Gemini only when needed ----------

    def gem_key(self):
        try:
            with open(self.key_path) as f:
                return f.read().strip()
        except Exception:
            return ""

    def gem_ok(self):
        return bool(self.gem_key()) and time.time() >= getattr(self, "gem_down_until", 0)

    def gem_mark_down(self):
        first = not getattr(self, "gem_was_down", False)
        self.gem_was_down = True
        self.gem_down_until = time.time() + 900
        if first:
            def say(dt):
                self.add_msg("Gemini limit reached. Using Gemma on the phone for now. "
                             "I will check again in 15 minutes.", False)
                self.notify("RAMBO AI", "Gemini limit reached. Using Gemma for now.")
            Clock.schedule_once(say, 0)

    def gem_mark_up(self):
        if getattr(self, "gem_was_down", False):
            self.gem_was_down = False
            self.gem_down_until = 0

            def say(dt):
                self.add_msg("Gemini is back.", False)
                self.notify("RAMBO AI", "Gemini is back.")
            Clock.schedule_once(say, 0)

    def gem_probe(self):
        # one tiny call, only while Gemini is marked down and the wait is over
        if not getattr(self, "gem_was_down", False):
            return
        if time.time() < getattr(self, "gem_down_until", 0):
            return
        key = self.gem_key()
        if not key or getattr(self, "gem_probing", False):
            return
        self.gem_probing = True
        try:
            body = json.dumps({"contents": [{"role": "user", "parts": [{"text": "Reply OK"}]}],
                               "generationConfig": {"maxOutputTokens": 5}}).encode()
            code, raw = gemini_try(key, body)
            if code == 200:
                self.gem_mark_up()
            elif code == 429:
                self.gem_down_until = time.time() + 900
        except Exception as e:
            self.err("gem probe", e)
        finally:
            self.gem_probing = False

    def _gemma_only(self, text):
        if not text:
            self.reply("Gemini is resting. Ask me again in a moment.")
            return
        facts = []
        try:
            facts = self.db.memories()
        except Exception:
            pass
        threading.Thread(target=self._gemma_only_thread, args=(text, facts), daemon=True).start()

    def _gemma_only_thread(self, text, facts):
        out = ""
        try:
            sp = ("You are RAMBO AI, a smart, friendly assistant on the user's Android phone. "
                  "Answer clearly in two to five practical sentences. If you are not sure, say so. ")
            if facts:
                sp += "Known facts about the user: " + "; ".join(facts) + ". "
            out = gemma_chat(sp, text, max_tokens=300)
        except Exception as e:
            self.err("gemma only", str(e)[:100])

        def done(dt):
            if out:
                self.reply(out)
            else:
                self.reply("Gemma is not running and Gemini is resting. "
                           "Start Gemma in Termux, then ask again.")
        Clock.schedule_once(done, 0)

    # ---------- keep the app alive in the background ----------

    def ka(self, on):
        try:
            from jnius import autoclass
            PA = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            ctx = PA.mActivity
            it = Intent()
            it.setClassName(ctx.getPackageName(), "org.rambo.acc.RamboKeepAlive")
            if on:
                if autoclass("android.os.Build$VERSION").SDK_INT >= 26:
                    ctx.startForegroundService(it)
                else:
                    ctx.startService(it)
            else:
                ctx.stopService(it)
        except Exception as e:
            self.err("keepalive", e)

    # ---------- auto run: runs on its own thread, Gemma first ----------

    def _auto_alive(self, pid, gen):
        return bool(self.auto_on and pid == self.cur_proj and gen == getattr(self, "auto_gen", 0))

    def _auto_sleep(self, pid, gen, secs):
        end = time.time() + secs
        while time.time() < end and self._auto_alive(pid, gen):
            time.sleep(1)

    def _auto_end(self, pid, status, why):
        self.auto_on = False
        try:
            if why:
                self.db.add_plog(pid, "run", why)
            self.db.set_pstatus(pid, status)
        except Exception as e:
            self.err("auto end", e)
        Clock.schedule_once(lambda dt: (self.refresh_projects(), self.update_proj_view()), 0)
        self.ka(False)

    def _auto_sys(self, p):
        s = ("You are RAMBO AI, working on a long project for the user, one small step per turn. "
             "Project: " + p[1] + ". Goal: " + (p[2] or "not stated") + ". "
             "Each turn do ONE useful step: produce real content (plan, research notes, draft, "
             "checklist, design, schedule, copy) or give phone commands. Do not repeat earlier steps. "
             'Reply ONLY with JSON: {"note": "what you did or produced", "commands": [], '
             '"question": "", "done": false}. Put a question in "question" if you need the '
             "user's input or hit a problem (then leave commands empty). Set done true only when the goal "
             "is fully finished. Allowed commands: open <app or website>, search <text>, timer <minutes>, "
             "alarm HH:MM, play <what to play on YouTube>. To play a song or video on YouTube use "
             "the play command by itself, do not open the app first. Max 3 commands. "
             "You cannot tap inside other apps.")
        try:
            facts = self.db.memories()
        except Exception:
            facts = []
        if facts:
            s += " Known facts about the user: " + "; ".join(facts) + "."
        s += " Now: " + datetime.now().strftime("%A %B %d %Y %I:%M %p") + "."
        return s

    def _auto_user(self, pid, n, cut):
        lines = [k.upper() + ": " + t[:cut] for ts, k, t in self.db.plog(pid, n)]
        return "Project log so far:\n" + "\n".join(lines) + "\n\nDo the next step."

    def _auto_parse(self, txt):
        t2 = (txt or "").strip()
        if not t2:
            return None
        if t2.startswith("```"):
            t2 = re.sub(r"^```(?:json)?|```$", "", t2, flags=re.M).strip()
        d = None
        try:
            d = json.loads(t2)
        except Exception:
            m = re.search(r"\{.*\}", t2, re.S)
            if m:
                try:
                    d = json.loads(m.group(0))
                except Exception:
                    d = None
        if not isinstance(d, dict):
            if t2.startswith("{"):
                return None
            return (t2[:1500], [], "", False)
        note = str(d.get("note", "")).strip()
        cmds = [str(x) for x in (d.get("commands") or [])][:3]
        question = str(d.get("question", "")).strip()
        done = bool(d.get("done", False))
        if not (note or cmds or question):
            return None
        return (note, cmds, question, done)

    def _auto_gemini(self, p, pid):
        try:
            payload = {
                "systemInstruction": {"parts": [{"text": self._auto_sys(p)}]},
                "contents": [{"role": "user", "parts": [{"text": self._auto_user(pid, 12, 500)}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            }
            code, raw = gemini_try(self.gem_key(), json.dumps(payload).encode())
        except Exception as e:
            self.err("auto gemini net", str(e)[:100])
            return None
        if code == 429:
            self.gem_mark_down()
            return None
        if code != 200:
            self.err("auto gemini " + str(code), raw[:150])
            return None
        try:
            txt = json.loads(raw)["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return None
        self.gem_mark_up()
        return self._auto_parse(txt)

    def _auto_loop(self, pid, gen):
        fails = 0
        try:
            while self._auto_alive(pid, gen):
                if self.auto_steps >= 15:
                    self._auto_end(pid, "paused",
                                   "Reached 15 steps in this run. Tap AUTO RUN to keep going.")
                    return
                p = self.db.get_project(pid)
                if not p:
                    return
                order = ["gemma", "gemini"]
                if (p[2] or "").lower().startswith("gemini:") and self.gem_ok():
                    order = ["gemini", "gemma"]
                res, src = None, ""
                for who in order:
                    if not self._auto_alive(pid, gen):
                        return
                    if who == "gemma":
                        try:
                            txt = gemma_chat(self._auto_sys(p), self._auto_user(pid, 6, 350),
                                             max_tokens=450, want_json=True)
                            res = self._auto_parse(txt)
                        except Exception as e:
                            self.err("auto gemma", str(e)[:100])
                            res = None
                        if res and res[0] and res[0] == getattr(self, "_last_note", None):
                            res = None
                        src = "Gemma"
                    else:
                        if not self.gem_ok():
                            continue
                        res = self._auto_gemini(p, pid)
                        src = "Gemini"
                    if res:
                        break
                if not self._auto_alive(pid, gen):
                    return
                if res is None:
                    fails += 1
                    if fails >= 4:
                        self._auto_end(pid, "paused",
                                       "No model answered. Start Gemma in Termux, or check the Gemini key. Paused.")
                        return
                    wait = min(10 * (2 ** (fails - 1)), 60)
                    self.auto_note = "Waiting for a model, retry %d in %d s." % (fails, wait)
                    self._auto_sleep(pid, gen, wait)
                    continue
                fails = 0
                self.auto_note = ""
                note, cmds, question, done = res
                if note:
                    self._last_note = note
                    self.db.add_plog(pid, "pal", note)
                if src == "Gemini":
                    self.db.add_plog(pid, "run", "Used Gemini for this step.")
                self.auto_steps += 1
                for n, cm in enumerate(cmds):
                    Clock.schedule_once(lambda dt, cm=cm: self._auto_cmd(pid, cm), 1 + 1.5 * n)
                pname = p[1]
                if question:
                    self.db.add_plog(pid, "ask", question)
                    self._auto_end(pid, "waiting", None)
                    self.notify("RAMBO AI needs you: " + pname, question)
                    Clock.schedule_once(lambda dt: self.speak(question), 0)
                    return
                if done and (src == "Gemini" or self.auto_steps >= 3):
                    self._auto_end(pid, "done", None)
                    self.notify("Project finished: " + pname, (note or "Done.")[:150])
                    Clock.schedule_once(
                        lambda dt: self.speak("Project " + pname + " is finished."), 0)
                    return
                self._auto_sleep(pid, gen, (25 if src == "Gemini" else 6) + 1.5 * len(cmds))
        except Exception as e:
            self.err("auto loop", e)
            try:
                self._auto_end(pid, "paused", "Auto run error: " + str(e)[:120])
            except Exception:
                pass
        finally:
            if not self.auto_on:
                self.ka(False)

'''

# ---------------- Java keep-alive service ----------------
JAVA = r'''package org.rambo.acc;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

public class RamboKeepAlive extends Service {
    private PowerManager.WakeLock wl = null;

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        try {
            Notification.Builder b;
            if (Build.VERSION.SDK_INT >= 26) {
                NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
                nm.createNotificationChannel(new NotificationChannel(
                        "rambo_keep", "RAMBO AI running", NotificationManager.IMPORTANCE_LOW));
                b = new Notification.Builder(this, "rambo_keep");
            } else {
                b = new Notification.Builder(this);
            }
            Intent li = getPackageManager().getLaunchIntentForPackage(getPackageName());
            if (li != null) {
                int fl = PendingIntent.FLAG_UPDATE_CURRENT;
                if (Build.VERSION.SDK_INT >= 23) {
                    fl |= PendingIntent.FLAG_IMMUTABLE;
                }
                b.setContentIntent(PendingIntent.getActivity(this, 0, li, fl));
            }
            b.setSmallIcon(getApplicationInfo().icon);
            b.setContentTitle("RAMBO AI is working");
            b.setContentText("Auto run is going in the background");
            b.setOngoing(true);
            Notification n = b.build();
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(2, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
            } else {
                startForeground(2, n);
            }
            if (wl == null) {
                PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
                wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "rambo:keep");
                wl.acquire(6 * 60 * 60 * 1000L);
            }
        } catch (Exception e) {
        }
        return START_NOT_STICKY;
    }

    @Override
    public void onDestroy() {
        try {
            if (wl != null && wl.isHeld()) {
                wl.release();
            }
        } catch (Exception e) {
        }
        wl = null;
        super.onDestroy();
    }
}
'''

SERVICE_XML = ('<service android:name="org.rambo.acc.RamboKeepAlive"\n'
               '    android:exported="false"\n'
               '    android:foregroundServiceType="dataSync" />\n')


def add_perms(s):
    need = ["FOREGROUND_SERVICE", "FOREGROUND_SERVICE_DATA_SYNC",
            "WAKE_LOCK", "POST_NOTIFICATIONS"]
    m = re.search(r"^android\.permissions\s*=\s*(.*)$", s, re.M)
    if not m:
        line = "android.permissions = INTERNET," + ",".join(need)
        return s.replace("android.allow_backup = True",
                         "android.allow_backup = True\n\n" + line, 1)
    cur = m.group(1)
    have = [x.strip().upper() for x in cur.split(",")]
    add = [n for n in need if not any(h == n or h.endswith("." + n) for h in have)]
    if not add:
        return s
    base = cur.rstrip().rstrip(",")
    line = "android.permissions = " + ",".join(([base] if base else []) + add)
    return s[:m.start()] + line + s[m.end():]


# ---------------- apply ----------------
shutil.copy(MAIN, MAIN + ".bak33p")
shutil.copy(SPEC, SPEC + ".bak33p")
shutil.copy(MANI, MANI + ".bak33p")

new = main
new = new.replace(A_GEMMSG, GEM_FUNCS + A_GEMMSG, 1)
new = new.replace(A_KEY, "", 1)
new = new.replace(
    A_START,
    '        self.auto_gen = getattr(self, "auto_gen", 0) + 1\n'
    '        self.ka(True)\n'
    '        threading.Thread(target=self._auto_loop,\n'
    '                         args=(self.cur_proj, self.auto_gen), daemon=True).start()\n', 1)
new = new.replace(A_AUTOCMD, METHODS + A_AUTOCMD, 1)
new = new.replace(
    A_ONSTART,
    A_ONSTART +
    '        Clock.schedule_interval(\n'
    '            lambda dt: threading.Thread(target=self.gem_probe, daemon=True).start(), 60)\n', 1)
new = new.replace(
    A_HARD,
    '            hard = low.startswith("gemini") or len(text) > 700\n', 1)
new = new.replace(
    A_COOL,
    '        self._last_cloud_text = text\n'
    '        if time.time() < getattr(self, "gem_down_until", 0):\n'
    '            self._gemma_only(text)\n'
    '            return\n', 1)
new = new.replace(A_GTHREAD, A_GTHREAD.replace("gemini_post", "gemini_try"), 1)
new = new.replace(
    A_429,
    '        if code == 429:\n'
    '            self.gem_mark_down()\n'
    '            self._gemma_only(getattr(self, "_last_cloud_text", ""))\n'
    '            return\n', 1)
new = new.replace(A_OKREPLY, "        self.gem_mark_up()\n" + A_OKREPLY, 1)

with open(MAIN, "w") as f:
    f.write(new)
try:
    py_compile.compile(MAIN, doraise=True, cfile="_main_check.pyc")
except Exception as e:
    shutil.copy(MAIN + ".bak33p", MAIN)
    die("main.py failed to compile, restored backup: " + str(e)[:300])
try:
    os.remove("_main_check.pyc")
except Exception:
    pass

os.makedirs(os.path.join(ROOT, "java/org/rambo/acc"), exist_ok=True)
with open(os.path.join(ROOT, "java/org/rambo/acc/RamboKeepAlive.java"), "w") as f:
    f.write(JAVA)

if "RamboKeepAlive" not in mani:
    with open(MANI, "w") as f:
        f.write(mani.rstrip("\n") + "\n" + SERVICE_XML)

new_spec = add_perms(spec)
if new_spec != spec:
    with open(SPEC, "w") as f:
        f.write(new_spec)

print("OK_PATCHED_V33")
print("Backups: main.py.bak33p, buildozer.spec.bak33p, manifest_service.xml.bak33p")
print("New file: java/org/rambo/acc/RamboKeepAlive.java")
print("Permissions line now:")
for ln in open(SPEC):
    if ln.startswith("android.permissions"):
        print("  " + ln.strip())
