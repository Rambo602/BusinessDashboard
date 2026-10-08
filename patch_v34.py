#!/usr/bin/env python3
# patch_v34.py - routes by task type, browses the web by itself, never launches Chrome
# Run AFTER patch_v33, from ~/BusinessDashboard:  python patch_v34.py
# Backs up main.py first. Aborts if an anchor is missing. No build-file changes.
import os, sys, shutil, py_compile

ROOT = os.getcwd()
MAIN = os.path.join(ROOT, "main.py")


def die(msg):
    print("STOPPED: " + msg)
    sys.exit(1)


if not os.path.exists(MAIN):
    die("run this from ~/BusinessDashboard (main.py missing)")
main = open(MAIN).read()

if "def web_search" in main:
    die("patch v34 already applied")
if "def gemma_chat" not in main:
    die("apply patch_v33.py first")

A_FUNC = "def gemma_chat("
A_START = "    def _auto_sys(self, p):\n"
A_END = "    def _auto_cmd(self, pid, cm):\n"
for name, a in (("gemma_chat", A_FUNC), ("_auto_sys", A_START), ("_auto_cmd", A_END)):
    if main.count(a) != 1:
        die("anchor missing or not unique in main.py: " + name)
if main.index(A_START) > main.index(A_END):
    die("auto run methods are not in the expected order")

WEB_FUNCS = r'''import html as _html
import urllib.parse
import urllib.request

LIVE_WORDS = ("search", "research", "find", "look up", "lookup", "latest", "current",
              "price", "cost", "news", "online", "internet", "web", "google", "fab",
              "website", "http", "www.", ".com", "compare", "review", "best ",
              "today", "tutorial", "how to", "download", "marketplace", "trending",
              "competitor", "listing", "available", "release", "docs", "documentation")
HEAVY_WORDS = ("analy", "strategy", "unreal", "blueprint", "script", "code",
               "architecture", "business plan", "report", "design a")


def needs_live(goal):
    low = (goal or "").lower()
    return any(w in low for w in LIVE_WORDS)


def pick_first(goal):
    # which model should try a project's steps first
    low = (goal or "").lower()
    if low.startswith("gemini:") or needs_live(low) or len(low) > 400:
        return "gemini"
    if any(w in low for w in HEAVY_WORDS):
        return "gemini"
    return "gemma"


def looks_url(s):
    return bool(re.match(r"^(https?://)?[\w.-]+\.(com|org|net|io|gg|dev|app|co|ai|edu|gov|info)(/\S*)?$",
                         (s or "").strip(), re.I))


def _clean(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


def _http_get(url, timeout=20):
    rq = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(rq, timeout=timeout) as r:
        raw = r.read(700000)
        cs = r.headers.get_content_charset() or "utf-8"
    return raw.decode(cs, "replace")


def parse_results(page, n=5):
    out = []
    pat = (r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
           r'(.*?)(?=<a[^>]+class="result__a"|$)')
    for m in re.finditer(pat, page, re.S):
        href, title, rest = m.group(1), _clean(m.group(2)), m.group(3)
        u = re.search(r"uddg=([^&]+)", href)
        url = urllib.parse.unquote(u.group(1)) if u else href
        if url.startswith("//"):
            url = "https:" + url
        if "duckduckgo.com/y.js" in url or not url.startswith("http"):
            continue
        sn = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', rest, re.S)
        out.append((title, url, _clean(sn.group(1)) if sn else ""))
        if len(out) >= n:
            break
    return out


def web_search(q, n=5):
    page = _http_get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(q))
    return parse_results(page, n)


def web_read(url, limit=3500):
    if not url.lower().startswith("http"):
        url = "https://" + url
    page = _http_get(url)
    page = re.sub(r"(?is)<(script|style|nav|header|footer|svg|noscript|form)\b.*?</\1>", " ", page)
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
    body = _clean(page)
    return ((_clean(title.group(1)) + ". ") if title else "") + body[:limit]


'''

NEW_METHODS = r'''    def _auto_sys(self, p):
        s = ("You are RAMBO AI, working on a long project for the user, one small step per turn. "
             "Project: " + p[1] + ". Goal: " + (p[2] or "not stated") + ". "
             "Each turn do ONE useful step: produce real content (plan, research notes, draft, "
             "checklist, design, schedule, copy), research on the web, or give phone commands. "
             "Do not repeat earlier steps. "
             'Reply ONLY with JSON: {"note": "what you did or found", "commands": [], '
             '"search_web": "", "read_url": "", "question": "", "done": false}. '
             "You can browse the internet yourself. Set search_web to a short web search query, "
             "or read_url to a full page URL. The app runs it in the background and the results "
             "appear in the project log as WEB lines on your next turn. When the goal needs "
             "current or real facts (prices, products, listings, news, documentation), search "
             "first, then read the best result, then use what you read. Never invent facts that "
             "should come from the web, and put the source URL in the note. Do not use the "
             "open or search commands for browsing. "
             'Put a question in "question" if you need the user\'s input or hit a problem '
             "(then leave commands empty). Set done true only when the goal is fully finished. "
             "Allowed commands: open <app>, timer <minutes>, alarm HH:MM, "
             "play <what to play on YouTube>. To play a song or video use the play command by "
             "itself. Max 3 commands. You cannot tap inside other apps.")
        try:
            facts = self.db.memories()
        except Exception:
            facts = []
        if facts:
            s += " Known facts about the user: " + "; ".join(facts) + "."
        s += " Now: " + datetime.now().strftime("%A %B %d %Y %I:%M %p") + "."
        return s

    def _auto_user(self, pid, n, cut, webcut=900):
        lines = []
        for ts, k, t in self.db.plog(pid, n):
            lines.append(k.upper() + ": " + t[:(webcut if t.startswith("WEB") else cut)])
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
            return (t2[:1500], [], "", False, "", "")
        note = str(d.get("note", "")).strip()
        cmds = [str(x) for x in (d.get("commands") or [])][:3]
        question = str(d.get("question", "")).strip()
        done = bool(d.get("done", False))
        sw = str(d.get("search_web", "") or "").strip()
        ru = str(d.get("read_url", "") or "").strip()
        if not (note or cmds or question or sw or ru):
            return None
        return (note, cmds, question, done, sw, ru)

    def _auto_weak(self, res):
        # thin answer from Gemma: escalate to Gemini when it is available
        note, cmds, question, done, sw, ru = res
        if cmds or question or sw or ru:
            return False
        return len(note) < 40

    def _auto_gemini(self, p, pid, live):
        key = self.gem_key()
        try:
            payload = {
                "systemInstruction": {"parts": [{"text": self._auto_sys(p)}]},
                "contents": [{"role": "user",
                              "parts": [{"text": self._auto_user(pid, 12, 500, 2000)}]}],
            }
            if live:
                # Google Search through Gemini. Cannot be combined with JSON mode,
                # so the answer is parsed from text.
                payload["tools"] = [{"google_search": {}}]
            else:
                payload["generationConfig"] = {"responseMimeType": "application/json"}
            code, raw = gemini_try(key, json.dumps(payload).encode())
            if live and code == 400:
                payload.pop("tools", None)
                payload["generationConfig"] = {"responseMimeType": "application/json"}
                code, raw = gemini_try(key, json.dumps(payload).encode())
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
            parts = json.loads(raw)["candidates"][0]["content"]["parts"]
            txt = "".join(x.get("text", "") for x in parts)
        except Exception:
            return None
        self.gem_mark_up()
        return self._auto_parse(txt)

    def _auto_web(self, pid, kind, arg):
        # live browsing from the background thread; no Chrome, nothing for Android to block
        try:
            if kind == "search":
                rows = web_search(arg)
                if not rows:
                    self.db.add_plog(pid, "run", "WEB SEARCH '" + arg[:80] + "': no results.")
                    return
                txt = "\n".join("%d. %s - %s (%s)" % (i + 1, t, s[:200], u)
                                for i, (t, u, s) in enumerate(rows))
                self.db.add_plog(pid, "run", "WEB SEARCH '" + arg[:80] + "':\n" + txt)
            else:
                txt = web_read(arg)
                self.db.add_plog(pid, "run", "WEB PAGE " + arg[:120] + ":\n" + txt)
        except Exception as e:
            self.db.add_plog(pid, "run", "WEB " + kind.upper() + " FAILED (" + arg[:80] + "): "
                             + str(e)[:80])

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
                goal = p[2] or ""
                live = needs_live(goal)
                # first research step happens automatically for goals that need live facts
                if live and self.auto_steps == 0 and not any(
                        t.startswith("WEB") for ts, k, t in self.db.plog(pid, 30)):
                    self._auto_web(pid, "search", goal.replace("gemini:", "").strip()[:120])
                order = ["gemma", "gemini"]
                if pick_first(goal) == "gemini" and self.gem_ok():
                    order = ["gemini", "gemma"]
                res, src, spare = None, "", None
                for who in order:
                    if not self._auto_alive(pid, gen):
                        return
                    got = None
                    if who == "gemma":
                        try:
                            txt = gemma_chat(self._auto_sys(p),
                                             self._auto_user(pid, 6, 350, 900),
                                             max_tokens=450, want_json=True)
                            got = self._auto_parse(txt)
                        except Exception as e:
                            self.err("auto gemma", str(e)[:100])
                            got = None
                        if got and got[0] and got[0] == getattr(self, "_last_note", None):
                            got = None
                    else:
                        if not self.gem_ok():
                            continue
                        got = self._auto_gemini(p, pid, live)
                        if got and got[0] and got[0] == getattr(self, "_last_note", None):
                            got = None
                    if got and self._auto_weak(got) and self.gem_ok() and who == "gemma":
                        spare = (got, "Gemma")
                        continue
                    if got:
                        res, src = got, ("Gemma" if who == "gemma" else "Gemini")
                        break
                if res is None and spare:
                    res, src = spare
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
                note, cmds, question, done, sw, ru = res
                if note:
                    self._last_note = note
                    self.db.add_plog(pid, "pal", note)
                if src == "Gemini":
                    self.db.add_plog(pid, "run", "Used Gemini for this step.")
                self.auto_steps += 1
                jobs, keep = [], []
                if sw:
                    jobs.append(("search", sw))
                if ru:
                    jobs.append(("read", ru))
                for cm in cmds:
                    c = cm.strip()
                    low = c.lower()
                    if low.startswith("search "):
                        jobs.append(("search", c[7:].strip()))
                    elif low.startswith("open ") and looks_url(c[5:]):
                        jobs.append(("read", c[5:].strip()))
                    else:
                        keep.append(c)
                seen = [t for ts, k, t in self.db.plog(pid, 40) if t.startswith("WEB")]
                fresh = []
                for kind, arg in jobs[:3]:
                    tag = ("WEB SEARCH '" if kind == "search" else "WEB PAGE ") + arg[:80 if kind == "search" else 120]
                    if any(t.startswith(tag) for t in seen):
                        continue
                    fresh.append((kind, arg))
                jobs = fresh
                for kind, arg in jobs:
                    if not self._auto_alive(pid, gen):
                        return
                    self._auto_web(pid, kind, arg)
                for n, cm in enumerate(keep):
                    Clock.schedule_once(lambda dt, cm=cm: self._auto_cmd(pid, cm), 1 + 1.5 * n)
                pname = p[1]
                if question:
                    self.db.add_plog(pid, "ask", question)
                    self._auto_end(pid, "waiting", None)
                    self.notify("RAMBO AI needs you: " + pname, question)
                    Clock.schedule_once(lambda dt: self.speak(question), 0)
                    return
                if done and not jobs and (src == "Gemini" or self.auto_steps >= 3):
                    self._auto_end(pid, "done", None)
                    self.notify("Project finished: " + pname, (note or "Done.")[:150])
                    Clock.schedule_once(
                        lambda dt: self.speak("Project " + pname + " is finished."), 0)
                    return
                self._auto_sleep(pid, gen, (25 if src == "Gemini" else 6) + 1.5 * len(keep))
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

shutil.copy(MAIN, MAIN + ".bak34p")
i, j = main.index(A_START), main.index(A_END)
new = main[:i] + NEW_METHODS + main[j:]
new = new.replace(A_FUNC, WEB_FUNCS + A_FUNC, 1)
with open(MAIN, "w") as f:
    f.write(new)
try:
    py_compile.compile(MAIN, doraise=True, cfile="_main_check.pyc")
except Exception as e:
    shutil.copy(MAIN + ".bak34p", MAIN)
    die("main.py failed to compile, restored backup: " + str(e)[:300])
try:
    os.remove("_main_check.pyc")
except Exception:
    pass
print("OK_PATCHED_V34")
print("Backup: main.py.bak34p")
