__version__ = "1.3.7"
# Pocket Pal v1.2 (chat screen, voice, talk back, memory, local-first router)

import os
import re
import json
import time
import sqlite3
import threading
import traceback
import urllib.request
from datetime import datetime
from urllib.parse import quote

from kivy.app import App
from kivy.base import ExceptionHandler, ExceptionManager
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget


GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "gemini-flash-latest:generateContent")
CRASH_PATH = [None]

ACC_HELP = ("Accessibility commands: acc settings | acc status | acc screen | "
            "acc tap <text> | acc tapxy <x> <y> | acc type <text> | acc clip <text> | "
            "acc paste | acc scroll down | acc scroll up | acc back | acc home. "
            "Add 'in 5' in front to wait 5 seconds so you can switch apps first, "
            "for example: in 5 acc screen")

ACC_AUTO = ("You can also use the screen of other apps: acc screen (reads the visible text, "
            "it appears as a SCREEN line on your next turn), acc tap <exact text on screen>, "
            "acc type <text>, acc clip <text>, acc paste, acc scroll down, acc scroll up, acc back, acc home. "
            "To work inside an app: open <app>, then acc screen, then ONE tap or type, then acc screen "
            "again to check it worked before the next step. Never invent button names, only tap text you "
            "saw in a SCREEN line. Never tap or type send, pay, buy, order, delete, post or submit: the app "
            "stops and asks the user. If the screen does not show what you need, set question.")

AUTO_RISKY = re.compile(r"\b(send|pay|payment|buy|purchase|order|checkout|check out|delete|remove|erase|"
                        r"post|publish|submit|transfer|confirm|subscribe|uninstall|reset|log ?out|sign ?out)\b",
                        re.I)

LEARN_RX = [
    re.compile(r"^(?:my name is|call me)\s+[a-z][a-z' -]{1,30}$", re.I),
    re.compile(r"^i (?:live|work|study) (?:in|at|for|with)\s+.{2,60}$", re.I),
    re.compile(r"^i (?:really )?(?:like|love|prefer|hate|dislike|enjoy)\s+.{2,60}$", re.I),
    re.compile(r"^my (?:goal|focus|job|business|dream|plan|favou?rite [a-z ]{2,20}) (?:is|are)\s+.{2,80}$", re.I),
    re.compile(r"^i(?:'m| am) (?:building|working on|learning|studying|making|starting)\s+.{2,80}$", re.I),
]


def learn_fact(text):
    t = " ".join((text or "").strip().split()).rstrip(".!")
    if not t or len(t) > 140 or "?" in t:
        return None
    if re.match(r"^(?:remember|forget|note|add|open|search|call|text|play|timer|alarm|acc)\b", t, re.I):
        return None
    if re.search(r"\b(?:love|like|hate|dislike|enjoy|prefer) (?:you|it|that|this|them|him|her|u)\b", t, re.I):
        return None
    for rx in LEARN_RX:
        if rx.match(t):
            return t[0].upper() + t[1:]
    return None


HELP = ("Say or type: open youtube | search cats | timer 10 minutes | "
        "alarm 7:30 | add task buy milk | what time is it | "
        "remember my gym is at 6am | forget gym. "
        "Anything else goes to Gemini. Also: backup, restore, errors, clear chat.")


class CrashLogger(ExceptionHandler):
    def handle_exception(self, inst):
        try:
            if CRASH_PATH[0]:
                with open(CRASH_PATH[0], "a") as f:
                    f.write(datetime.now().isoformat() + "\n"
                            + traceback.format_exc() + "\n")
        except Exception:
            pass
        return ExceptionManager.PASS


ExceptionManager.add_handler(CrashLogger())


def build_system(facts):
    s = ('You are RAMBO AI, a friendly voice assistant on the user\'s Android phone. '
         'Reply ONLY with JSON: {"commands": [], "reply": "what you say to the user"}. '
         'Keep replies short for simple questions. When asked to explain or write code, give a complete answer and put code inside ``` blocks. '
         'Put phone actions in "commands" only when the user asked for an action. '
         'Allowed commands: open <app name or website>, search <text>, call <number>, '
         'text <number> <message>, timer <minutes>, alarm HH:MM, play <what to play on YouTube>. Max 5 commands. '
         'If you need more information to finish a task, ask in the reply and leave commands empty.')
    if facts:
        s += " Known facts about the user: " + "; ".join(facts) + "."
    s += " Current date and time: " + datetime.now().strftime("%A %B %d %Y %I:%M %p") + "."
    return s


def http_post(url, headers, body):
    from jnius import autoclass, cast
    URL = autoclass("java.net.URL")
    Scanner = autoclass("java.util.Scanner")
    conn = cast("java.net.HttpURLConnection", URL(url).openConnection())
    conn.setRequestMethod("POST")
    conn.setConnectTimeout(10000)
    conn.setReadTimeout(60000)
    for k, v in headers.items():
        conn.setRequestProperty(k, v)
    conn.setDoOutput(True)
    out = conn.getOutputStream()
    out.write(body)
    out.close()
    code = conn.getResponseCode()
    stream = conn.getInputStream() if code < 400 else conn.getErrorStream()
    sc = Scanner(stream, "UTF-8").useDelimiter("\\A")
    text = sc.next() if sc.hasNext() else ""
    return code, text


def http_get(url):
    from jnius import autoclass, cast
    URL = autoclass("java.net.URL")
    Scanner = autoclass("java.util.Scanner")
    conn = cast("java.net.HttpURLConnection", URL(url).openConnection())
    conn.setRequestMethod("GET")
    conn.setConnectTimeout(20000)
    conn.setReadTimeout(30000)
    conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    conn.setRequestProperty("Cookie", "CONSENT=YES+1; SOCS=CAI")
    conn.setRequestProperty("Accept-Language", "en-US,en;q=0.9")
    code = conn.getResponseCode()
    stream = conn.getInputStream() if code < 400 else conn.getErrorStream()
    sc = Scanner(stream, "UTF-8").useDelimiter("\\A")
    text = sc.next() if sc.hasNext() else ""
    return code, text


def gemini_post(key, body):
    lite = GEMINI_URL.replace("gemini-flash-latest", "gemini-flash-lite-latest")
    code, raw = 0, ""
    for u in (GEMINI_URL, lite, GEMINI_URL, lite):
        code, raw = http_post(
            u, {"Content-Type": "application/json", "x-goog-api-key": key}, body)
        if code not in (500, 503):
            break
        time.sleep(2)
    return code, raw


_GROQ = {"key": "", "path": ""}


def _groq_key():
    if _GROQ["key"]:
        return _GROQ["key"]
    try:
        if _GROQ["path"] and os.path.exists(_GROQ["path"]):
            _GROQ["key"] = open(_GROQ["path"]).read().strip()
    except Exception:
        pass
    return _GROQ["key"]


def _groq_save(folder, key):
    try:
        p = os.path.join(folder, "groq.key")
        with open(p, "w") as f:
            f.write(key.strip())
        _GROQ["path"] = p
        _GROQ["key"] = key.strip()
        return "Groq key saved. It now backs up Gemini automatically."
    except Exception as e:
        return "Could not save the key: " + str(e)[:80]


def _groq_fallback(body, code, raw):
    k = _groq_key()
    if not k:
        return code, raw
    try:
        d = json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
        msgs = []
        si = d.get("systemInstruction") or d.get("system_instruction")
        if si:
            t = " ".join(p.get("text", "") for p in si.get("parts", []))
            if t.strip():
                msgs.append({"role": "system", "content": t})
        for c in d.get("contents", []):
            t = " ".join(p.get("text", "") for p in c.get("parts", []) if "text" in p)
            if not t.strip():
                continue
            r = "assistant" if c.get("role") == "model" else "user"
            if msgs and msgs[-1]["role"] == r:
                msgs[-1]["content"] += "\n" + t
            else:
                msgs.append({"role": r, "content": t})
        if not any(m["role"] == "user" for m in msgs):
            return code, raw
        rb = json.dumps({"model": "llama-3.3-70b-versatile", "messages": msgs,
                         "max_tokens": 2000, "temperature": 0.4}).encode()
        c2, r2 = http_post("https://api.groq.com/openai/v1/chat/completions",
                           {"Content-Type": "application/json", "Authorization": "Bearer " + k}, rb)
        if c2 != 200:
            return code, raw
        txt = json.loads(r2)["choices"][0]["message"]["content"]
        return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": txt}]},
                                                "finishReason": "STOP"}]})
    except Exception:
        return code, raw


def gemini_try(key, body):
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
    return _groq_fallback(body, code, raw)


import html as _html
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
    return ("termux" not in low) and any(w in low for w in LIVE_WORDS)


def pick_first(goal):
    # which model should try a project's steps first
    low = (goal or "").lower()
    if low.startswith("gemini:") or needs_live(low):
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


def gem_msg(raw):
    try:
        return str(json.loads(raw)["error"]["message"])[:150]
    except Exception:
        return (raw or "no details")[:100]


def autosize(lbl):
    lbl.size_hint_y = None
    lbl.halign = "left"
    lbl.valign = "top"
    lbl.bind(width=lambda w, v: setattr(w, "text_size", (v, None)),
             texture_size=lambda w, v: setattr(w, "height", v[1] + 10))
    return lbl


from kivy.metrics import dp as _dp

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

try:
    import ssl as _ssl, certifi as _certifi
    os.environ["SSL_CERT_FILE"] = _certifi.where()
    _ssl._create_default_https_context = lambda *a, **k: _ssl.create_default_context(cafile=_certifi.where())
except Exception:
    pass


def mk_input(hint, multiline=False, height=45, **kw):
    return TextInput(input_type="text", keyboard_suggestions=True,
                     hint_text=hint, multiline=multiline,
                     size_hint_y=None, height=_dp(height), **style_in(kw))


class Bubble(Label):
    def __init__(self, mine=False, **kw):
        super().__init__(**kw)
        self.mine = mine
        self.size_hint_y = None
        self.halign = "left"
        self.valign = "middle" if mine else "top"
        self.font_size = "17sp"
        self.color = (1, 1, 1, 1) if mine else (0.92, 0.96, 1.0, 1)
        self._rect = None
        if mine:
            with self.canvas.before:
                Color(0.12, 0.17, 0.30, 1)
                self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[20])
        self.bind(pos=self._upd, size=self._upd,
                  width=self._tw, texture_size=self._th)

    def _tw(self, *a):
        pad = 28 if self.mine else 6
        self.text_size = (max(self.width - pad, 10), None)

    def _th(self, *a):
        self.height = self.texture_size[1] + (26 if self.mine else 14)

    def _upd(self, *a):
        if self._rect is not None:
            self._rect.pos = self.pos
            self._rect.size = self.size

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


from kivy.graphics import Line
from kivy.uix.gridlayout import GridLayout

BG = (0.02, 0.03, 0.08, 1)
INBG = (0.05, 0.08, 0.17, 1)
TXT = (0.85, 1.0, 1.0, 1)
CYAN = (0.0, 0.9, 1.0, 1)
MAGENTA = (0.85, 0.3, 1.0, 1)
GREEN = (0.1, 1.0, 0.6, 1)
AMBER = (1.0, 0.7, 0.15, 1)


def style_in(kw):
    kw.setdefault("background_color", INBG)
    kw.setdefault("foreground_color", TXT)
    kw.setdefault("cursor_color", CYAN)
    kw.setdefault("hint_text_color", (0.4, 0.55, 0.65, 1))
    return kw


class NeonButton(Button):
    def __init__(self, glow=CYAN, **kw):
        super().__init__(**kw)
        self.glow = glow
        self.active = False
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = glow
        self.bold = True
        with self.canvas.before:
            self._fill = Color(0, 0, 0, 1)
            self._r = RoundedRectangle(pos=self.pos, size=self.size, radius=[14])
            Color(*glow)
            self._l = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, 14), width=1.4)
        self.bind(pos=self._u, size=self._u, state=self._paint)
        self._paint()

    def _u(self, *a):
        self._r.pos = self.pos
        self._r.size = self.size
        self._l.rounded_rectangle = (self.x, self.y, self.width, self.height, 14)

    def _paint(self, *a):
        k = 0.5 if (self.active or self.state == "down") else 0.16
        g = self.glow
        self._fill.rgba = (g[0] * k, g[1] * k, g[2] * k, 1)

    def set_active(self, on):
        self.active = on
        self._paint()



class Database:

    def __init__(self, path):
        self.conn = sqlite3.connect(
            path,
            check_same_thread=False
        )
        self.create_tables()
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS jobs ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "target TEXT, command TEXT, status TEXT, "
            "result TEXT, created_at TEXT)"
        )
        self.conn.commit()

    def create_tables(self):

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS finances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT,
            amount REAL,
            category TEXT,
            created_at TEXT
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS gmail_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT,
            subject TEXT,
            body TEXT,
            status TEXT DEFAULT 'queued',
            created_at TEXT
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS youtube_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_url TEXT,
            comment TEXT,
            status TEXT DEFAULT 'queued',
            created_at TEXT
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS website_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            content_size INTEGER,
            checked_at TEXT
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            created_at TEXT
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact TEXT,
            created_at TEXT
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            text TEXT,
            created_at TEXT
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            goal TEXT,
            status TEXT,
            created_at TEXT
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS project_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            kind TEXT,
            text TEXT,
            created_at TEXT
        )
        """)

        self.conn.commit()

    def log(self, message):
        self.conn.execute(
            "INSERT INTO activity(message, created_at) VALUES (?, ?)",
            (message, datetime.now().isoformat())
        )
        self.conn.commit()

    def add_task(self, task):
        self.conn.execute(
            "INSERT INTO tasks(task, created_at) VALUES (?, ?)",
            (task, datetime.now().isoformat())
        )
        self.conn.commit()

    def add_finance(self, description, amount, category):
        self.conn.execute(
            """
            INSERT INTO finances
            (description, amount, category, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                description,
                amount,
                category,
                datetime.now().isoformat()
            )
        )
        self.conn.commit()

    def queue_email(self, recipient, subject, body):
        self.conn.execute(
            """
            INSERT INTO gmail_queue
            (recipient, subject, body, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                recipient,
                subject,
                body,
                datetime.now().isoformat()
            )
        )
        self.conn.commit()

    def queue_youtube(self, url, comment):
        self.conn.execute(
            """
            INSERT INTO youtube_queue
            (video_url, comment, created_at)
            VALUES (?, ?, ?)
            """,
            (
                url,
                comment,
                datetime.now().isoformat()
            )
        )
        self.conn.commit()

    def cache_website(self, url, size):
        self.conn.execute(
            """
            INSERT INTO website_cache
            (url, content_size, checked_at)
            VALUES (?, ?, ?)
            """,
            (
                url,
                size,
                datetime.now().isoformat()
            )
        )
        self.conn.commit()

    def finance_total(self):
        result = self.conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM finances"
        ).fetchone()

        return result[0]

    def task_count(self):
        return self.conn.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

    def email_count(self):
        return self.conn.execute(
            """
            SELECT COUNT(*)
            FROM gmail_queue
            WHERE status='queued'
            """
        ).fetchone()[0]

    def youtube_count(self):
        return self.conn.execute(
            """
            SELECT COUNT(*)
            FROM youtube_queue
            WHERE status='queued'
            """
        ).fetchone()[0]

    def recent_logs(self):
        return self.conn.execute(
            """
            SELECT created_at, message
            FROM activity
            ORDER BY id DESC
            LIMIT 8
            """
        ).fetchall()

    def add_job(self, target, command):
        self.conn.execute(
            "INSERT INTO jobs(target, command, status, result, created_at) "
            "VALUES (?, ?, 'queued', '', ?)",
            (target, command, datetime.now().isoformat())
        )
        self.conn.commit()

    def job_count(self):
        return self.conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status='queued'"
        ).fetchone()[0]

    def add_memory(self, fact):
        self.conn.execute(
            "INSERT INTO memory(fact, created_at) VALUES (?, ?)",
            (fact, datetime.now().isoformat()))
        self.conn.commit()

    def memories(self, limit=40):
        rows = self.conn.execute(
            "SELECT fact FROM memory ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
        return [r[0] for r in reversed(rows)]

    def forget(self, term):
        cur = self.conn.execute(
            "DELETE FROM memory WHERE LOWER(fact) LIKE ?",
            ("%" + term.lower() + "%",))
        self.conn.commit()
        return cur.rowcount

    def add_chat(self, role, text):
        self.conn.execute(
            "INSERT INTO chat(role, text, created_at) VALUES (?, ?, ?)",
            (role, text, datetime.now().isoformat()))
        self.conn.commit()

    def recent_chat(self, n=30):
        rows = self.conn.execute(
            "SELECT role, text FROM chat ORDER BY id DESC LIMIT ?",
            (n,)).fetchall()
        return list(reversed(rows))

    def clear_chat(self):
        self.conn.execute("DELETE FROM chat")
        self.conn.commit()

    def list_tasks(self, n=10):
        return [r[0] for r in self.conn.execute(
            "SELECT task FROM tasks ORDER BY id DESC LIMIT ?", (n,)).fetchall()]

    def errors(self, n=5):
        return self.conn.execute(
            "SELECT created_at, message FROM activity "
            "WHERE message LIKE 'ERROR%' ORDER BY id DESC LIMIT ?",
            (n,)).fetchall()

    BACKUP_TABLES = ["tasks", "finances", "gmail_queue", "youtube_queue",
                     "website_cache", "jobs", "memory", "projects", "project_log"]

    def export_all(self):
        out = {"pocketpal_backup": 1,
               "created": datetime.now().isoformat(), "tables": {}}
        for t in self.BACKUP_TABLES:
            cur = self.conn.execute("SELECT * FROM " + t)
            cols = [d[0] for d in cur.description]
            out["tables"][t] = {"cols": cols,
                                "rows": [list(r) for r in cur.fetchall()]}
        return out

    def import_all(self, data):
        if not isinstance(data, dict) or data.get("pocketpal_backup") != 1:
            raise ValueError("not a Pocket Pal backup")
        total = 0
        for t in self.BACKUP_TABLES:
            blob = data.get("tables", {}).get(t)
            if not blob:
                continue
            real = [r[1] for r in self.conn.execute("PRAGMA table_info(" + t + ")")]
            cols = blob["cols"]
            if any(c not in real for c in cols):
                raise ValueError("backup columns do not match: " + t)
            self.conn.execute("DELETE FROM " + t)
            q = ("INSERT INTO " + t + " (" + ",".join(cols) + ") VALUES ("
                 + ",".join("?" * len(cols)) + ")")
            for row in blob["rows"]:
                self.conn.execute(q, row)
                total += 1
        self.conn.commit()
        return total

    def add_project(self, name, goal):
        cur = self.conn.execute(
            "INSERT INTO projects(name, goal, status, created_at) VALUES (?, ?, ?, ?)",
            (name, goal, "new", datetime.now().isoformat()))
        self.conn.commit()
        return cur.lastrowid

    def projects(self):
        return self.conn.execute(
            "SELECT id, name, goal, status FROM projects ORDER BY id DESC").fetchall()

    def get_project(self, pid):
        return self.conn.execute(
            "SELECT id, name, goal, status FROM projects WHERE id=?", (pid,)).fetchone()

    def delete_project(self, pid):
        self.conn.execute("DELETE FROM project_log WHERE project_id=?", (pid,))
        self.conn.execute("DELETE FROM projects WHERE id=?", (pid,))
        self.conn.commit()

    def set_pstatus(self, pid, status):
        self.conn.execute("UPDATE projects SET status=? WHERE id=?", (status, pid))
        self.conn.commit()

    def add_plog(self, pid, kind, text):
        self.conn.execute(
            "INSERT INTO project_log(project_id, kind, text, created_at) VALUES (?, ?, ?, ?)",
            (pid, kind, text, datetime.now().isoformat()))
        self.conn.commit()

    def plog(self, pid, n=20):
        rows = self.conn.execute(
            "SELECT created_at, kind, text FROM project_log WHERE project_id=? "
            "ORDER BY id DESC LIMIT ?", (pid, n)).fetchall()
        return list(reversed(rows))

    def notes_search(self, query, limit=3):
        stop = {"what", "with", "that", "this", "have", "from", "your", "about",
                "tell", "please", "would", "could", "should", "there", "their",
                "when", "where", "which", "does", "into", "make", "need", "want"}
        words = [w for w in re.findall(r"[a-z]{4,}", query.lower()) if w not in stop]
        if not words:
            return []
        rows = self.conn.execute(
            "SELECT text FROM project_log WHERE kind='pal' ORDER BY id DESC LIMIT 300").fetchall()
        scored = []
        for (t,) in rows:
            low = t.lower()
            sc = sum(1 for w in set(words) if w in low)
            if sc:
                scored.append((sc, t))
        scored.sort(key=lambda x: -x[0])
        return [t[:700] for sc, t in scored[:limit]]

    def recall_project(self, pid, window, query, k=3, cut=400):
        # older project notes (not in the visible log window) that match the goal
        shown = set(t for _, _, t in self.plog(pid, window))
        rows = self.conn.execute(
            "SELECT text FROM project_log WHERE project_id=? AND kind='pal' "
            "ORDER BY id DESC LIMIT 400", (pid,)).fetchall()
        stop = {"what", "with", "that", "this", "have", "from", "your", "about", "project",
                "goal", "note", "step", "then", "next", "make", "need", "want", "will"}
        words = set(w for w in re.findall(r"[a-z]{4,}", (query or "").lower()) if w not in stop)
        scored = []
        for i, (t,) in enumerate(rows):
            if t in shown:
                continue
            low = t.lower()
            scored.append((sum(1 for w in words if w in low), -i, t))
        scored.sort(reverse=True)
        hit = [x for x in scored if x[0] > 0][:k]
        if not hit:
            hit = scored[:2]
        return [x[2][:cut] for x in hit]

    def forget_last(self):
        row = self.conn.execute("SELECT id, fact FROM memory ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return ""
        self.conn.execute("DELETE FROM memory WHERE id=?", (row[0],))
        self.conn.commit()
        return row[1]

    def task_rows(self, n=30):
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(tasks)")]
        col = None
        for c in ("task", "title", "name", "description", "text"):
            if c in cols:
                col = c
                break
        if col is None:
            col = cols[1] if len(cols) > 1 else cols[0]
        rows = self.conn.execute(
            "SELECT id, " + col + " FROM tasks ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return [(r[0], str(r[1])) for r in rows]

    def del_task(self, tid):
        self.conn.execute("DELETE FROM tasks WHERE id=?", (tid,))
        self.conn.commit()

    def close(self):
        self.conn.close()


class BusinessBackend:

    def __init__(self, db):
        self.db = db

    def daily_report(self):

        report = (
            "Daily Business Report\n\n"
            f"Date: {datetime.now()}\n"
            f"Financial total: "
            f"${self.db.finance_total():.2f}\n"
            f"Tasks: {self.db.task_count()}\n"
        )

        self.db.queue_email(
            "YOUR_EMAIL_HERE",
            "Daily Business Report",
            report
        )

        self.db.log(
            "Daily report created and queued."
        )

    def check_website(self, url):

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent":
                    "BusinessDashboard/0.1"
                }
            )

            with urllib.request.urlopen(
                request,
                timeout=10
            ) as response:

                data = response.read()

            self.db.cache_website(
                url,
                len(data)
            )

            self.db.log(
                f"Website checked successfully: "
                f"{len(data)} bytes."
            )

            return True

        except Exception as e:

            self.db.log(
                f"Website check failed: {e}"
            )

            return False


class BusinessDashboard(App):

    def build(self):
        self.title = "RAMBO AI"
        Window.softinput_mode = "below_target"
        Window.clearcolor = BG
        os.makedirs(self.user_data_dir, exist_ok=True)
        CRASH_PATH[0] = os.path.join(self.user_data_dir, "crash.log")
        self.cfg_path = os.path.join(self.user_data_dir, "settings.json")
        self.key_path = os.path.join(self.user_data_dir, "gemini.key")
        _GROQ["path"] = os.path.join(self.user_data_dir, "groq.key")
        self.load_settings()
        self.db = Database(os.path.join(self.user_data_dir, "business.db"))
        self.backend = BusinessBackend(self.db)
        self.hist = []
        self.cool_until = 0
        self.convo_active = False
        self.tts = None
        self.tts_ok = False
        self.thinking = None
        self.cur_proj = None
        self.voice_target = None
        self.auto_on = False
        self.auto_steps = 0

        root = BoxLayout(orientation="vertical", padding=6, spacing=6)
        self.body = BoxLayout()
        root.add_widget(self.body)
        self.flash_lbl = Label(text="Ready.", color=GREEN, font_size="13sp",
                               size_hint_y=None, height=_dp(24), shorten=True,
                               halign="center", valign="middle")
        self.flash_lbl.bind(size=lambda w, v: setattr(w, "text_size", v))
        root.add_widget(self.flash_lbl)
        bar = BoxLayout(size_hint_y=None, height=_dp(56), spacing=6)
        self.tab_btns = {}
        self.tab_views = {}
        builders = [("TALK", self.build_chat), ("PHONE", self.build_phone),
                    ("LOOKUP", self.build_lookup), ("PROJECT", self.build_projects),
                    ("TASKS", self.build_tasks), ("MORE", self.build_more),
                    ("TOOLS", self.build_tools)]
        for name, fn in builders:
            self.tab_views[name] = fn()
        for name, label, col in (("TALK", "CHAT", CYAN),
                                 ("PROJECT", "PROJECT", MAGENTA),
                                 ("TOOLS", "TOOLS", GREEN)):
            b = NeonButton(glow=col, text=label, font_size="14sp")
            b.bind(on_press=lambda inst, n=name: self.switch(n))
            self.tab_btns[name] = b
            bar.add_widget(b)
        root.add_widget(bar)
        self.switch("TALK")
        self.load_chat()
        self.refresh()
        Clock.schedule_interval(lambda dt: self.refresh(), 5)
        return root

    # ---------- settings ----------

    def load_settings(self):
        self.cfg = {"talk": True, "convo": False, "auto": False}
        try:
            with open(self.cfg_path) as f:
                self.cfg.update(json.load(f))
        except Exception:
            pass

    def save_settings(self):
        try:
            with open(self.cfg_path, "w") as f:
                json.dump(self.cfg, f)
        except Exception:
            pass

    def upd_toggles(self):
        def t(b, name, k):
            on = bool(self.cfg.get(k))
            b.text = name + ": " + ("ON" if on else "OFF")
            b.color = GREEN if on else (0.6, 0.6, 0.75, 1)
        t(self.b_talk, "Talk back", "talk")
        t(self.b_convo, "Conversation", "convo")
        t(self.b_auto, "Auto-listen", "auto")

    def tog(self, key):
        self.cfg[key] = not self.cfg.get(key, False)
        if key == "convo" and not self.cfg[key]:
            self.convo_active = False
        self.save_settings()
        self.upd_toggles()

    # ---------- layout helpers ----------

    def switch(self, name):
        self.cur_tab = name
        self.body.clear_widgets()
        self.body.add_widget(self.tab_views[name])
        grp = "TOOLS" if name in ("PHONE", "LOOKUP", "TASKS", "MORE", "TOOLS") else name
        for n, b in self.tab_btns.items():
            b.set_active(n == grp)

    def _scroll(self):
        sv = ScrollView()
        c = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None, padding=[2, 2])
        c.bind(minimum_height=c.setter("height"))
        sv.add_widget(c)
        return sv, c

    def _head(self, c, t, col=CYAN):
        c.add_widget(Label(text=t, color=col, bold=True, font_size="16sp",
                           size_hint_y=None, height=36))

    def _btn(self, c, t, cb, col=CYAN, h=48):
        b = NeonButton(glow=col, text=t, size_hint_y=None, height=_dp(h))
        b.bind(on_press=self._wrap(cb))
        c.add_widget(b)
        return b

    def _row(self, c, inp, label, cb, col=CYAN):
        r = BoxLayout(size_hint_y=None, height=_dp(50), spacing=6)
        r.add_widget(inp)
        b = NeonButton(glow=col, text=label, size_hint_x=0.32)
        b.bind(on_press=self._wrap(cb))
        r.add_widget(b)
        c.add_widget(r)

    # ---------- tabs ----------

    def build_chat(self):
        v = BoxLayout(orientation="vertical", spacing=6)
        self.chat_view = v

        top = BoxLayout(size_hint_y=None, height=_dp(46), spacing=6)
        title = Label(text="RAMBO AI", color=TXT, bold=True, font_size="19sp",
                      halign="left", valign="middle", padding=[10, 0])
        title.bind(size=lambda w, sz: setattr(w, "text_size", sz))
        top.add_widget(title)
        newb = NeonButton(glow=MAGENTA, text="NEW CHAT", size_hint_x=0.34,
                          font_size="12sp")
        newb.bind(on_press=lambda *a: self.new_chat())
        cpb = NeonButton(glow=GREEN, text="COPY", size_hint_x=0.22, font_size="12sp")
        svb = NeonButton(glow=AMBER, text="SAVE", size_hint_x=0.2, font_size="12sp")
        svb.bind(on_release=lambda *a: self.save_last_mem())
        Clock.schedule_once(lambda dt: cpb.parent.add_widget(svb) if cpb.parent else None, 0.5)
        cpb.bind(on_press=lambda *a: self.copy_chat())
        top.add_widget(cpb)
        top.add_widget(newb)
        v.add_widget(top)

        self.chat_scroll = ScrollView()
        self.chat_box = BoxLayout(orientation="vertical", size_hint_y=None,
                                  spacing=10, padding=[6, 6])
        self.chat_box.bind(minimum_height=self.chat_box.setter("height"))
        self.chat_scroll.add_widget(self.chat_box)
        v.add_widget(self.chat_scroll)

        self.chips_row = BoxLayout(size_hint_y=None, height=_dp(42), spacing=6)
        for label, cmd in (("YouTube", "open youtube"),
                           ("10 min timer", "set a timer for 10 minutes"),
                           ("My tasks", "show my tasks"),
                           ("APK", "apk pick"),
                           ("PROG", "prog pick"), ("DOC", "doc pick")):
            cb = NeonButton(glow=CYAN, text=label, font_size="12sp")
            cb.bind(on_press=lambda inst, c=cmd: self.chip_go(c))
            self.chips_row.add_widget(cb)
        v.add_widget(self.chips_row)

        pill = BoxLayout(size_hint_y=None, height=_dp(60), spacing=4,
                         padding=[14, 4, 4, 4])
        with pill.canvas.before:
            Color(0.09, 0.11, 0.19, 1)
            pr = RoundedRectangle(pos=pill.pos, size=pill.size, radius=[28])
            Color(0.0, 0.9, 1.0, 0.35)
            pl = Line(rounded_rectangle=(pill.x, pill.y, pill.width, pill.height, 28),
                      width=1.2)

        def _pill(*a):
            pr.pos = pill.pos
            pr.size = pill.size
            pl.rounded_rectangle = (pill.x, pill.y, pill.width, pill.height, 28)

        pill.bind(pos=_pill, size=_pill)
        self.msg_input = TextInput(input_type="text", keyboard_suggestions=True,
                                   hint_text="Message RAMBO AI",
                                   multiline=False, font_size="18sp",
                                   background_color=(0, 0, 0, 0),
                                   foreground_color=TXT, cursor_color=CYAN,
                                   hint_text_color=(0.4, 0.55, 0.65, 1),
                                   padding=[2, 15, 2, 0])
        self.msg_input.bind(on_text_validate=self.on_send)
        pill.add_widget(self.msg_input)
        plus = NeonButton(glow=CYAN, text="+", size_hint=(None, 1),
                          width=_dp(54), font_size="26sp")
        plus.bind(on_press=self.on_attach)
        pill.add_widget(plus)
        mic = NeonButton(glow=GREEN, text="MIC", size_hint=(None, 1),
                         width=_dp(68), font_size="14sp")
        mic.bind(on_press=self.on_mic)
        pill.add_widget(mic)
        send = NeonButton(glow=CYAN, text="SEND", size_hint=(None, 1),
                          width=_dp(76), font_size="14sp")
        send.bind(on_press=self.on_send)
        pill.add_widget(send)
        v.add_widget(self._att_make_strip())
        v.add_widget(pill)
        return v

    def chip_go(self, cmd):
        self.convo_active = False
        self.handle(cmd, False)

    def copy_chat(self):
        try:
            from kivy.core.clipboard import Clipboard
            rows = self.db.recent_chat(40)
            out = []
            for role, text in rows:
                out.append(("You: " if role == "user" else "RAMBO AI: ") + str(text))
            if not out:
                self.flash("Nothing to copy yet")
                return
            Clipboard.copy("\n\n".join(out))
            self.flash("Copied the last %d messages. Paste them to Claude." % len(out))
        except Exception as e:
            self.err("copy chat", e)
            self.flash("Copy failed")

    def hide_chips(self):
        try:
            if self.chips_row.parent is not None:
                self.chips_row.parent.remove_widget(self.chips_row)
        except Exception:
            pass

    def save_last_mem(self, *a):  # SAVE_VISIBLE_V66
        def say(m):
            try:
                self.add_msg(m, False)
            except Exception:
                pass
            try:
                self.flash(m)
            except Exception:
                pass
        try:
            last = [t for r, t in self.hist if r == "model"]  # SAVE_REAL_V67
            txt = last[-1] if last else ""
            if txt.startswith(("Sent to", "SAVED", "SAVE")):
                txt = ""
            elif " replied:\n" in txt[:40]:
                txt = txt.split("\n", 1)[1]
            if not txt.strip():
                try:
                    from kivy.core.clipboard import Clipboard
                    txt = Clipboard.paste() or ""
                except Exception:
                    txt = ""
            txt = txt.strip()[:6000]
            if not txt:
                say("SAVE: nothing to save yet.")
                return
            self.db.add_memory(txt)
            n = len(self.db.memories(1000))
            say("SAVED to memory (%d characters). Memory now holds %d entries." % (len(txt), n))
        except Exception as e:
            self.err("save mem", e)
            say("SAVE FAILED: " + str(e)[:150])

    def new_chat(self):
        try:
            self.convo_active = False
            self.db.clear_chat()
            self.chat_box.clear_widgets()
            self.hist = []
            self.thinking = None
            if self.chips_row.parent is None:
                self.chat_view.add_widget(self.chips_row, index=1)
            self.add_msg("New chat. What can I do for you?", False)
        except Exception as e:
            self.err("new chat", e)

    def build_tools(self):
        sv, c = self._scroll()
        self._head(c, "VOICE", MAGENTA)
        row = BoxLayout(size_hint_y=None, height=_dp(50), spacing=6)
        self.b_talk = NeonButton(glow=MAGENTA, font_size="13sp")
        self.b_convo = NeonButton(glow=MAGENTA, font_size="13sp")
        self.b_auto = NeonButton(glow=MAGENTA, font_size="13sp")
        self.b_talk.bind(on_press=lambda *a: self.tog("talk"))
        self.b_convo.bind(on_press=lambda *a: self.tog("convo"))
        self.b_auto.bind(on_press=lambda *a: self.tog("auto"))
        for b in (self.b_talk, self.b_convo, self.b_auto):
            row.add_widget(b)
        c.add_widget(row)
        self.upd_toggles()
        self._head(c, "TOOLS", CYAN)
        for name, label, col in (("PHONE", "PHONE", GREEN),
                                 ("LOOKUP", "LOOKUP", AMBER),
                                 ("TASKS", "TASKS", GREEN),
                                 ("MORE", "MORE (key, tests, backup, log)", CYAN)):
            self._btn(c, label, lambda *a, n=name: self.switch(n), col, 56)
        return sv

    def phone_go(self, cmd):
        if cmd.strip() in ("timer", "alarm", "call", "text", "search"):
            self.phone_status.text = "Fill in the box first."
            self.flash("Fill in the box first.")
            return
        try:
            res = self.pa(cmd)
        except Exception as e:
            self.err("phone tab", e)
            res = "Error: " + str(e)[:100]
        self.phone_status.text = res
        self.flash(res)

    def build_phone(self):
        sv, c = self._scroll()
        self.phone_status = autosize(Label(text="Pick an app or action.", color=GREEN))
        c.add_widget(self.phone_status)

        self._head(c, "OPEN APP", GREEN)
        apps = [("YouTube", "youtube"), ("Gmail", "gmail"), ("Chrome", "chrome"),
                ("Maps", "maps"), ("Camera", "camera"), ("Settings", "settings"),
                ("TikTok", "tiktok"), ("Messages", "messages")]
        g = GridLayout(cols=2, spacing=8, size_hint_y=None, height=_dp(4 * 56 + 3 * 8))
        for label, app in apps:
            b = NeonButton(glow=GREEN, text=label)
            b.bind(on_press=lambda inst, a=app: self.phone_go("open " + a))
            g.add_widget(b)
        c.add_widget(g)

        self._head(c, "TIMER AND ALARM", AMBER)
        self.timer_in = mk_input("Minutes", input_filter="float")
        self._row(c, self.timer_in, "TIMER",
                  lambda *a: self.phone_go("timer " + self.timer_in.text.strip()), AMBER)
        self.alarm_in = mk_input("Time HH:MM (24h)")
        self._row(c, self.alarm_in, "ALARM",
                  lambda *a: self.phone_go("alarm " + self.alarm_in.text.strip()), AMBER)

        self._head(c, "CALL AND TEXT", CYAN)
        self.call_in = mk_input("Phone number")
        self._row(c, self.call_in, "CALL",
                  lambda *a: self.phone_go("call " + self.call_in.text.strip()), CYAN)
        self.sms_num = mk_input("Text to number")
        c.add_widget(self.sms_num)
        self.sms_msg = mk_input("Message")
        self._row(c, self.sms_msg, "TEXT",
                  lambda *a: self.phone_go("text " + self.sms_num.text.strip()
                                           + " " + self.sms_msg.text.strip()), CYAN)
        return sv

    def look_q(self):
        return self.look_in.text.strip()

    def look_search(self, kind):
        q = self.look_q()
        if not q:
            self.flash("Type your question in the box first.")
            return
        if kind == "web":
            self.phone_go("search " + q)
        elif kind == "yt":
            self.phone_go("open https://www.youtube.com/results?search_query=" + quote(q))
        elif kind == "ai":
            self.look_in.text = ""
            self.switch("TALK")
            self.handle("ask " + q, False)

    def build_lookup(self):
        sv, c = self._scroll()
        self._head(c, "LOOK UP", AMBER)
        self.look_in = mk_input("What do you want to find out?", height=56)
        c.add_widget(self.look_in)
        self._btn(c, "ASK AI (Gemini)", lambda *a: self.look_search("ai"), MAGENTA, 56)
        self._btn(c, "SEARCH THE WEB", lambda *a: self.look_search("web"), AMBER, 56)
        self._btn(c, "SEARCH YOUTUBE", lambda *a: self.look_search("yt"), GREEN, 56)
        self._head(c, "WEBSITE CHECK", CYAN)
        self.website_url = mk_input("Website URL")
        c.add_widget(self.website_url)
        self._btn(c, "CHECK WEBSITE", self.check_website, CYAN)
        return sv

    def build_tasks(self):
        v = BoxLayout(orientation="vertical", spacing=6)
        self.dashboard = Label(text="Loading...", color=CYAN, bold=True,
                               size_hint_y=None, height=70)
        v.add_widget(self.dashboard)
        sv, c = self._scroll()
        self._head(c, "TASKS", MAGENTA)
        self.task_input = mk_input("Enter task")
        c.add_widget(self.task_input)
        self._btn(c, "ADD TASK", self.add_task_ref, MAGENTA)
        self._head(c, "YOUR TASKS  (RUN = auto work on it)", MAGENTA)
        self.task_list = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None)
        self.task_list.bind(minimum_height=self.task_list.setter("height"))
        c.add_widget(self.task_list)
        self._task_sig = None
        Clock.schedule_interval(lambda dt: self.sync_tasks(), 3)
        Clock.schedule_once(lambda dt: self.sync_tasks(True), 0.5)
        self._head(c, "FINANCES", GREEN)
        self.finance_description = mk_input("Description")
        c.add_widget(self.finance_description)
        self.finance_amount = mk_input("Amount", input_filter="float")
        c.add_widget(self.finance_amount)
        self.finance_category = mk_input("Category")
        c.add_widget(self.finance_category)
        self._btn(c, "ADD FINANCE", self.add_finance, GREEN)
        v.add_widget(sv)
        return v

    def build_more(self):
        sv, c = self._scroll()
        self._head(c, "GEMINI KEY", MAGENTA)
        self.key_in = mk_input("Paste Gemini key here", password=True)
        self._row(c, self.key_in, "SAVE", self.save_key, MAGENTA)
        self.key_state = autosize(Label(
            text="Key: SAVED" if os.path.exists(self.key_path) else "Key: NOT saved yet",
            color=TXT))
        c.add_widget(self.key_state)
        self._head(c, "APP UPDATE", AMBER)
        self.gh_in = mk_input("GitHub token (paste once)", password=True)
        self._row(c, self.gh_in, "SAVE", self.save_gh_token, AMBER)
        self._btn(c, "CHECK + INSTALL UPDATE", self.check_update, AMBER, 56)
        self.upd_out = autosize(Label(text="Installed: " + self._cur_ver(), color=TXT))
        c.add_widget(self.upd_out)
        self._head(c, "APP UPDATE", AMBER)
        self.gh_in = mk_input("GitHub token (paste once)", password=True)
        self._row(c, self.gh_in, "SAVE", self.save_gh_token, AMBER)
        self._btn(c, "CHECK + INSTALL UPDATE", self.check_update, AMBER, 56)
        import updater
        self.upd_out = autosize(Label(text="Installed: " + updater.cur_ver(), color=TXT))
        c.add_widget(self.upd_out)
        self._head(c, "SELF TEST", GREEN)
        self._btn(c, "TEST EVERYTHING", self.run_tests_btn, GREEN, 56)
        self._btn(c, "TEST GEMINI", self.test_gemini, MAGENTA)
        self.test_out = autosize(Label(text="Tap TEST EVERYTHING.", color=TXT))
        c.add_widget(self.test_out)
        self._head(c, "GMAIL", CYAN)
        self.email_to = mk_input("Recipient email")
        c.add_widget(self.email_to)
        self.email_subject = mk_input("Subject")
        c.add_widget(self.email_subject)
        self.email_body = mk_input("Email message", multiline=True, height=120)
        c.add_widget(self.email_body)
        self._btn(c, "QUEUE EMAIL", self.queue_email, CYAN)
        self._btn(c, "CREATE DAILY REPORT", self.daily_report, CYAN)

        self._head(c, "YOUTUBE", GREEN)
        self.youtube_url = mk_input("Video URL")
        c.add_widget(self.youtube_url)
        self.youtube_comment = mk_input("Comment", multiline=True, height=100)
        c.add_widget(self.youtube_comment)
        self._btn(c, "QUEUE COMMENT", self.queue_youtube, GREEN)

        self._head(c, "BACKUP", AMBER)
        self._btn(c, "BACKUP (share / copy)", lambda *a: self.handle("backup", False), AMBER)
        self._btn(c, "RESTORE (from clipboard)", lambda *a: self.handle("restore", False), AMBER)

        self._head(c, "ACTIVITY LOG", MAGENTA)
        self.log_output = autosize(Label(text="Ready.", color=TXT))
        c.add_widget(self.log_output)
        return sv

    # ---------- in-app updater ----------

    def _gh_file(self):
        return os.path.join(os.path.dirname(self.key_path) or ".", "gh_token.txt")

    def _cur_ver(self):
        try:
            from jnius import autoclass
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            return str(act.getPackageManager().getPackageInfo(
                act.getPackageName(), 0).versionName)
        except Exception:
            return "unknown"

    def upd_set(self, text):
        Clock.schedule_once(lambda dt: setattr(self.upd_out, "text", text), 0)

    def save_gh_token(self, *a):
        try:
            t = self.gh_in.text.strip()
            if not t:
                self.upd_set("Paste a GitHub token first.")
                return
            with open(self._gh_file(), "w", encoding="utf-8") as f:
                f.write(t)
            self.gh_in.text = ""
            self.upd_set("GitHub token SAVED. Tap CHECK + INSTALL UPDATE.")
        except Exception as e:
            self.err("save token", e)

    def check_update(self, *a):
        import threading
        if not os.path.exists(self._gh_file()):
            self.upd_set("Save a GitHub token first.")
            return
        self.upd_set("Checking GitHub...")
        threading.Thread(target=self._update_worker, daemon=True).start()

    def _update_worker(self):
        try:
            import io
            import re
            import zipfile
            import urllib.error
            import urllib.request
            tok = open(self._gh_file(), encoding="utf-8").read().strip()
            repo = "Rambo602/BusinessDashboard"
            hdr = {"Authorization": "Bearer " + tok,
                   "Accept": "application/vnd.github+json",
                   "User-Agent": "rambo-ai"}

            def get(url, h, timeout):
                return urllib.request.urlopen(
                    urllib.request.Request(url, headers=h), timeout=timeout)

            with get("https://api.github.com/repos/%s/actions/artifacts"
                     "?per_page=30" % repo, hdr, 30) as r:
                arts = json.loads(r.read().decode())["artifacts"]
            arts = [x for x in arts if not x.get("expired")
                    and "apk" in x["name"].lower()]
            if not arts:
                self.upd_set("No APK build found on GitHub.")
                return
            art = sorted(arts, key=lambda x: x.get("created_at", ""), reverse=True)[0]
            self.upd_set("Downloading newest build...")

            class NoRedir(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **k):
                    return None

            op = urllib.request.build_opener(NoRedir)
            loc = None
            data = None
            try:
                data = op.open(urllib.request.Request(
                    art["archive_download_url"], headers=hdr), timeout=30).read()
            except urllib.error.HTTPError as e:
                if e.code in (301, 302, 303, 307, 308):
                    loc = e.headers["Location"]
                else:
                    raise
            if loc:
                with get(loc, {"User-Agent": "rambo-ai"}, 300) as r:
                    data = r.read()
            z = zipfile.ZipFile(io.BytesIO(data))
            names = [n for n in z.namelist() if n.endswith(".apk")]
            if not names:
                self.upd_set("Build zip has no APK inside.")
                return
            name = names[0]
            m = re.search(r"-(\d+(?:\.\d+)+)-", os.path.basename(name))
            if not m:
                self.upd_set("Cannot read version from " + name)
                return
            new = tuple(int(x) for x in m.group(1).split("."))
            cur_s = self._cur_ver()
            try:
                cur = tuple(int(x) for x in cur_s.split("."))
            except Exception:
                cur = (0,)
            if new <= cur:
                self.upd_set("Up to date. Installed %s, latest %s." % (cur_s, m.group(1)))
                return
            self.upd_set("Opening installer for %s..." % m.group(1))
            self._install_apk(z.read(name), os.path.basename(name))
        except Exception as e:
            self.upd_set("Update failed: %s" % e)

    def _install_apk(self, apk, fname):
        from jnius import autoclass
        PA = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        ContentValues = autoclass("android.content.ContentValues")
        Downloads = autoclass("android.provider.MediaStore$Downloads")
        act = PA.mActivity
        mime = "application/vnd.android.package-archive"
        cr = act.getContentResolver()
        cv = ContentValues()
        cv.put("_display_name", fname)
        cv.put("mime_type", mime)
        cv.put("relative_path", "Download")
        uri = cr.insert(Downloads.EXTERNAL_CONTENT_URI, cv)
        out = cr.openOutputStream(uri)
        step = 1 << 20
        for i in range(0, len(apk), step):
            chunk = apk[i:i + step]
            out.write(chunk, 0, len(chunk))
        out.close()
        it = Intent(Intent.ACTION_VIEW)
        it.setDataAndType(uri, mime)
        it.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                    | Intent.FLAG_ACTIVITY_NEW_TASK)
        act.startActivity(it)
        self.upd_set("Installer opened. Tap Update.")

    def _gh_file(self):
        return os.path.join(os.path.dirname(self.key_path) or ".", "gh_token.txt")

    def upd_set(self, t):
        Clock.schedule_once(lambda dt: setattr(self.upd_out, "text", t), 0)

    def save_gh_token(self, *a):
        t = self.gh_in.text.strip()
        if t:
            open(self._gh_file(), "w").write(t)
            self.gh_in.text = ""
        self.upd_set("Token SAVED." if t else "Paste a token first.")

    def check_update(self, *a):
        import threading, updater
        if not os.path.exists(self._gh_file()):
            return self.upd_set("Save a GitHub token first.")
        threading.Thread(target=updater.run, args=(self._gh_file(), self.upd_set),
                         daemon=True).start()

    # ---------- projects and auto run ----------

    def build_projects(self):
        sv, c = self._scroll()
        self.proj_sv = sv
        _v69_bar = None  # PROJ_LAYOUT_V69
        try:
            _v69_bar = self._v69_page(c)
        except Exception as e:
            self.err("v69 page", e)
            try:
                c.clear_widgets()
            except Exception:
                pass
            self._v69_old_page(c)
        self.refresh_projects()
        Clock.schedule_interval(lambda dt: self.update_proj_view(), 3)
        if _v69_bar is not None:
            try:
                _v69_box = BoxLayout(orientation="vertical")
                _v69_box.add_widget(sv)
                try:
                    _v69_box.add_widget(_v69_bar)
                except Exception:
                    _v69_box.remove_widget(sv)
                    raise
                return _v69_box
            except Exception as e:
                self.err("v69 box", e)
        return sv

    def _v68_old_create(self, c):
        self._btn(c, "SPEAK PROJECT (name + goal)", self.speak_project, GREEN, 56)
        self._btn(c, "CREATE PROJECT", self.new_project, MAGENTA)
        self._btn(c, "CREATE AND AUTO RUN", self.create_run, GREEN)

    def _v68_old_ctl(self, c):
        self._btn(c, "SEND ANSWER", self.add_note, CYAN, 56)
        self._btn(c, "SPEAK ANSWER (MIC)", self.speak_note, GREEN)
        self._btn(c, "START AUTO RUN", self.auto_start, GREEN, 56)
        self._btn(c, "PAUSE", lambda *a: self.auto_stop("Paused."), AMBER)
        self._btn(c, "MARK DONE", self.mark_done, MAGENTA)
        self._btn(c, "DELETE PROJECT (tap twice)", self.proj_delete, AMBER)
        self._head(c, "WHAT TO DO WITH THE RESULT", GREEN)
        self._btn(c, "SHARE RESULT (Claude, ChatGPT, Grok, Gemini...)", self.proj_share2, CYAN, 56)
        self._btn(c, "SEND TO CLAUDE (brings the reply back)", lambda *a: self.proj_to_app("claude"), CYAN, 56)
        self._btn(c, "SEND TO CHATGPT", lambda *a: self.proj_to_app("chatgpt"), GREEN)
        self._btn(c, "SAVE PDF", self.proj_pdf, GREEN)
        self._btn(c, "SAVE TEXT", self.proj_txt, GREEN)
        self._btn(c, "COPY RESULT", self.proj_copy, CYAN)
        self._btn(c, "SAVE TO MEMORY", self.proj_mem, AMBER)
        self._btn(c, "TIDY WITH GEMMA (clean summary)", self.proj_tidy, MAGENTA, 56)

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

    def _v69_page(self, c):
        self.proj_name = mk_input("Project name")
        self.proj_goal = mk_input("Goal: what should it build or do?", multiline=True, height=100)
        nb = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None, height=0, opacity=0)
        nb.disabled = True
        nb.add_widget(self.proj_name)
        nb.add_widget(self.proj_goal)
        nb.add_widget(self._v68_row([("SPEAK", self.speak_project, GREEN),
                                     ("CREATE", self.new_project, MAGENTA),
                                     ("CREATE+RUN", self.create_run, GREEN)]))
        top = self._v68_btn("+ NEW PROJECT", lambda *a: None, MAGENTA)
        top.size_hint_y = None
        top.height = 72  # BIGBTN_V71
        top.font_size = "18sp"
        def tog(*a):
            o = nb.height == 0
            if o:
                nb.height = sum(w.height for w in nb.children) + 6 * (len(nb.children) - 1)
            else:
                nb.height = 0
            nb.opacity = 1 if o else 0
            nb.disabled = not o
        top.bind(on_release=self._v72_newproj)
        c.add_widget(top)
        c.add_widget(nb)
        self.proj_list = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None)
        self.proj_list.bind(minimum_height=self.proj_list.setter("height"))
        c.add_widget(self.proj_list)
        self.proj_list.bind(children=lambda *a: Clock.schedule_once(self._v71_big, 0))
        Clock.schedule_once(self._v71_big, 0.3)
        self.proj_title = autosize(Label(text="None selected.", color=TXT, bold=True))
        c.add_widget(self.proj_title)
        self.proj_status = autosize(Label(text="", color=GREEN))
        c.add_widget(self.proj_status)
        self.proj_log = autosize(Label(text="", color=TXT))
        c.add_widget(self.proj_log)
        self.proj_note = mk_input("Message this project", multiline=True, height=56)
        mic = NeonButton(glow=GREEN, text="MIC", size_hint_x=None, width=_dp(70), font_size="16sp")
        mic.bind(on_release=self.speak_note)
        snd = NeonButton(glow=CYAN, text="SEND", size_hint_x=None, width=_dp(80), font_size="16sp")
        snd.bind(on_release=self.add_note)
        r1 = BoxLayout(orientation="horizontal", spacing=6, size_hint_y=None, height=_dp(56))
        r1.add_widget(self.proj_note)
        r1.add_widget(mic)
        r1.add_widget(snd)
        r2 = self._v68_row([("RUN", self.auto_start, GREEN),
                            ("PAUSE", lambda *a: self.auto_stop("Paused."), AMBER),
                            ("CLAUDE", lambda *a: self.proj_to_app("claude"), CYAN),
                            ("MENU", self._v69_menu, MAGENTA)])
        bar = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None, height=_dp(56) + 68, padding=[0, 6, 0, 0])
        bar.add_widget(r1)
        bar.add_widget(r2)
        return bar

    def _v71_big(self, *a):
        try:
            for w in list(self.proj_list.children):
                w.size_hint_y = None
                w.height = 68
                try:
                    w.font_size = "18sp"
                except Exception:
                    pass
        except Exception as e:
            self.err("v71 big", e)

    def _v69_menu(self, *a):
        from kivy.uix.modalview import ModalView
        items = [("DONE (mark finished)", self.mark_done, MAGENTA),
                 ("SAVE TO MEMORY", self.proj_mem, AMBER),
                 ("SHARE (any app)", self.proj_share2, CYAN),
                 ("SEND TO CHATGPT", lambda *x: self.proj_to_app("chatgpt"), GREEN),
                 ("SAVE PDF", self.proj_pdf, GREEN),
                 ("SAVE TEXT", self.proj_txt, GREEN),
                 ("COPY RESULT", self.proj_copy, CYAN),
                 ("TIDY WITH GEMMA", self.proj_tidy, MAGENTA),
                 ("DELETE (tap twice)", self.proj_delete, AMBER)]
        n = len(items)
        mv = ModalView(size_hint=(0.92, None), height=n * 56 + (n - 1) * 6 + 16)
        box = BoxLayout(orientation="vertical", spacing=6, padding=8)
        for t, cb, g in items:
            def go(inst, cb=cb, keep=t.startswith("DELETE")):
                if not keep:
                    mv.dismiss()
                cb(inst)
            bt = self._v68_btn(t, go, g)
            box.add_widget(bt)
        mv.add_widget(box)
        mv.open()

    def _v69_old_page(self, c):
        self._head(c, "NEW PROJECT", MAGENTA)
        self.proj_name = mk_input("Project name (business, game, workout...)")
        c.add_widget(self.proj_name)
        self.proj_goal = mk_input("Goal: what should it build or do?", multiline=True, height=100)
        c.add_widget(self.proj_goal)
        try:
            for _x in self._v68_create():
                c.add_widget(_x)
        except Exception as e:
            self.err("v68 create", e)
            self._v68_old_create(c)

        self._head(c, "YOUR PROJECTS (tap to open)", CYAN)
        self.proj_list = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None)
        self.proj_list.bind(minimum_height=self.proj_list.setter("height"))
        c.add_widget(self.proj_list)

        self._head(c, "SELECTED PROJECT", GREEN)
        self.proj_title = autosize(Label(text="None selected.", color=TXT, bold=True))
        c.add_widget(self.proj_title)
        self.proj_status = autosize(Label(text="", color=GREEN))
        c.add_widget(self.proj_status)

        self._head(c, "PROJECT LOG", AMBER)
        self.proj_log = autosize(Label(text="", color=TXT))
        c.add_widget(self.proj_log)
        self.proj_note = mk_input("Add a note, or answer its question", multiline=True, height=90)
        c.add_widget(self.proj_note)
        try:  # PROJ_LAYOUT_V68
            for _x in self._v68_ctl():
                c.add_widget(_x)
        except Exception as e:
            self.err("v68 ctl", e)
            self._v68_old_ctl(c)

    def _proj_export(self):
        if self.cur_proj is None:
            self.flash("Open a project first")
            return None, None
        p = self.db.get_project(self.cur_proj)
        rows = self.db.plog(self.cur_proj, 200)
        pal = [t for ts, k, t in rows if k == "pal"]
        summ = [t for t in pal if t.startswith("SUMMARY:")]
        body = summ[-1][8:].strip() if summ else "\n\n".join(pal)
        if not body:
            self.flash("Nothing to export yet")
            return None, None
        return p[1], "Goal: " + (p[2] or "") + "\n\n" + body

    def proj_share(self, *a):
        try:
            title, text = self._proj_export()
            if not text:
                return
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            PA = autoclass("org.kivy.android.PythonActivity")
            i = Intent(Intent.ACTION_SEND)
            i.setType("text/plain")
            i.putExtra(Intent.EXTRA_SUBJECT, title)
            i.putExtra(Intent.EXTRA_TEXT, (title + "\n\n" + text)[:100000])
            PA.mActivity.startActivity(Intent.createChooser(i, "Send to"))
        except Exception as e:
            self.err("share", e)
            self.flash("Share failed")

    def proj_share2(self, *a):
        try:
            title, text = self._proj_export()
            if not text:
                return
            from jnius import autoclass, cast
            Intent = autoclass("android.content.Intent")
            JString = autoclass("java.lang.String")
            PA = autoclass("org.kivy.android.PythonActivity")
            i = Intent()
            i.setAction(Intent.ACTION_SEND)
            i.setType("text/plain")
            i.putExtra(Intent.EXTRA_SUBJECT, JString(title))
            i.putExtra(Intent.EXTRA_TEXT, JString((title + "\n\n" + text)[:90000]))
            try:
                ch = Intent.createChooser(i, cast("java.lang.CharSequence", JString("Send to")))
            except Exception:
                ch = i
            PA.mActivity.startActivity(ch)
        except Exception as e:
            self.err("share", e)
            self.flash("Share failed: " + str(e)[:90])

    def _quick_time(self, text):
        from datetime import datetime, timedelta, timezone
        t = text.lower().strip().rstrip("?.! ")
        if re.match(r"^what day is it(?: today)?$", t):
            return datetime.now().strftime("Today is %A, %B %d, %Y")
        m = re.match(r"^what(?:'s| is)?\s+(?:the\s+)?(time|date)(?:\s+is\s+it)?(?:\s+(?:in|at)\s+(.+?))?(?:\s+(?:right\s+)?now|\s+today)?$", t)
        if not m:
            return None
        kind, place = m.group(1), (m.group(2) or "").strip()
        Z = {"italy": (1, "eu"), "rome": (1, "eu"), "france": (1, "eu"), "paris": (1, "eu"),
             "germany": (1, "eu"), "berlin": (1, "eu"), "spain": (1, "eu"), "madrid": (1, "eu"),
             "uk": (0, "eu"), "london": (0, "eu"), "england": (0, "eu"), "ireland": (0, "eu"),
             "japan": (9, None), "tokyo": (9, None), "china": (8, None), "beijing": (8, None),
             "india": (5.5, None), "dubai": (4, None), "moscow": (3, None), "russia": (3, None),
             "new york": (-5, "us"), "florida": (-5, "us"), "chicago": (-6, "us"), "texas": (-6, "us"),
             "denver": (-7, "us"), "los angeles": (-8, "us"), "california": (-8, "us"),
             "arizona": (-7, None), "phoenix": (-7, None), "hawaii": (-10, None), "mexico": (-6, None)}
        if not place or place in ("here", "my area", "my location"):
            d = datetime.now()
            return d.strftime("It is %I:%M %p on %A, %B %d, %Y").replace("is 0", "is ")
        place = re.sub(r"^(the|a)\s+", "", place)
        if place not in Z:
            return None
        std, rule = Z[place]
        u = datetime.now(timezone.utc)
        y = u.year
        dst = False
        if rule == "eu":
            def ls(mo):
                d = datetime(y, mo, 31, 1, tzinfo=timezone.utc)
                return d - timedelta(days=(d.weekday() + 1) % 7)
            dst = ls(3) <= u < ls(10)
        elif rule == "us":
            d1 = datetime(y, 3, 1)
            sec = 1 + (6 - d1.weekday()) % 7 + 7
            d2 = datetime(y, 11, 1)
            fs = 1 + (6 - d2.weekday()) % 7
            st = datetime(y, 3, sec, 2, tzinfo=timezone.utc) - timedelta(hours=std)
            en = datetime(y, 11, fs, 2, tzinfo=timezone.utc) - timedelta(hours=std + 1)
            dst = st <= u < en
        loc = u + timedelta(hours=std + (1 if dst else 0))
        s = loc.strftime("%I:%M %p on %A, %B %d, %Y").lstrip("0")
        return "In " + place.title() + " it is " + s + (" (daylight saving)" if dst else "")

    RB_APPS = {"claude": ("com.anthropic.claude", "Claude"),
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

    def proj_copy(self, *a):
        try:
            title, text = self._proj_export()
            if not text:
                return
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(title + "\n\n" + text)
            self.flash("Result copied")
        except Exception as e:
            self.err("copy result", e)

    def _save_bytes(self, name, data):
        try:
            from jnius import autoclass
            PA = autoclass("org.kivy.android.PythonActivity")
            CV = autoclass("android.content.ContentValues")
            MS = autoclass("android.provider.MediaStore$Downloads")
            cr = PA.mActivity.getContentResolver()
            cv = CV()
            cv.put("_display_name", name)
            cv.put("mime_type", "application/pdf" if name.endswith(".pdf") else "text/plain")
            cv.put("relative_path", "Download")
            uri = cr.insert(MS.EXTERNAL_CONTENT_URI, cv)
            o = cr.openOutputStream(uri)
            o.write(bytearray(data))
            o.close()
            return "Download/" + name
        except Exception as e:
            self.err("mediastore", e)
            return self._save_bytes_old(name, data)

    def _save_bytes_old(self, name, data):
        for d in ("/storage/emulated/0/Download", self.user_data_dir):
            try:
                path = os.path.join(d, name)
                with open(path, "wb") as f:
                    f.write(data)
                return path
            except Exception:
                continue
        return None

    def proj_txt(self, *a):
        title, text = self._proj_export()
        if not text:
            return
        nm = re.sub(r"[^A-Za-z0-9]+", "_", title)[:30] + "_" + datetime.now().strftime("%m%d_%H%M") + ".txt"
        path = self._save_bytes(nm, (title + "\n\n" + text).encode("utf-8"))
        self.flash("Saved: " + path if path else "Save failed")

    def proj_pdf(self, *a):
        try:
            title, text = self._proj_export()
            if not text:
                return
            nm = re.sub(r"[^A-Za-z0-9]+", "_", title)[:30] + "_" + datetime.now().strftime("%m%d_%H%M") + ".pdf"
            path = self._save_bytes(nm, self._mk_pdf(title, text))
            self.flash("Saved: " + path if path else "Save failed")
        except Exception as e:
            self.err("pdf", e)
            self.flash("PDF failed")

    def _mk_pdf(self, title, text):
        import textwrap
        lines = []
        for para in (title + "\n\n" + text).split("\n"):
            lines += textwrap.wrap(para, 88) or [""]
        pages = [lines[i:i + 52] for i in range(0, len(lines), 52)] or [[""]]
        n = len(pages)
        kids = " ".join("%d 0 R" % (4 + 2 * k) for k in range(n))
        objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
                ("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, n)).encode(),
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
        for k, pl in enumerate(pages):
            st = "BT /F1 11 Tf 14 TL 50 800 Td\n"
            for ln in pl:
                esc = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                st += "(" + esc + ") Tj T*\n"
            st += "ET"
            sb = st.encode("latin-1", "replace")
            objs.append(("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % (5 + 2 * k)).encode())
            objs.append(b"<< /Length %d >>\nstream\n" % len(sb) + sb + b"\nendstream")
        out = b"%PDF-1.4\n"
        offs = []
        for i, o in enumerate(objs):
            offs.append(len(out))
            out += b"%d 0 obj\n" % (i + 1) + o + b"\nendobj\n"
        xr = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        for o in offs:
            out += b"%010d 00000 n \n" % o
        out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xr)
        return out

    def proj_mem(self, *a):
        title, text = self._proj_export()
        if not text:
            return
        self.db.add_plog(self.cur_proj, "pal", "Saved result of " + title + ": " + text[:1500])
        self.flash("Saved to memory. Gemma can use it later")

    def proj_tidy(self, *a):
        title, text = self._proj_export()
        if not text:
            return
        self.flash("Gemma is tidying... (can take a minute)")
        pid = self.cur_proj
        threading.Thread(target=self._tidy_thread, args=(pid, title, text[:2500]), daemon=True).start()

    def _tidy_thread(self, pid, title, text):
        try:
            import urllib.request
            body = json.dumps({"messages": [
                {"role": "system", "content": "Rewrite the user's project notes as a clean, organised summary with short headings and bullet points. Keep every important fact. No preamble."},
                {"role": "user", "content": text}], "max_tokens": 600}).encode()
            rq = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
                                        data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(rq, timeout=240) as r:
                out = json.loads(r.read().decode())["choices"][0]["message"]["content"].strip()
            self.db.add_plog(pid, "pal", "SUMMARY: " + out)
            Clock.schedule_once(lambda dt: self.flash("Summary ready. Share or save it now"), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: self.flash("Tidy failed. Is the Gemma server running?"), 0)

    def proj_delete(self, *a):
        import time as _t
        if self.cur_proj is None:
            self.flash("Open a project first")
            return
        if _t.time() - getattr(self, "_del_t", 0) > 5:
            self._del_t = _t.time()
            self.flash("Tap DELETE PROJECT again to confirm")
            return
        self.db.delete_project(self.cur_proj)
        self.cur_proj = None
        self.auto_on = False
        self.proj_title.text = "None selected."
        self.proj_status.text = ""
        self.proj_log.text = ""
        self.refresh_projects()
        self.flash("Project deleted")

    def refresh_projects(self):
        self.proj_list.clear_widgets()
        rows = self.db.projects()
        if not rows:
            self.proj_list.add_widget(autosize(Label(text="No projects yet.", color=TXT)))
        for pid, name, goal, status in rows:
            b = NeonButton(glow=CYAN, text=name + "  [" + status + "]",
                           size_hint_y=None, height=48)
            b.bind(on_press=lambda inst, p=pid: self.select_project(p))
            self.proj_list.add_widget(b)

    def select_project(self, pid):
        self.cur_proj = pid
        self.auto_on = False
        self.update_proj_view()

    def new_project(self, *a):
        name = self.proj_name.text.strip()
        goal = self.proj_goal.text.strip()
        if not name:
            self.proj_status.text = "Give the project a name first."
            return
        pid = self.db.add_project(name, goal)
        self.db.add_plog(pid, "you", "Goal: " + (goal or "(none yet)"))
        self.proj_name.text = ""
        self.proj_goal.text = ""
        self.refresh_projects()
        self.select_project(pid)

    def update_proj_view(self):
        try:
            if self.cur_proj is None:
                return
            p = self.db.get_project(self.cur_proj)
            if not p:
                return
            self.proj_title.text = p[1] + "\nGoal: " + (p[2] or "(none)")
            self.proj_status.text = "Status: " + p[3] + ("  (auto run ON)" if self.auto_on else "") + (("\n" + self.auto_note) if getattr(self, "auto_note", "") and self.auto_on else "")
            lines = []
            for ts, kind, text in self.db.plog(self.cur_proj, 20):
                who = {"pal": "Pal", "you": "You", "run": "Ran", "ask": "ASKS"}.get(kind, kind)
                lines.append(ts[5:16].replace("T", " ") + " " + who + ": " + text)
            newlog = "\n\n".join(lines) if lines else "No log yet."
            changed = newlog != self.proj_log.text
            self.proj_log.text = newlog
            if changed:
                Clock.schedule_once(lambda dt: setattr(self.proj_sv, "scroll_y", 0), 0.4)
        except Exception as e:
            self.err("proj view", e)

    def add_note(self, *a):
        if self.cur_proj is None:
            return
        t = self.proj_note.text.strip()
        if not t:
            return
        self.proj_note.text = ""
        self.db.add_plog(self.cur_proj, "you", t)
        p = self.db.get_project(self.cur_proj)
        self.update_proj_view()
        if p and p[3] != "done":
            self.auto_start()

    def mark_done(self, *a):
        if self.cur_proj is None:
            return
        self.auto_on = False
        self.db.set_pstatus(self.cur_proj, "done")
        self.refresh_projects()
        self.update_proj_view()

    def notify(self, title, text):
        try:
            from jnius import autoclass
            PA = autoclass("org.kivy.android.PythonActivity")
            ctx = PA.mActivity
            Context = autoclass("android.content.Context")
            nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE)
            Builder = autoclass("android.app.Notification$Builder")
            if autoclass("android.os.Build$VERSION").SDK_INT >= 26:
                NC = autoclass("android.app.NotificationChannel")
                nm.createNotificationChannel(NC("pocketpal", "Pocket Pal", 3))
                b = Builder(ctx, "pocketpal")
            else:
                b = Builder(ctx)
            PI = autoclass("android.app.PendingIntent")
            i = ctx.getPackageManager().getLaunchIntentForPackage(ctx.getPackageName())
            pi = PI.getActivity(ctx, 0, i, PI.FLAG_IMMUTABLE | PI.FLAG_UPDATE_CURRENT)
            b.setSmallIcon(ctx.getApplicationInfo().icon)
            b.setContentTitle(title)
            b.setContentText(text[:200])
            b.setContentIntent(pi)
            b.setAutoCancel(True)
            nm.notify(1, b.build())
        except Exception as e:
            self.err("notify", e)

    def auto_start(self, *a):
        if self.cur_proj is None:
            self.proj_status.text = "Open a project first."
            return
        if self.auto_on:
            return
        self.auto_on = True
        self.auto_steps = 0
        self.auto_fail = 0
        self.auto_note = ""
        self.db.set_pstatus(self.cur_proj, "running")
        self.refresh_projects()
        self.update_proj_view()
        self.auto_gen = getattr(self, "auto_gen", 0) + 1
        try:  # V86_CLS
            from jnius import autoclass as _ac86
            self._v81_S = getattr(self, "_v81_S", None) or _ac86("org.rambo.acc.RamboAccService")
            if not bool(self._v81_S.isOn()):
                self.proj_status.text = "Accessibility is OFF. Type: acc settings, turn on RAMBO AI, then tap START AUTO RUN."
        except Exception as e:
            self.err("acc class", e)
        self.ka(True)
        threading.Thread(target=self._auto_loop,
                         args=(self.cur_proj, self.auto_gen), daemon=True).start()

    def auto_stop(self, why):
        was = self.auto_on
        self.auto_on = False
        if self.cur_proj is not None:
            p = self.db.get_project(self.cur_proj)
            if p and p[3] == "running":
                self.db.set_pstatus(self.cur_proj, "paused")
            if was:
                self.db.add_plog(self.cur_proj, "run", why)
        self.refresh_projects()
        self.update_proj_view()

    def auto_next(self, dt):
        if not self.auto_on or self.cur_proj is None:
            return
        if self.auto_steps >= 15:
            self.auto_stop("Reached 15 steps in this run. Tap AUTO RUN to keep going.")
            return
        wait = int(self.cool_until - time.time())
        if wait > 0:
            Clock.schedule_once(self.auto_next, wait + 2)
            return
        try:
            with open(self.key_path) as f:
                key = f.read().strip()
        except Exception:
            key = ""
        if not key:
            self.auto_stop("No Gemini key.")
            return
        pid = self.cur_proj
        p = self.db.get_project(pid)
        sysmsg = (
            "You are RAMBO AI, working on a long project for the user, one small step per turn. "
            "Project: " + p[1] + ". Goal: " + (p[2] or "not stated") + ". "
            "Each turn do ONE useful step: produce real content (plan, research notes, draft, "
            "checklist, design, schedule, copy) or give phone commands. Do not repeat earlier steps. "
            "Reply ONLY with JSON: {\"note\": \"what you did or produced\", \"commands\": [], "
            "\"question\": \"\", \"done\": false}. Put a question in \"question\" if you need the "
            "user's input or hit a problem (then leave commands empty). Set done true when the goal "
            "is finished. Allowed commands: open <app or website>, search <text>, timer <minutes>, "
            "alarm HH:MM, play <what to play on YouTube>. To play a song or video on YouTube use "
            "the play command by itself, do not open the app first. Max 3 commands. "
            "You cannot tap inside other apps."
        )
        facts = self.db.memories()
        if facts:
            sysmsg += " Known facts about the user: " + "; ".join(facts) + "."
        sysmsg += " Now: " + datetime.now().strftime("%A %B %d %Y %I:%M %p") + "."
        lines = []
        for ts, kind, text in self.db.plog(pid, 12):
            lines.append(kind.upper() + ": " + text[:500])
        prompt = "Project log so far:\n" + "\n".join(lines) + "\n\nDo the next step."
        payload = {
            "systemInstruction": {"parts": [{"text": sysmsg}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        body = json.dumps(payload).encode()
        threading.Thread(target=self._auto_thread, args=(key, body, pid), daemon=True).start()

    def _auto_thread(self, key, body, pid):
        code, raw, err = 0, "", ""
        try:
            code, raw = gemini_post(key, body)
        except Exception as e:
            err = str(e)
        Clock.schedule_once(lambda dt: self.on_auto(code, raw, err, pid), 0)

    def on_auto(self, code, raw, err, pid):
        if not self.auto_on or pid != self.cur_proj:
            return
        if err or code in (408, 500, 502, 503, 504):
            self.err("auto net", err or str(code))
            self.auto_fail = getattr(self, "auto_fail", 0) + 1
            wait = min(10 * (2 ** (self.auto_fail - 1)), 60)
            self.auto_note = ("No connection, retrying in %d s (try %d)." % (wait, self.auto_fail)
                              if err else "Gemini busy, retrying in %d s (try %d)." % (wait, self.auto_fail))
            if self.auto_fail == 8:
                self.notify("RAMBO AI: still offline", "Auto run keeps retrying. Open the app if you want to stop it.")
            self.update_proj_view()
            Clock.schedule_once(self.auto_next, wait)
            return
        if code == 429:
            self.cool_until = time.time() + 60
            self.db.add_plog(pid, "run", "Gemini free limit hit. Retrying in about a minute.")
            self.update_proj_view()
            Clock.schedule_once(self.auto_next, 62)
            return
        if code != 200:
            self.err("auto " + str(code), raw[:150])
            self.auto_stop("Gemini error " + str(code) + ": " + gem_msg(raw) + " Paused.")
            return
        self.auto_fail = 0
        self.auto_note = ""
        note, cmds, question, done = "", [], "", False
        try:
            txt = json.loads(raw)["candidates"][0]["content"]["parts"][0]["text"].strip()
            note = txt
            t2 = txt
            if t2.startswith("```"):
                t2 = re.sub(r"^```(?:json)?|```$", "", t2, flags=re.M).strip()
            d = json.loads(t2)
            if isinstance(d, dict):
                note = str(d.get("note", "")).strip()
                cmds = [str(x) for x in d.get("commands", [])][:3]
                question = str(d.get("question", "")).strip()
                done = bool(d.get("done", False))
        except Exception:
            pass
        if not note and not question and not cmds:
            self.auto_stop("Gemini gave no usable step. Paused.")
            return
        if note:
            self.db.add_plog(pid, "pal", note)
        self.auto_steps += 1
        for n, cm in enumerate(cmds):
            Clock.schedule_once(lambda dt, cm=cm: self._auto_cmd(pid, cm), 1 + 1.5 * n)
        pname = self.db.get_project(pid)[1]
        if question:
            self.db.add_plog(pid, "ask", question)
            self.db.set_pstatus(pid, "waiting")
            self.auto_on = False
            self.notify("RAMBO AI needs you: " + pname, question)
            self.speak(question)
        elif done:
            self.db.set_pstatus(pid, "done")
            self.auto_on = False
            self.notify("Project finished: " + pname, note[:150])
            self.speak("Project " + pname + " is finished.")
        else:
            Clock.schedule_once(self.auto_next, 25 + 1.5 * len(cmds))
        self.refresh_projects()
        self.update_proj_view()

    # ---------- Gemma first, Gemini only when needed ----------

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
                  "Answer clearly and completely. Follow the requested format exactly, including numbered steps. Put any code inside ``` blocks. If you are not sure, say so. ")
            if facts:
                sp += "Known facts about the user: " + "; ".join(facts) + ". "
            out = gemma_chat(sp, text, max_tokens=700)
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

    V72_SAFE = re.compile(r"^(~/reverse\.sh|ls|cat|head|tail|grep|pwd|echo|wc|find|df|du|uname|date|whoami|ps|id|which|stat|file|sort|uniq|unzip -p|strings|python -m py_compile|git (status|log|diff|branch)|pip list|pkg list-installed)\b")
    V72_BAD = re.compile(r"(\brm\s+-[a-z]*[rf]|\bdd\s+if|\bmkfs|\bshutdown|\breboot|:\(\)\s*\{|>\s*/dev/|\bchmod\s+-R\s+777|\b(curl|wget)\b[^|]*\|\s*(ba)?sh)", re.I)

    V77_ASK = re.compile(r"(\brm\b|\brmdir\b|\bmv\b|\bchmod\b|\bchown\b|\bkill(all)?\b|\bpkill\b|\bsudo\b|\bsu\b|\buninstall\b|\bpurge\b|\bpkg\s+(remove|autoclean)|\bgit\s+(push|reset|clean|checkout|rebase|restore)|\b(curl|wget|nc|ncat|ssh|scp|sftp|ftp|telnet|socat)\b|\btee\b|\bsed\s+-i|>|\btruncate\b|\bshred\b|\bcrontab\b|\bnohup\b|\beval\b|\bexec\b|\bam\s+start|\bpm\s+(clear|uninstall)|\.key\b|token|\.ssh|secret|password|termux\.properties|\.bashrc|\.env\b|os\.(remove|unlink|rmdir|system|popen|rename)|shutil|rmtree|subprocess|socket|urllib|requests\.|\bopen\([^)]*['\"][wa+])", re.I)

    def _v77_needs_ok(self, cmd):
        c = re.sub(r"2>&1|2>/dev/null|>/dev/null", "", cmd)
        return bool(self.V77_ASK.search(c))

    def _v72_is_safe(self, cmd):  # V76_SAFE
        if re.search(r"[<>`]", cmd) or re.search(r"\bfind\b.*-(exec|delete|ok)\b", cmd):
            return False
        flat = re.sub(r"\$\(|\)", " ; ", cmd)
        segs = re.split(r"&&|\|\||;|\|", flat)
        n = 0
        for sg in segs:
            sg = sg.strip()
            if not sg.strip("\"' "):
                continue
            n += 1
            if not (self.V72_SAFE.match(sg) or re.match(r"^(tr|cut|basename|dirname|printf|true)\b", sg)):
                return False
        return n > 0

    def _v72_status(self, msg):
        self._v78_msg = str(msg).replace("\n", " ")[:55]
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

    def _v72_run_termux(self, cmd, wait=60):  # V74_HTTP_EXEC
        tok = ""
        try:
            tp = os.path.join(self.user_data_dir, "exec.token")
            if os.path.exists(tp):
                tok = open(tp).read().strip()
        except Exception:
            tok = ""
        if not tok:
            return "No token yet. In Termux run: cat ~/.rambo_exec_token  then type here: setexec TOKEN"
        try:
            rq = urllib.request.Request("http://127.0.0.1:8765/run", data=cmd.encode("utf-8"),
                                        headers={"X-Token": tok}, method="POST")
            with urllib.request.urlopen(rq, timeout=wait + 10) as r:
                out = r.read().decode("utf-8", "replace")
            self._v73_diag = "http exec ok: " + cmd[:60]
            return out.strip()[-1500:] or "(no output)"
        except Exception as e:
            self._v73_diag = "http exec failed: " + str(e)[:120]
            return ("Exec server not reachable (" + str(e)[:80] + "). In Termux run: "
                    "nohup python ~/rambo_exec.py > ~/rambo_exec.log 2>&1 &")

    def _v72_run_termux_old(self, cmd, wait=60):
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
            _JS = autoclass("java.lang.String")  # V73_DIAG
            _AR = autoclass("java.lang.reflect.Array")
            _line = ("( " + cmd + " ) > $HOME/.rambo_out.txt 2>&1; echo \"$(date) exit=$?\" >> $HOME/rambo_term.log; "
                     "curl -s -m 20 --data-binary @$HOME/.rambo_out.txt http://127.0.0.1:%d/o" % port)
            _arr = _AR.newInstance(_JS, 2)
            _AR.set(_arr, 0, _JS("-c"))
            _AR.set(_arr, 1, _JS(_line))
            i.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", _arr)
            i.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home/BusinessDashboard")
            i.putExtra("com.termux.RUN_COMMAND_BACKGROUND", True)
            _cn = act.startService(i)
            self._v73_diag = "startService component=" + str(_cn) + " port=" + str(port) + " cmd=" + cmd[:60]
        except Exception as e:
            srv.server_close()
            return "TERMUX START FAILED: " + str(e)[:200]
        t0 = time.time()
        while box["out"] is None and time.time() - t0 < wait:
            srv.handle_request()
        srv.server_close()
        if box["out"] is None:
            return ("TIMEOUT: Termux did not call back. In Termux run: cat ~/rambo_term.log  "
                    "(a new line means the command ran). Then type: logs  and  termuxperm")
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
        _ev = getattr(self, "_v75_ev_ok", None)
        if _ev is not None and not _ev.is_set():
            self._v75_ok = True
            _ev.set()
            self.reply("Approved.")
            return
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
            if self._auto_risky(cm):
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
        else:
            self.acc_run("acc tapxy 975 2175")
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
            if cur and cur == prev and q[-40:] in cur and len(cur) - cur.rfind(q[-40:]) - len(q[-40:]) > 20:
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

    def _v73_logs(self):
        try:
            rows = self.db.errors(10)
        except Exception as e:
            rows = "could not read: " + str(e)[:100]
        d = getattr(self, "_v73_diag", "no Termux run yet this session")
        self.reply("LAST TERMUX RUN: " + d + "\nAPP ERRORS:\n" + str(rows)[:1400])

    def _v73_perm(self):
        P = "com.termux.permission.RUN_COMMAND"
        try:
            from jnius import autoclass
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            pi = act.getPackageManager().getPackageInfo(act.getPackageName(), 4096)
            rp = [str(x) for x in (pi.requestedPermissions or [])]
            declared = P in rp
            granted = act.checkSelfPermission(P) == 0
            msg = ("package " + str(act.getPackageName()) + "; declared in this APK: " + str(declared)
                   + "; granted: " + str(granted))
            if declared and not granted:
                JS = autoclass("java.lang.String")
                AR = autoclass("java.lang.reflect.Array")
                arr = AR.newInstance(JS, 1)
                AR.set(arr, 0, JS(P))
                act.requestPermissions(arr, 73)
                msg += ". Asked Android for it. Tap Allow if a prompt appears, then try: termux ls"
            elif not declared:
                msg += ". This APK does not contain the permission, so the build must be redone."
            self.reply(msg)
        except Exception as e:
            self.reply("termuxperm failed: " + str(e)[:200])

    def _v75_install(self):  # V75_HOLDCOPY
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
        try:  # V81_CACHE
            from jnius import autoclass as _ac81
            self._v81_S = _ac81("org.rambo.acc.RamboAccService")
        except Exception:
            pass
        self._v75_stop = False
        self._v75_ok = False
        self.reply("Goal started: " + goal[:200] + "\nType stop goal to cancel.")
        threading.Thread(target=self._v75_thread, args=(goal,), daemon=True).start()

    def _v75_plan(self, key, prompt):
        sysm = ("You are the planner for RAMBO AI, an Android assistant. The user gives a goal. Each turn reply with ONLY JSON: "
                "{\"say\": \"short status for the user\", \"action\": \"termux or claude or done\", \"arg\": \"...\"}. "
                "termux: arg is ONE shell command for Termux (Linux, no root, use pkg not apt). Read-only commands run at once, others need the user's approval. "
                "claude: arg is a question or task for the Claude app. It is slow, but when the goal says to ask Claude you MUST use it. "
                "open: arg is an app name or package to open (e.g. chrome or com.android.chrome); returns what is on its screen. tap: arg is a button label to tap in the current app; returns the new screen. read: returns the current screen text. home: returns to RAMBO AI. For multi-app goals: open the app, tap or read, then home, then done. "
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
        _safe83 = bool(re.match(r"^(am start|monkey -p)\b", cmd.strip())) and not re.search(r"[;&|`$<>]", cmd)
        if not _safe83 and (self._auto_risky(cmd) or self._v77_needs_ok(cmd)):  # V77_AUTO
            ev = threading.Event()
            self._v75_ev_ok = ev
            self._v75_ok = False
            self._v75_say("Needs your OK: " + cmd[:200] + "\nType approve within 2 minutes, or stop goal.")
            ev.wait(120)
            if not self._v75_ok:
                return "NOT APPROVED (no approval, so it was not run)"
        self._v75_say("Running in Termux: " + cmd[:100])
        out = self._v72_run_termux(cmd)
        self._v75_say("Result:\n" + out[:700])
        return out

    def _v78_stat(self, msg):  # V78_STICKY
        self._v78_msg = str(msg).replace("\n", " ")[:55]

    def _v78_start(self):
        self._v78_on = True
        self._v78_msg = "starting"
        threading.Thread(target=self._v78_loop, daemon=True).start()

    def _v78_loop(self):
        try:
            from jnius import autoclass
            from android.runnable import run_on_ui_thread
            Toast = autoclass("android.widget.Toast")
            JS = autoclass("java.lang.String")
            act = autoclass("org.kivy.android.PythonActivity").mActivity
        except Exception as e:
            self.err("v78 toast", e)
            return
        box = {"t": None}

        @run_on_ui_thread
        def show(m):
            try:
                if box["t"] is not None:
                    box["t"].cancel()
                box["t"] = Toast.makeText(act, JS(m), 1)
                box["t"].show()
            except Exception:
                pass

        while getattr(self, "_v78_on", False):
            show("AUTO RUNNING: " + getattr(self, "_v78_msg", "working"))
            time.sleep(3)
        show("AUTO: finished")

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

    def _v86_cont(self, q):
        from jnius import autoclass
        S = getattr(self, "_v81_S", None) or autoclass("org.rambo.acc.RamboAccService")
        if str(S.currentPackage() or "") != "com.anthropic.claude":
            self._v82_open("com.anthropic.claude")
            time.sleep(2)
        scr = str(S.screenText() or "")
        if "Reply to Claude" not in scr:
            self._v75_say("Not in a Claude chat, using a new chat instead")
            return False
        self._v78_stat("Typing in current Claude chat")
        s, _f = self.acc_run("acc type " + q)
        if not str(s).startswith("Typed"):
            self._v75_say("DEBUG type failed: " + str(s)[:80])
            return False
        time.sleep(1)
        s, _f = self.acc_run("acc tap Send message")
        if not str(s).startswith("Tapped"):
            s, _f = self.acc_run("acc tapxy 975 1370")
        self._v78_stat("Send result: " + str(s)[:60])
        return str(s).startswith("Tapped")

    def _v86_wait(self, q):
        S = None
        try:
            from jnius import autoclass
            S = getattr(self, "_v81_S", None) or autoclass("org.rambo.acc.RamboAccService")
        except Exception:
            pass
        prev, reply, t0 = "", "", time.time()
        while not self._v75_stop and time.time() - t0 < 150:
            time.sleep(5)
            self._v78_stat("Waiting for Claude (%ds)" % int(time.time() - t0))
            cur = ""
            try:
                if S is not None and str(S.currentPackage() or "") == "com.anthropic.claude":
                    cur = str(S.screenText() or "")
            except Exception:
                cur = ""
            if cur and cur == prev and q[-40:] in cur and len(cur) - cur.rfind(q[-40:]) - len(q[-40:]) > 20:
                reply = cur
                break
            prev = cur
        self._rb_wait = None
        self._v75_front()
        if not reply:
            return "Claude did not reply (it may be stuck). Do NOT ask Claude again. Use done and tell the user Claude did not answer."
        k = reply.rfind(q[-40:])
        if k >= 0:
            reply = reply[k + len(q[-40:]):]
        return reply.strip()[:1500]

    def _v75_claude(self, q, cont=False):
        if cont:
            self._v75_say("Asking Claude (same chat): " + q[:120])
            sent = False
            try:
                sent = self._v86_cont(q)
            except Exception as e:
                self._v75_say("DEBUG cont error: " + str(e)[:100])
            if sent:
                return self._v86_wait(q)
        return self._v75_claude_new(q)

    def _v75_claude_new(self, q):
        self._v75_say("Asking Claude: " + q[:120])
        Clock.schedule_once(lambda dt: self.rb_send("claude", q), 0)
        time.sleep(8)
        try:  # V80_SHARE
            from jnius import autoclass as _ac80
            _S80 = getattr(self, "_v81_S", None) or _ac80("org.rambo.acc.RamboAccService")
            _pk = str(_S80.currentPackage() or "")
            _scr = str(_S80.screenText() or "")
            self._v75_say("DEBUG screen: pkg=%s text=%s" % (_pk, _scr[:150].replace("\n", " | ")))
            if _pk == "com.anthropic.claude":
                if "Send to" in _scr:
                    self._v78_stat("Choosing New chat in Claude")
                    _s, _f = self.acc_run("acc tap New chat")
                    if not str(_s).startswith("Tapped"):
                        self.acc_run("acc tapxy 540 393")
                    time.sleep(3)
                elif not _scr.strip():
                    self._v78_stat("Screen unreadable, tapping New chat spot")
                    self.acc_run("acc tapxy 540 393")
                    time.sleep(3)
        except Exception as e:
            self._v75_say("DEBUG share error: " + str(e)[:100])
        self._v78_stat("Tapping Send in Claude")
        short, _f = self.acc_run("acc tap Send message")
        if not str(short).startswith("Tapped"):
            short, _f = self.acc_run("acc tapxy 975 1370")
        self._v78_stat("Send result: " + str(short)[:60])
        S = None
        try:
            from jnius import autoclass
            S = getattr(self, "_v81_S", None) or autoclass("org.rambo.acc.RamboAccService")
        except Exception:
            pass
        prev, reply, t0 = "", "", time.time()
        while not self._v75_stop and time.time() - t0 < 150:
            time.sleep(5)
            self._v78_stat("Waiting for Claude (%ds)" % int(time.time() - t0))
            cur = ""
            try:
                if S is not None and str(S.currentPackage() or "") == "com.anthropic.claude":
                    cur = str(S.screenText() or "")
            except Exception:
                cur = ""
            if cur and cur == prev and q[-40:] in cur and len(cur) - cur.rfind(q[-40:]) - len(q[-40:]) > 20:
                reply = cur
                break
            prev = cur
        self._rb_wait = None
        self._v75_front()
        if not reply:
            return "Claude did not reply (it may be stuck). Do NOT ask Claude again. Use done and tell the user Claude did not answer."  # V80_NOREASK
        k = reply.rfind(q[-40:])
        if k >= 0:
            reply = reply[k + len(q[-40:]):]
        return reply.strip()[:1500]

    def _v82_log(self, goal, steps, result):
        try:
            import os, json, time
            f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rambo_log.json")
            try:
                data = json.load(open(f))
            except Exception:
                data = []
            data.append({"time": time.time(), "goal": goal, "steps": steps, "result": result})
            json.dump(data, open(f, "w"), indent=2)
        except Exception as e:
            self.err("v82 log", e)

    def _v82_read(self):
        try:
            from jnius import autoclass
            S = getattr(self, "_v81_S", None) or autoclass("org.rambo.acc.RamboAccService")
            pk = str(S.currentPackage() or "")
            tx = str(S.screenText() or "").replace("\n", " | ")
            return "[%s] %s" % (pk, tx[:1200])
        except Exception as e:
            return "Could not read screen: " + str(e)[:100]

    def _v82_open(self, name):
        try:
            from jnius import autoclass
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            Intent = autoclass("android.content.Intent")
            pm = act.getPackageManager()
            pkg = name.strip()
            if "." not in pkg:
                low, found = pkg.lower(), ""
                apps = pm.getInstalledApplications(0)
                for i in range(apps.size()):
                    ai = apps.get(i)
                    try:
                        lab = str(pm.getApplicationLabel(ai)).lower()
                    except Exception:
                        continue
                    if low in lab and pm.getLaunchIntentForPackage(ai.packageName):
                        found = str(ai.packageName)
                        break
                if not found:
                    return "App not found: " + name + ". Try the package name."
                pkg = found
            li = pm.getLaunchIntentForPackage(pkg)
            if li is None:
                return "Cannot launch " + pkg
            li.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            self._v78_stat("Opening " + pkg)
            act.startActivity(li)
            time.sleep(4)
            return self._v82_read()
        except Exception as e:
            return "Open failed: " + str(e)[:100]

    def _v82_tap(self, label):
        self._v78_stat("Tapping " + label[:30])
        short, _f = self.acc_run("acc tap " + label)
        if label.strip().lower() in ("send", "send message") and not str(short).startswith("Tapped"):
            short, _f = self.acc_run("acc tap Send message")
            if not str(short).startswith("Tapped"):
                short, _f = self.acc_run("acc tapxy 975 2175")
        time.sleep(2)
        return str(short) + " | " + self._v82_read()

    def _v82_home(self):
        self._v75_front()
        time.sleep(2)
        return "Back in RAMBO AI"

    def _v75_thread(self, goal):
        self.ka(True)
        self._v78_start()
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
                    self._v82_log(goal, hist, arg)
                    self._v75_say("DONE: " + arg[:1500])
                    return
                if act == "termux" and arg:
                    out = self._v75_term(arg)
                elif act == "claude" and arg:
                    out = self._v75_claude(arg)
                elif act == "open" and arg:
                    out = self._v82_open(arg)
                elif act == "tap" and arg:
                    out = self._v82_tap(arg)
                elif act == "read":
                    out = self._v82_read()
                elif act == "home":
                    out = self._v82_home()
                else:
                    out = "Unknown or empty action"
                hist.append("%d. %s %s -> %s" % (n, act, arg[:300], out[:900]))
            self._v75_say("Stopped after 10 steps without finishing.")
        except Exception as e:
            self.err("v75 goal", e)
            self._v75_say("Goal stopped by an error: " + str(e)[:120])
        finally:
            self.ka(False)
            self._v78_on = False

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
                    "claude <question or task> asks the Claude app and returns its reply as a SCREEN line. It is slow, but when the goal says to ask Claude you MUST use it. "
                    "To inspect an APK run: termux ~/reverse.sh <apk path>. It prints a summary of the Java side only. "
                    "Never use rm -rf, dd or mkfs. Use one termux or claude command per turn. "
                    "Only report results that appear in the log as TERMUX or SCREEN lines. Never say Claude answered unless a SCREEN Claude reply line is in the log. After a claude command, wait for its reply line before you set done. To ask Claude you must put a command like claude <question> in the commands list; writing it in note does nothing.")

    def _v72_orig_sys(self, p):
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
             "(then leave commands empty). Set done true only when the goal is fully finished. When the result is ready, put it in note, set done true and leave question empty. Never put a final result in question. "
             "Allowed commands: open <app>, timer <minutes>, alarm HH:MM, "
             "play <what to play on YouTube>. To play a song or video use the play command by "
             "itself. Max 3 commands. " + ACC_AUTO)
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
            lines.append(k.upper() + ": " + t[:(2500 if t.startswith("TERMUX") else (webcut if t.startswith(("WEB", "SCREEN")) else cut))])
        older = []
        try:
            p = self.db.get_project(pid)
            last = lines[-1] if lines else ""
            older = self.db.recall_project(
                pid, n, ((p[1] + " " + (p[2] or "")) if p else "") + " " + last)
        except Exception as e:
            self.err("recall", e)
        head = ""
        if older:
            head = ("Earlier findings from this project (older than the log below):\n- "
                    + "\n- ".join(older) + "\n\n")
        return head + "Project log so far:\n" + "\n".join(lines) + "\n\nDo the next step."

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

    def _auto_groq(self, p, pid):
        try:
            payload = {
                "systemInstruction": {"parts": [{"text": self._auto_sys(p)}]},
                "contents": [{"role": "user",
                              "parts": [{"text": self._auto_user(pid, 12, 500, 2000)}]}],
            }
            code, raw = _groq_fallback(json.dumps(payload).encode(), 0, "")
            if code != 200:
                self._last_model_err = "Groq failed"
                return None
            txt = json.loads(raw)["candidates"][0]["content"]["parts"][0]["text"]
            return self._auto_parse(txt)
        except Exception as e:
            self._last_model_err = "Groq: " + str(e)[:80]
            return None

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
            self._last_model_err = "Gemini net error: " + str(e)[:80]
            return None
        if code == 429:
            self.gem_mark_down()
            self._last_model_err = "Gemini rate limit (429)"
            return None
        if code != 200:
            self.err("auto gemini " + str(code), raw[:150])
            self._last_model_err = "Gemini " + str(code) + ": " + gem_msg(raw)
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
                order = ["gemma", "gemini", "groq"]
                if pick_first(goal) == "gemini" and self.gem_ok():
                    order = ["gemini", "gemma", "groq"]
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
                            self._last_model_err = "Gemma: " + str(e)[:80]
                            got = None
                        if got and got[0] and got[0] == getattr(self, "_last_note", None):
                            got = None
                    elif who == "groq":
                        got = self._auto_groq(p, pid)
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
                        res, src = got, {"gemma": "Gemma", "groq": "Groq"}.get(who, "Gemini")
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
                    self.auto_note = "Waiting for a model, retry %d in %d s. %s" % (fails, wait, getattr(self, "_last_model_err", ""))
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
                if cmds:
                    self.db.add_plog(pid, "run", "CMDS: " + json.dumps(cmds)[:200])
                if sw:
                    jobs.append(("search", sw))
                if ru:
                    jobs.append(("read", ru))
                for cm in cmds:
                    c = cm.strip()
                    _m = re.match(r"^(?:ask\s+)?claude\s*[:,\-]?\s*(.+)$", c, re.I | re.S)
                    if _m:
                        c = "claude " + _m.group(1).strip()
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
                claude_ran = False
                rest = []
                for cm in keep:
                    if cm.strip().lower().startswith("claude "):
                        if claude_ran:
                            continue
                        claude_ran = True
                        cq = cm.strip()[7:].strip()
                        prior = [t for ts, k, t in self.db.plog(pid, 60) if t.startswith("CLAUDE ASKED: " + cq[:100])]
                        if len(prior) >= 2:
                            self.db.add_plog(pid, "run", "SCREEN Already asked Claude this twice. Do not ask again. Use done and say Claude did not answer.")
                        else:
                            had = bool([t for ts, k, t in self.db.plog(pid, 60) if t.startswith("CLAUDE ASKED:")])
                            lg = (goal or "").lower()
                            cont = ("same chat" in lg or "current chat" in lg or (had and "new chat" not in lg))
                            self.db.add_plog(pid, "run", "CLAUDE ASKED: " + cq[:100] + (" [same chat]" if cont else " [new chat]"))
                            self._v75_stop = False
                            rep = self._v75_claude(cq, cont)
                            rep = rep.split("\nCopy message")[0].strip()
                            self.db.add_plog(pid, "run", "SCREEN Claude reply: " + rep[:1500])
                    else:
                        rest.append(cm)
                keep = rest
                for n, cm in enumerate(keep):
                    Clock.schedule_once(lambda dt, cm=cm: self._auto_cmd(pid, cm), self._auto_delay(keep, n))
                pname = p[1]
                if question:
                    self.db.add_plog(pid, "ask", question)
                    self._auto_end(pid, "waiting", None)
                    self.notify("RAMBO AI needs you: " + pname, question)
                    Clock.schedule_once(lambda dt: self.speak(question), 0)
                    return
                if done and not jobs and not claude_ran and (src in ("Gemini", "Groq") or self.auto_steps >= 3):
                    self._auto_end(pid, "done", None)
                    self.notify("Project finished: " + pname, (note or "Done.")[:150])
                    Clock.schedule_once(
                        lambda dt: self.speak("Project " + pname + " is finished."), 0)
                    return
                self._auto_sleep(pid, gen, (6 if src == "Gemini" else 6) + self._auto_delay(keep, len(keep)))
        except Exception as e:
            self.err("auto loop", e)
            try:
                self._auto_end(pid, "paused", "Auto run error: " + str(e)[:120])
            except Exception:
                pass
        finally:
            if not self.auto_on:
                self.ka(False)

    def _auto_delay(self, keep, n):
        d = 1.0 + 1.5 * n
        for c in keep[:n]:
            if c.strip().lower().startswith("open "):
                d += 3.5
        return d

    def _auto_risky(self, cm):
        low = cm.strip().lower()
        verb = low.split(" ", 1)[0] if low else ""
        return verb in ("call", "text", "sms", "email", "pay", "buy", "delete")

    def _auto_block(self, pid, cm, why=""):
        self._auto_hold = time.time() + 25
        self.db.add_plog(pid, "run", "STOPPED (needs your OK): " + cm + ((" - " + why) if why else ""))
        q = ("I want to run: " + cm + ". It could have a real-world effect, so I stopped. "
             "If you agree, type that exact command in the command box yourself, "
             "then tap AUTO RUN to continue.")
        self.db.add_plog(pid, "ask", q)
        p = self.db.get_project(pid)
        self._auto_end(pid, "waiting", None)
        try:
            self.notify("RAMBO AI needs you: " + (p[1] if p else ""), q[:150])
            self.speak(q)
        except Exception as e:
            self.err("auto block", e)

    def _auto_acc(self, pid, cm):
        body = cm[3:].strip()
        bl = body.lower()
        if bl.startswith("tapxy"):
            self._auto_block(pid, cm, "tapping a position blind")
            return
        if bl.startswith("tap ") and AUTO_RISKY.search(body[4:]):
            self._auto_block(pid, cm)
            return
        short, full = self.acc_run(cm)
        if full:
            self.db.add_plog(pid, "run", full[:1800])
        else:
            self.db.add_plog(pid, "run", cm + " -> " + short)

    def _auto_learn(self, text, low):
        if not self.cfg.get("learn", True):
            return
        f = learn_fact(text)
        if not f:
            return
        if f.lower() in [m.lower() for m in self.db.memories(300)]:
            return
        self.db.add_memory(f)
        self.db.log("Auto-remembered: " + f)
        self.flash("Remembered: " + f[:80])

    def _auto_cmd(self, pid, cm):
        try:
            if time.time() < getattr(self, "_auto_hold", 0):
                self.db.add_plog(pid, "run", cm + " -> skipped (stopped for your OK)")
                return
            low0 = cm.strip().lower()
            self._v72_status("AUTO: " + cm.strip()[:45])  # AUTO_V72
            if low0.startswith(("termux ", "claude ")):
                self._v72_special(pid, cm.strip())
                return
            if low0 == "acc" or low0.startswith("acc "):
                self._auto_acc(pid, cm.strip())
                return
            if self._auto_risky(cm):
                self._auto_block(pid, cm)
                return
            if cm.lower().startswith("play "):
                self.yt_play(cm[5:])
                self.db.add_plog(pid, "run", cm + " -> finding the video")
                return
            res = self.phone_action(cm)
            self.db.add_plog(pid, "run", cm + " -> " + res)
        except Exception as e:
            self.err("auto cmd", e)

    # ---------- feedback, task list, self test ----------

    def flash(self, msg):
        try:
            self._v75_install()
        except Exception:
            pass
        try:
            self.flash_lbl.text = str(msg).replace("\n", " ")[:120]
        except Exception:
            pass

    def _lastlog(self):
        try:
            rows = self.db.recent_logs()
            return rows[0][1] if rows else ""
        except Exception:
            return ""

    def _wrap(self, cb):
        def run(*a):
            try:
                before = self._lastlog()
                cb(*a)
                after = self._lastlog()
                self.flash(after if after != before else "Done.")
            except Exception as e:
                self.err("button", e)
                self.flash("Error: " + str(e)[:90])
        return run

    def add_task_ref(self, *a):
        self.add_task(None)
        self.sync_tasks(True)

    def sync_tasks(self, force=False):
        try:
            rows = self.db.task_rows()
        except Exception as e:
            self.err("task list", e)
            return
        sig = tuple(rows)
        if sig == self._task_sig and not force:
            return
        self._task_sig = sig
        self.task_list.clear_widgets()
        if not rows:
            self.task_list.add_widget(autosize(Label(text="No tasks yet.", color=TXT)))
        for tid, text in rows:
            r = BoxLayout(size_hint_y=None, height=_dp(56), spacing=5)
            l = Label(text=text, color=TXT, halign="left", valign="middle",
                      shorten=True, shorten_from="right", size_hint_x=0.5)
            l.bind(size=lambda w, v: setattr(w, "text_size", v))
            run = NeonButton(glow=GREEN, text="RUN", size_hint_x=0.25)
            run.bind(on_press=lambda inst, t=text: self.run_task(t))
            dn = NeonButton(glow=AMBER, text="DONE", size_hint_x=0.25)
            dn.bind(on_press=lambda inst, i=tid: self.finish_task(i))
            r.add_widget(l)
            r.add_widget(run)
            r.add_widget(dn)
            self.task_list.add_widget(r)

    def run_task(self, text):
        name = text[:40]
        pid = self.db.add_project(name, text)
        self.db.add_plog(pid, "you", "Goal: " + text)
        self.refresh_projects()
        self.select_project(pid)
        self.switch("PROJECT")
        self.auto_start()
        self.flash("Running: " + name)

    def finish_task(self, tid):
        try:
            self.db.del_task(tid)
        except Exception as e:
            self.err("finish task", e)
        self.sync_tasks(True)
        self.flash("Task marked done.")

    def run_tests(self):
        out = []

        def ok(name, cond, extra=""):
            out.append(("PASS " if cond else "FAIL ") + name + ((" - " + extra) if extra else ""))

        try:
            self.db.add_memory("selftest zz")
            ok("memory save and forget", self.db.forget("selftest zz") >= 1)
        except Exception as e:
            ok("memory", False, str(e)[:60])
        try:
            self.db.add_task("selftest zz")
            hit = [r for r in self.db.task_rows() if r[1] == "selftest zz"]
            for r in hit:
                self.db.del_task(r[0])
            ok("tasks add, list, delete", bool(hit))
        except Exception as e:
            ok("tasks", False, str(e)[:60])
        try:
            pid = self.db.add_project("selftest zz", "x")
            self.db.add_plog(pid, "you", "t")
            good = len(self.db.plog(pid)) == 1
            self.db.conn.execute("DELETE FROM project_log WHERE project_id=?", (pid,))
            self.db.conn.execute("DELETE FROM projects WHERE id=?", (pid,))
            self.db.conn.commit()
            ok("projects save", good)
        except Exception as e:
            ok("projects", False, str(e)[:60])
        try:
            ok("finances total", isinstance(self.db.finance_total(), (int, float)))
        except Exception as e:
            ok("finances", False, str(e)[:60])
        calls = []
        self.pa = lambda c: (calls.append(c) or "ok")
        self.yt_play = lambda q: (calls.append("yt_play " + q) or "ok")
        try:
            for ph in ("open youtube and play fade to black",
                       "open google and show me pokemon go events",
                       "timer for 10 minutes", "set alarm for 7:30 pm",
                       "search cats", "play lo fi", "open gmail"):
                del calls[:]
                try:
                    self.local_route(ph, ph.lower())
                except Exception as e:
                    calls.append("ERR " + str(e)[:30])
                ok("understands: " + ph, len(calls) == 1 and not calls[0].startswith("ERR"),
                   calls[0][:45] if calls else "no match")
        finally:
            self.__dict__.pop("pa", None)
            self.__dict__.pop("yt_play", None)
        ok("voice reply engine ready", bool(self.tts_ok))
        ok("Gemini key saved", os.path.exists(self.key_path),
           "" if os.path.exists(self.key_path) else "type: setkey YOUR_KEY")
        self.notify("Pocket Pal test", "If you see this, notifications work.")
        out.append("INFO notification sent - check your notification shade")
        out.append("MANUAL tap each PHONE button, then TEST GEMINI")
        return "\n".join(out)

    def run_tests_btn(self, *a):
        s = self.run_tests()
        self.test_out.text = s
        self.flash("%d test(s) failed" % s.count("FAIL ") if "FAIL " in s else "All tests passed.")

    def test_gemini(self, *a):
        self.switch("TALK")
        self.handle("ask reply with the single word OK", False)

    # ---------- play the top YouTube result ----------

    def save_key(self, *a):
        t = self.key_in.text.strip()
        if not t:
            self.flash("Paste the key first.")
            return
        try:
            with open(self.key_path, "w") as f:
                f.write(t)
            self.key_in.text = ""
            self.key_state.text = "Key: SAVED"
            self.flash("Key saved on this phone.")
        except Exception as e:
            self.err("save key", e)
            self.flash("Could not save the key.")

    def yt_play(self, q):
        q = q.strip()
        self.flash("Finding: " + q)
        threading.Thread(target=self._yt_thread, args=(q,), daemon=True).start()
        return "Finding " + q + " on YouTube..."

    def _yt_thread(self, q):
        vid, msg = "", ""
        try:
            code, html = http_get("https://www.youtube.com/results?search_query=" + quote(q))
            for pat in (r'"videoRenderer":\{"videoId":"([A-Za-z0-9_-]{11})"',
                        r'"videoId":"([A-Za-z0-9_-]{11})"',
                        r'\\x22videoId\\x22:\\x22([A-Za-z0-9_-]{11})\\x22'):
                m = re.search(pat, html)
                if m:
                    vid = m.group(1)
                    break
            if not vid:
                msg = "status " + str(code) + ", " + str(len(html)) + " bytes, no video id"
        except Exception as e:
            msg = str(e)
        Clock.schedule_once(lambda dt: self._yt_open(q, vid, msg), 0)

    def _yt_open(self, q, vid, msg):
        if msg:
            self.err("yt find", msg)
        try:
            if vid:
                self.pa("open https://www.youtube.com/watch?v=" + vid)
                self.reply("Playing the top result for " + q + ".")
            else:
                self.pa("open https://www.youtube.com/results?search_query=" + quote(q))
                self.reply("Could not pick a video (" + msg[:90] + "), so I opened the search results.")
        except Exception as e:
            self.err("yt open", e)

    # ---------- voice for the project tab ----------

    def speak_project(self, *a):
        self.convo_active = False
        self.voice_target = self._got_project
        self.flash("Listening... say the project and what it should do.")
        self.listen()

    def _got_project(self, said):
        said = said.strip()
        name, goal = "", said
        m = re.match(r"^(?:create |start |make )?(?:a )?(?:new )?project (?:called|named) (.+?)(?:[,.]? (?:goal|to|that|and) (.+))?$", said, re.I)
        if m:
            name = m.group(1).strip()
            goal = (m.group(2) or said).strip()
        if not name:
            name = " ".join(said.split()[:4]).capitalize()
        self.proj_name.text = name
        self.proj_goal.text = goal
        self.flash("Heard it. Tap CREATE PROJECT, or CREATE AND AUTO RUN.")

    def create_run(self, *a):
        if not self.proj_name.text.strip() and self.proj_goal.text.strip():
            self.proj_name.text = " ".join(self.proj_goal.text.split()[:4]).capitalize()
        self.new_project()
        if self.cur_proj is not None:
            self.auto_start()

    def speak_note(self, *a):
        if self.cur_proj is None:
            self.flash("Open a project first.")
            return
        self.convo_active = False
        self.voice_target = self._got_note
        self.flash("Listening... say your note or answer.")
        self.listen()

    def _got_note(self, said):
        self.proj_note.text = said.strip()
        self.add_note()

    # ---------- chat helpers ----------

    def add_msg(self, text, mine):
        b = Bubble(mine=mine, text=text)
        row = BoxLayout(size_hint_y=None, height=b.height, spacing=6)
        b.bind(height=lambda w, h: setattr(row, "height", h))
        if mine:
            b.size_hint_x = 0.82
            row.add_widget(Widget(size_hint_x=0.18))
            row.add_widget(b)
        else:
            b.size_hint_x = 1
            row.add_widget(b)
        self.chat_box.add_widget(row)
        Clock.schedule_once(lambda dt: setattr(self.chat_scroll, "scroll_y", 0), 0.15)
        return row

    def remove_thinking(self):
        if self.thinking is not None:
            try:
                self.chat_box.remove_widget(self.thinking)
            except Exception:
                pass
            self.thinking = None

    def load_chat(self):
        rows = self.db.recent_chat(30)
        if rows:
            self.hide_chips()
        for role, text in rows:
            self.add_msg(text, role == "user")
        self.hist = [("user" if r == "user" else "model", t) for r, t in rows][-8:]
        if not rows:
            self.add_msg("Hi, I am RAMBO AI. Tap MIC and say something like "
                         "\"open youtube\" or \"set a timer for 10 minutes\". "
                         "Type help for more.", False)
        if not os.path.exists(self.key_path):
            self.add_msg("To enable AI answers, type: setkey YOUR_GEMINI_KEY", False)

    def err(self, where, e):
        try:
            self.db.log("ERROR " + where + ": " + str(e)[:200])
        except Exception:
            pass

    def reply(self, text):
        self.remove_thinking()
        self.add_msg(text, False)
        try:
            self.db.add_chat("bot", text)
            self.db.log("Pal: " + text[:100])
        except Exception as e:
            self.err("reply", e)
        self.hist.append(("model", text))
        self.hist = self.hist[-12:]
        self.speak(text)
        if self.convo_active:
            Clock.schedule_once(lambda dt: self._after_speech(0), 0.6)
        self.refresh()

    # ---------- text to speech ----------

    def init_tts(self):
        try:
            from jnius import autoclass, PythonJavaClass, java_method
            PA = autoclass("org.kivy.android.PythonActivity")
            TTS = autoclass("android.speech.tts.TextToSpeech")
            app = self

            class InitListener(PythonJavaClass):
                __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
                __javacontext__ = "app"

                @java_method("(I)V")
                def onInit(self, status):
                    app.tts_ok = (status == 0)

            self._tts_listener = InitListener()
            self.tts = TTS(PA.mActivity, self._tts_listener)
        except Exception as e:
            self.err("tts init", e)

    def speak(self, text):
        if not (self.cfg.get("talk") and self.tts_ok and self.tts is not None):
            return
        try:
            from jnius import autoclass
            TTS = autoclass("android.speech.tts.TextToSpeech")
            t = re.sub(r"[*_`#]", "", text)[:700]
            JS = autoclass("java.lang.String")
            BN = autoclass("android.os.Bundle")
            try:
                self.tts.speak(JS(t), TTS.QUEUE_FLUSH, BN(), "pp")
            except Exception:
                self.tts.speak(JS(t), TTS.QUEUE_FLUSH, None)
        except Exception as e:
            self.err("speak", e)

    def _after_speech(self, tries):
        if not self.convo_active:
            return
        speaking = False
        try:
            speaking = bool(self.tts is not None and self.tts_ok and self.tts.isSpeaking())
        except Exception:
            speaking = False
        if speaking and tries < 120:
            Clock.schedule_once(lambda dt: self._after_speech(tries + 1), 0.5)
            return
        Clock.schedule_once(lambda dt: self.listen(), 0.4)

    # ---------- + button: attach a file (APK files go to the APK Analyzer) ----------

    ATTACH_MAX = 15 * 1024 * 1024
    APK_EXT = (".apk", ".apks", ".xapk", ".apkm")
    APK_HELP = ("APK Analyzer. It only reads APK files. It never installs or runs them.\n"
                "apk pick (or tap + and choose an APK)\n"
                "apk summary | manifest | permissions | components [exported]\n"
                "apk strings TEXT | classes TEXT | class NAME | method CLASS METHOD\n"
                "apk search TEXT | deps | network | files TEXT | file PATH\n"
                "apk report | apk report save\n"
                "apk ask YOUR QUESTION (Gemma answers from the extracted evidence)\n"
                "apk cloud on / off (lets Gemini help, and shows what would be sent)\n"
                "apk limit MB | apk cancel | apk delete | apk delete all | apk jadx")
    APK_SYS = ("You are RAMBO AI's APK analysis assistant. You get EVIDENCE from static analysis of an "
               "Android APK: manifest data, class and method names, strings, URLs, libraries. Rules: "
               "use only the evidence. Name the class, string, permission or file behind every technical "
               "claim. Label claims CONFIRMED (directly in the evidence) or HYPOTHESIS (inferred). If the "
               "evidence is not enough, say: Cannot be determined from the evidence, and say what to look "
               "at next. Method bodies are NOT decompiled, so never claim to know what a method does "
               "internally. If you need more data, reply with ONLY a JSON object such as "
               "{\"tool\":\"search_code\",\"args\":{\"query\":\"login\"}}. Allowed tools: "
               "inspect_apk_manifest, list_permissions, list_components, search_apk_strings, list_classes, "
               "inspect_class, inspect_method, search_code, inspect_dependencies, "
               "inspect_network_references, summarize_apk. Otherwise answer in plain text, short, for a "
               "phone screen. If asked to write code, write your own original implementation of the "
               "behavior and say it is not the app's source code.")

    def on_attach(self, instance):
        self.flash("Pick a file to attach")
        self._pick_file("attach")

    def on_apk_pick(self):
        self._pick_file("apk")

    def _pick_file(self, mode):
        try:
            from jnius import autoclass
            from android import activity
            PA = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            i = Intent(Intent.ACTION_OPEN_DOCUMENT)
            i.addCategory(Intent.CATEGORY_OPENABLE)
            i.setType("*/*")
            self._pick_mode = mode
            activity.unbind(on_activity_result=self.on_attach_result)
            activity.bind(on_activity_result=self.on_attach_result)
            PA.mActivity.startActivityForResult(i, 4343)
            return True
        except Exception as e:
            self.err("file picker", e)
            self.add_msg("Could not open the file picker: " + str(e)[:160], False)
            return False

    def on_attach_result(self, request, result, data):
        if request != 4343:
            return
        if result != -1 or data is None:
            return
        try:
            uri = data.getData()
        except Exception as e:
            Clock.schedule_once(lambda dt: self.err("attach result", e), 0)
            return
        if uri is None:
            return
        mode = getattr(self, "_pick_mode", "attach")
        threading.Thread(target=self._attach_read, args=(uri, mode), daemon=True).start()

    def _say(self, text):
        Clock.schedule_once(lambda dt: self.add_msg(text, False), 0)

    def _prog(self, text):
        Clock.schedule_once(lambda dt: self.flash(text), 0)

    def _attach_read(self, uri, mode):
        name, mime, err, fd = "file", "", "", None
        try:
            from jnius import autoclass
            PA = autoclass("org.kivy.android.PythonActivity")
            res = PA.mActivity.getContentResolver()
            try:
                mime = str(res.getType(uri) or "")
            except Exception:
                pass
            try:
                cur = res.query(uri, None, None, None, None)
                if cur is not None:
                    try:
                        if cur.moveToFirst():
                            ix = cur.getColumnIndex("_display_name")
                            if ix >= 0:
                                name = str(cur.getString(ix))
                    finally:
                        cur.close()
            except Exception:
                pass
            pfd = res.openFileDescriptor(uri, "r")
            fd = pfd.detachFd()
        except Exception as e:
            err = str(e)[:150]
        if fd is None:
            self._say("Could not open that file. " + err)
            return
        low = name.lower()
        if mode == "apk" or low.endswith(self.APK_EXT) or mime == "application/vnd.android.package-archive":
            self._apk_import(fd, name)
            return
        if mode in ("prog", "doc") or low.endswith(self.PROG_BIN_EXT):
            if mode == "doc":
                self._doc_import(fd, name)
            else:
                self._prog_import(fd, name)
            return
        raw = b""
        try:
            with os.fdopen(fd, "rb") as f:
                raw = f.read(self.ATTACH_MAX + 1)
        except Exception as e:
            err = str(e)[:150]
        Clock.schedule_once(lambda dt: self._attach_done(name, mime, raw, err), 0)

    def _attach_done(self, name, mime, raw, err):
        import base64
        import mimetypes
        if err or not raw:
            self.add_msg("Could not read that file. " + err, False)
            return
        if len(raw) > self.ATTACH_MAX:
            self.add_msg("That file is over 15 MB. Pick a smaller one.", False)
            return
        if mime in ("", "application/octet-stream"):
            mime = mimetypes.guess_type(name)[0] or mime
        parts = None
        if mime.startswith(("image/", "audio/")) or mime == "application/pdf":
            parts = [{"inline_data": {"mime_type": mime,
                                      "data": base64.b64encode(raw).decode()}}]
        else:
            try:
                t = raw.decode("utf-8")
                if "\x00" in t[:2000]:
                    raise ValueError("binary")
                parts = [{"text": "File " + name + ":\n" + t[:120000]}]
            except Exception:
                parts = None
        if parts is None:
            self.add_msg("I can read text, PDF, image and audio files. That one looks like "
                         + (mime or "an unknown type") + ".", False)
            return
        self.attach = {"name": name, "parts": parts, "preview": None}
        try:
            self._att_preview(name, mime, raw)
        except Exception as e:
            self.err("attach preview", e)
            self.add_msg("Attached: " + name + ". Type your question and press SEND.", False)

    # ---------- attachment preview (thumbnail + X above the message box) ----------

    def _att_make_strip(self):
        from kivy.uix.image import Image as KImage
        strip = BoxLayout(size_hint_y=None, height=0, spacing=8,
                          padding=[10, 0, 4, 0], opacity=0, disabled=True)
        thumb = KImage(size_hint=(None, 1), width=0)
        try:
            thumb.fit_mode = "contain"
        except Exception:
            pass
        lab = Label(text="", color=TXT, font_size="13sp", halign="left", valign="middle")
        lab.bind(size=lambda w, sz: setattr(w, "text_size", sz))
        rm = NeonButton(glow=MAGENTA, text="X", size_hint=(None, 1), width=_dp(56), font_size="20sp")
        rm.bind(on_press=lambda *a: self._att_remove())
        strip.add_widget(thumb)
        strip.add_widget(lab)
        strip.add_widget(rm)
        self.att_strip, self.att_thumb, self.att_lab = strip, thumb, lab
        return strip

    def _att_show(self, on):
        s = getattr(self, "att_strip", None)
        if s is None:
            return
        s.height = 76 if on else 0
        s.opacity = 1 if on else 0
        s.disabled = not on

    def _att_dir(self):
        d = os.path.join(self.user_data_dir, "att_prev")
        os.makedirs(d, exist_ok=True)
        try:
            cut = time.time() - 7 * 86400
            for f in os.listdir(d):
                p = os.path.join(d, f)
                if os.path.getmtime(p) < cut:
                    os.remove(p)
        except Exception:
            pass
        return d

    def _att_preview(self, name, mime, raw):
        path = None
        ext = os.path.splitext(name)[1].lower()
        if mime.startswith("image/") and ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
            path = os.path.join(self._att_dir(), "%d%s" % (int(time.time() * 1000), ext))
            with open(path, "wb") as f:
                f.write(raw)
        self.attach["preview"] = path
        th = self.att_thumb
        if path:
            th.source = path
            try:
                th.reload()
            except Exception:
                pass
            th.width = 64
        else:
            th.source = ""
            th.width = 0
        kind = "Image" if path else ((mime.split("/")[-1] or "File").upper())
        kb = max(1, len(raw) // 1024)
        self.att_lab.text = (name + "\n" + kind + ", " + str(kb)
                             + " KB. Type a question and press SEND, or tap X to remove.")
        self._att_show(True)

    def _att_remove(self):
        att = getattr(self, "attach", None)
        self.attach = None
        self._att_show(False)
        try:
            if att and att.get("preview") and os.path.exists(att["preview"]):
                os.remove(att["preview"])
        except Exception:
            pass
        self.flash("Attachment removed")

    def _att_bubble(self, path):
        if not path or not os.path.exists(path):
            return
        try:
            from kivy.uix.image import Image as KImage
            row = BoxLayout(size_hint_y=None, height=190, spacing=6)
            row.add_widget(Widget(size_hint_x=0.35))
            img = KImage(source=path, size_hint_x=0.65)
            try:
                img.fit_mode = "contain"
            except Exception:
                pass
            row.add_widget(img)
            self.chat_box.add_widget(row)
            Clock.schedule_once(lambda dt: setattr(self.chat_scroll, "scroll_y", 0), 0.15)
        except Exception as e:
            self.err("attach bubble", e)

    def _send_attach(self, text):
        att = self.attach
        self.attach = None
        self._att_show(False)
        if not text:
            text = "Summarize this file."
        shown = text + "\n(file: " + att["name"] + ")"
        self._att_bubble(att.get("preview"))
        self.add_msg(shown, True)
        self.hide_chips()
        try:
            self.db.add_chat("user", shown)
        except Exception as e:
            self.err("chat save", e)
        self.hist.append(("user", text))
        self.hist = self.hist[-12:]
        self._att_once = att["parts"]
        try:
            self._ask_cloud(text)
        finally:
            self._att_once = None

    # ---------- APK Analyzer (static: reads the file, never runs or installs it) ----------

    def _apk_root(self):
        p = os.path.join(self.user_data_dir, "apk_ws")
        os.makedirs(p, exist_ok=True)
        return p

    def _apk_ws(self):
        root = os.path.realpath(self._apk_root())
        ws = getattr(self, "apk_cur", None)
        if not ws:
            try:
                ws = open(os.path.join(root, "current.txt")).read().strip()
            except Exception:
                ws = None
        if ws and os.path.dirname(os.path.realpath(ws)) == root and os.path.isfile(os.path.join(ws, "info.json")):
            self.apk_cur = ws
            return ws
        return None

    def _apk_import(self, fd, name):
        import shutil
        import apkscan
        if getattr(self, "apk_busy", False):
            try:
                os.close(fd)
            except Exception:
                pass
            self._say("An APK is already being analyzed. Say: apk cancel")
            return
        self.apk_cancel = False
        self.apk_busy = True
        root = self._apk_root()
        inc = os.path.join(root, "incoming.part")
        try:
            limit = int(self.cfg.get("apk_max_mb", 600)) << 20
            free = shutil.disk_usage(root).free
            if free < 200 * 1024 * 1024:
                raise apkscan.ApkError("Less than 200 MB of free storage. Free some space first.")
            self._say("Importing " + name + ". It is only read, never installed or run.")
            with os.fdopen(fd, "rb") as f:
                apkscan.copy_stream(f, inc, limit, lambda: self.apk_cancel,
                                    lambda n: self._prog("Copied %d MB" % (n >> 20)))
            if free < 2 * os.path.getsize(inc) + 100 * 1024 * 1024:
                raise apkscan.ApkError("Not enough free storage to analyze this file.")
            info = apkscan.analyze(inc, root, name, self._prog, lambda: self.apk_cancel, limit)
            ws = info["ws"]
            self.apk_cur = ws
            try:
                open(os.path.join(root, "current.txt"), "w").write(ws)
            except Exception:
                pass
            head = ("APK analyzed" + (" (from cache)" if info.get("cached") else "") + "\n"
                    + "File: " + str(info.get("file_name")) + "\n"
                    + "Size: %d KB\n" % (info["size"] // 1024)
                    + "SHA-256: " + info["sha256"] + "\n"
                    + "Type: " + ("split bundle, base APK analyzed" if info["archive"] == "bundle" else "APK") + "\n\n")
            self._say(head + apkscan.run_tool(ws, "summarize_apk", {})
                      + "\n\nNext: apk report | apk permissions | apk ask <question> | apk help")
        except apkscan.Cancelled:
            self._say("Analysis cancelled. Partial files were removed.")
        except apkscan.ApkError as e:
            self._say("Could not analyze this file: " + str(e))
        except MemoryError:
            self._say("Ran out of memory. Try: apk limit 200, or analyze on a computer.")
        except Exception as e:
            self.err("apk import", e)
            self._say("APK analysis failed: " + str(e)[:200])
        finally:
            self.apk_busy = False
            try:
                if os.path.exists(inc):
                    os.remove(inc)
            except Exception:
                pass

    def _apk_async(self, fn, label):
        def work():
            try:
                out = fn()
            except Exception as e:
                if e.__class__.__name__ not in ("ToolError", "ApkError"):
                    self.err("apk tool", e)
                out = "APK tool: " + str(e)[:300]
            self._say(out)
        threading.Thread(target=work, daemon=True).start()
        return label

    def _save_download(self, fname, data, mime):
        from jnius import autoclass
        PA = autoclass("org.kivy.android.PythonActivity")
        ContentValues = autoclass("android.content.ContentValues")
        Downloads = autoclass("android.provider.MediaStore$Downloads")
        cr = PA.mActivity.getContentResolver()
        cv = ContentValues()
        cv.put("_display_name", fname)
        cv.put("mime_type", mime)
        cv.put("relative_path", "Download")
        uri = cr.insert(Downloads.EXTERNAL_CONTENT_URI, cv)
        out = cr.openOutputStream(uri)
        out.write(data, 0, len(data))
        out.close()

    def apk_route(self, text, low):
        if not (low == "apk" or low.startswith("apk ")
                or low.startswith(("analyze apk", "analyse apk", "inspect apk"))):
            return None
        try:
            import apkscan
        except Exception as e:
            self.err("apk import", e)
            return "The APK Analyzer file (apkscan.py) is not in this build."
        if not low.startswith("apk"):
            self.on_apk_pick()
            return "Choose the APK in the file picker. It is only read, never installed or run."
        rest = text[3:].strip()
        sub = rest.split(" ", 1)[0].lower() if rest else ""
        arg = rest.split(" ", 1)[1].strip() if " " in rest else ""
        ws = self._apk_ws()
        if sub in ("", "help"):
            self.add_msg(self.APK_HELP, False)
            return "APK Analyzer help is above."
        if sub in ("pick", "import", "open", "load"):
            self.on_apk_pick()
            return "Choose the APK in the file picker. It is only read, never installed or run."
        if sub == "cancel":
            self.apk_cancel = True
            return "Cancelling. Partial files will be removed."
        if sub == "limit":
            if arg.isdigit() and 20 <= int(arg) <= 2000:
                self.cfg["apk_max_mb"] = int(arg)
                return "APK size limit set to %s MB until the app restarts." % arg
            return "Use: apk limit 300 (between 20 and 2000 MB). Now: %s MB." % self.cfg.get("apk_max_mb", 600)
        if sub == "jadx":
            self.add_msg("JADX and Apktool need Java, so they cannot run inside this app. "
                         "In Termux you can try: pkg install openjdk-17, download JADX from "
                         "github.com/skylot/jadx/releases, then: jadx -d out file.apk. I have not "
                         "tested that on your phone. The built-in analysis (apk summary, apk class ...) "
                         "needs no Java.", False)
            return "JADX notes are above."
        if sub == "cloud":
            if arg.lower() in ("on", "yes", "enable"):
                self.cfg["apk_cloud"] = True
                return ("Cloud help is ON for this session. When local Gemma cannot answer, Gemini gets your "
                        "question plus up to ~7000 characters of APK findings (class and method names, strings, "
                        "URLs, permissions). Not sent: the APK file, certificates, other files. Secret-looking "
                        "values and emails are removed. You will see what is sent each time.")
            if arg.lower() in ("off", "no", "disable"):
                self.cfg["apk_cloud"] = False
                return "Cloud help is OFF. Everything stays on the phone."
            return "Cloud help is %s. Use: apk cloud on / off" % ("ON" if self.cfg.get("apk_cloud") else "OFF")
        if sub == "delete":
            root = self._apk_root()
            try:
                if arg.lower() == "all":
                    apkscan.delete_workspace(root)
                    self.apk_cur = None
                    return "All APK analysis data deleted."
                if not ws:
                    return "No APK is loaded."
                apkscan.delete_workspace(root, ws)
                self.apk_cur = None
                return "Deleted the analysis of the current APK."
            except Exception as e:
                self.err("apk delete", e)
                return "Could not delete: " + str(e)[:120]
        if sub == "status":
            if not ws:
                return "No APK loaded. Use: apk pick"
            i = apkscan.load_info(ws)
            return "Loaded: %s v%s (%d KB)" % (i["package"], i.get("version_name"), i["size"] // 1024)
        if not ws:
            return "No APK loaded yet. Use: apk pick, or tap + and choose an APK."
        if sub == "report":
            save = arg.lower() == "save"

            def rep():
                i = apkscan.load_info(ws)
                i["ws"] = ws
                body = apkscan.build_report(i)
                if save:
                    fname = "RAMBO_apk_report_" + i["package"] + ".txt"
                    self._save_download(fname, body.encode("utf-8"), "text/plain")
                    return "Report saved to Downloads as " + fname
                return body
            return self._apk_async(rep, "Building the report...")
        if sub == "ask":
            if not arg:
                return "Use: apk ask <your question>"
            return self._apk_ask(arg)
        if sub == "tool":
            def tool():
                try:
                    req = json.loads(arg)
                except Exception:
                    raise apkscan.ToolError("Tool request must be JSON, like {\"tool\":\"list_permissions\",\"args\":{}}")
                if not isinstance(req, dict):
                    raise apkscan.ToolError("Tool request must be a JSON object.")
                return apkscan.run_tool(ws, req.get("tool"), req.get("args"))
            return self._apk_async(tool, "Running tool...")
        table = {"summary": ("summarize_apk", {}), "manifest": ("inspect_apk_manifest", {}),
                 "permissions": ("list_permissions", {}), "perms": ("list_permissions", {}),
                 "deps": ("inspect_dependencies", {}), "libs": ("inspect_dependencies", {}),
                 "network": ("inspect_network_references", {}), "net": ("inspect_network_references", {}),
                 "urls": ("inspect_network_references", {})}
        call = None
        if sub in table:
            call = table[sub]
        elif sub in ("components", "comps"):
            call = ("list_components", {"exported_only": True} if arg.lower().startswith("export") else {})
        elif sub == "strings" and arg:
            call = ("search_apk_strings", {"query": arg})
        elif sub == "classes":
            call = ("list_classes", {"query": arg})
        elif sub == "class" and arg:
            call = ("inspect_class", {"name": arg})
        elif sub == "method" and " " in arg:
            c, m = arg.split(" ", 1)
            call = ("inspect_method", {"class": c, "method": m.strip()})
        elif sub == "search" and arg:
            call = ("search_code", {"query": arg})
        if call is not None:
            return self._apk_async(lambda: apkscan.run_tool(ws, call[0], call[1]), "Looking...")
        if sub == "files":
            return self._apk_async(lambda: apkscan.t_files(ws, {"query": arg}), "Listing files...")
        if sub == "file" and arg:
            return self._apk_async(lambda: apkscan.read_file(ws, arg), "Reading the file...")
        return "Unknown APK command. Say: apk help"

    def _apk_evidence(self, ws, q):
        import apkscan
        ql = q.lower()
        parts = []
        done = set()

        def add(name, args=None):
            key = name + json.dumps(args or {}, sort_keys=True)
            if key in done:
                return
            done.add(key)
            try:
                parts.append("## " + name + (" " + json.dumps(args) if args else "") + "\n"
                             + apkscan.run_tool(ws, name, args or {}))
            except Exception:
                pass
        add("summarize_apk")
        if any(w in ql for w in ("permission", "privacy", "access", "risk", "security")):
            add("list_permissions")
        if any(w in ql for w in ("component", "activity", "service", "receiver", "provider", "export",
                                 "architecture", "how does", "how it works", "explain", "risk", "security")):
            add("list_components", {"exported_only": True} if "export" in ql or "risk" in ql or "security" in ql else {})
        if any(w in ql for w in ("network", "server", "api", "url", "http", "communicat", "endpoint",
                                 "login", "auth", "internet", "risk", "security")):
            add("inspect_network_references")
        if any(w in ql for w in ("librar", "depend", "framework", "built", "sdk", "explain", "store", "setting")):
            add("inspect_dependencies")
        if any(w in ql for w in ("login", "auth", "sign in", "signin", "account", "password")):
            add("search_code", {"query": "login"})
            add("search_code", {"query": "token"})
        if any(w in ql for w in ("setting", "stor", "save", "database", "prefs", "preference", "cache")):
            add("search_code", {"query": "prefs"})
            add("search_code", {"query": "database"})
        stop = ("this", "that", "with", "from", "what", "where", "which", "does", "explain", "find",
                "show", "code", "about", "have", "into", "their", "there", "responsible", "feature",
                "application", "work", "works", "help", "recreate", "generate", "implementation",
                "identify", "relevant", "available", "found", "please")
        for w in [w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_\.]{3,}", q) if w.lower() not in stop][:4]:
            if "." in w and w.count(".") >= 2:
                add("inspect_class", {"name": w})
            else:
                add("search_code", {"query": w})
        return "\n\n".join(parts)[:7000]

    def _apk_llm_local(self, sysm, user, ws):
        import apkscan
        for _round in range(3):
            txt = gemma_chat(sysm, user, max_tokens=600)
            t = txt.strip()
            if t.startswith("```"):
                t = t.strip("`").replace("json", "", 1).strip()
            if t.startswith("{") and t.endswith("}"):
                try:
                    req = json.loads(t)
                except Exception:
                    return txt
                if isinstance(req, dict) and "tool" in req:
                    try:
                        out = apkscan.run_tool(ws, req.get("tool"), req.get("args"))
                    except Exception as e:
                        out = "Tool refused: " + str(e)[:200]
                    user += "\n\n## TOOL RESULT " + json.dumps(req)[:200] + "\n" + out[:3000]
                    continue
            return txt
        return gemma_chat(sysm, user + "\n\nAnswer now with the evidence you have. Do not request more tools.", max_tokens=600)

    def _apk_ask(self, q):
        ws = self._apk_ws()
        if not ws:
            return "No APK loaded yet. Use: apk pick"

        def work():
            import apkscan
            ev = self._apk_evidence(ws, q)
            user = "QUESTION: " + q + "\n\nEVIDENCE FROM THE APK:\n" + ev
            ans = ""
            try:
                ans = self._apk_llm_local(self.APK_SYS, user, ws)
            except Exception as e:
                self.err("apk gemma", str(e)[:100])
                ans = ""
            if ans:
                self._say(ans)
                return
            if self.cfg.get("apk_cloud") and self.gem_ok():
                safe = apkscan.scrub(user)
                self._say("Local Gemma did not answer. Sending to Gemini: your question and %d characters "
                          "of APK findings (names, strings, URLs, permissions). Not sent: the APK file, "
                          "certificates or other files. Secret-looking values and emails were removed." % len(safe))
                body = json.dumps({"systemInstruction": {"parts": [{"text": self.APK_SYS}]},
                                   "contents": [{"role": "user", "parts": [{"text": safe}]}]}).encode()
                code, raw = gemini_try(self.gem_key(), body)
                if code == 200:
                    try:
                        self._say(json.loads(raw)["candidates"][0]["content"]["parts"][0]["text"].strip())
                        return
                    except Exception as e:
                        self.err("apk gemini parse", e)
                self._say("Gemini could not answer (code %s). Here is the evidence I found:\n\n%s" % (code, ev[:3000]))
                return
            self._say("Local Gemma did not answer (start it in Termux). To let Gemini help, say: apk cloud on. "
                      "It shows what is sent. Here is what I found in the APK:\n\n" + ev[:3000])
        threading.Thread(target=work, daemon=True).start()
        return "Looking through the APK..."

    # ---------- auto run: screen control through Accessibility ----------

    def _auto_acc_help(self):
        on = False
        try:
            from jnius import autoclass
            on = bool(autoclass("org.rambo.acc.RamboAccService").isOn())
        except Exception:
            on = False
        if not on:
            return " You cannot tap inside other apps (Accessibility is off, so do not use acc commands)."
        return (" You CAN control the phone screen with these commands: acc screen (reads the text on "
                "screen; the result shows in the log as WEB SCREEN on your next turn), acc tap TEXT "
                "(taps a visible button or label), acc type TEXT, acc scroll down, acc scroll up, "
                "acc back, acc home. After you open an app, use acc screen in your NEXT step, because "
                "the app needs time to load. Read the screen before you tap. Never tap or type anything "
                "about payments, purchases, deleting, uninstalling or passwords: use the question field "
                "and ask the user instead.")

    def _auto_acc(self, pid, cm):
        body = cm.strip()[4:].strip().lower()
        ok = body in ("screen", "back", "home", "paste", "scroll down", "scroll up") or \
            body.startswith(("tap ", "type ", "clip "))
        if not ok:
            self.db.add_plog(pid, "run", cm + " -> not allowed in auto run")
            return
        risky = ("pay", "buy", "purchase", "checkout", "place order", "order now", "delete",
                 "uninstall", "transfer", "send money", "factory reset", "erase", "subscribe",
                 "password", "passcode", "pin")
        if body.startswith(("tap ", "type ")) and any(w in body for w in risky):
            self.db.add_plog(pid, "ask", "I did not run '" + cm + "' because it could spend money, delete "
                             "something or touch a password. Tell me if you want me to do it.")
            self._auto_end(pid, "waiting", None)
            return
        short, full = self.acc_run(cm)
        if short.startswith(("Accessibility is OFF", "Accessibility code is not")):
            self.db.add_plog(pid, "ask", short + " Type: acc settings, turn it on, then tap AUTO RUN.")
            self._auto_end(pid, "waiting", None)
            return
        self.db.add_plog(pid, "run", cm + " -> " + short)
        if full:
            self.db.add_plog(pid, "run", "WEB SCREEN " + " | ".join(full.splitlines())[:1600])

    # ---------- v47: Program Analyzer, document reader, Gemma booster ----------

    PROG_BIN_EXT = (".so", ".elf", ".exe", ".dll", ".bin", ".o", ".out", ".dex", ".jar", ".class")
    PROG_HELP = ("Program Analyzer. Reads any file or program. It never runs, installs or imports it.\n"
                 "prog pick (or tap + and choose a binary)\n"
                 "prog summary | imports [TEXT] | symbols [TEXT] | function NAME\n"
                 "prog strings TEXT | search TEXT | source [FROM TO] | entries [TEXT]\n"
                 "prog report | prog report save\n"
                 "prog ask QUESTION (Gemma answers from the extracted evidence)\n"
                 "Teaching: prog teach FACT | prog lessons [TEXT] | prog forget N\n"
                 "prog good (keep the last answer as an example) | prog bad\n"
                 "prog cloud on / off | prog cancel | prog delete [all] | prog status\n"
                 "Learning (nothing is learned until you approve): prog review | approve N|all | reject N|all | prog lessons export\n"
                 "Documents: doc pick | doc ask QUESTION | doc deep QUESTION | doc summary | doc outline | doc find TEXT | doc list | doc use N | doc delete [N|all]\n"
                 "Knowledge: kb QUESTION | kb add TITLE: NOTE | kb list\n"
                 "Apps: agent TASK | agent stop | agent yes/no | agent cloud on/off | agent stats (say: agent help)\n"
                 "Boost: boost eval | boost tips | boost status")
    PROG_SYS = ("You are RAMBO AI's program analysis assistant. You get EVIDENCE from static analysis of a "
                "file: file type, imports, symbols, function names, strings, source structure. Rules: use only "
                "the evidence. Name the import, symbol, string or line behind every technical claim. Label "
                "claims CONFIRMED (directly in the evidence) or HYPOTHESIS (inferred). If the evidence is not "
                "enough, say: Cannot be determined from the evidence, and say what to look at next. Machine "
                "code is NOT disassembled, so never claim to know what a binary function does internally. "
                "NOTES FROM THE USER may help but the evidence wins if they disagree. If you need more data, "
                "reply with ONLY a JSON object such as {\"tool\":\"search_code\",\"args\":{\"query\":\"login\"}}. "
                "Allowed tools: summarize_program, list_symbols, list_imports, search_strings, list_entries, "
                "read_source, show_function, search_code, recall_lessons, list_capabilities, call_graph, explain_api. REFERENCE NOTES, when given, are general background only. Otherwise answer in plain text, short, "
                "for a phone screen. If asked to recreate behavior, write your own original implementation "
                "and say it is not the original source code. Do not help hide, spread or weaponize malware.")

    def _boost_llm(self):
        def llm(sysm, user, mt):
            return gemma_chat(sysm or "You are a careful assistant. Answer briefly.", user, max_tokens=mt)
        return llm

    def _prog_root(self):
        p = os.path.join(self.user_data_dir, "prog_ws")
        os.makedirs(p, exist_ok=True)
        return p

    def _prog_ws(self):
        root = os.path.realpath(self._prog_root())
        ws = getattr(self, "prog_cur", None)
        if not ws:
            try:
                ws = open(os.path.join(root, "current.txt")).read().strip()
            except Exception:
                ws = None
        if ws and os.path.dirname(os.path.realpath(ws)) == root and os.path.isfile(os.path.join(ws, "info.json")):
            self.prog_cur = ws
            return ws
        return None

    def on_prog_pick(self):
        self._pick_file("prog")

    def _prog_import(self, fd, name):
        import shutil
        import proganalyze as PA
        if getattr(self, "prog_busy", False):
            try:
                os.close(fd)
            except Exception:
                pass
            self._say("A file is already being analyzed. Say: prog cancel")
            return
        self.prog_cancel = False
        self.prog_busy = True
        root = self._prog_root()
        inc = os.path.join(root, "incoming.part")
        try:
            limit = int(self.cfg.get("prog_max_mb", 300)) << 20
            if shutil.disk_usage(root).free < 150 * 1024 * 1024:
                raise PA.ProgError("Less than 150 MB of free storage. Free some space first.")
            self._say("Importing " + name + ". It is only read, never run or installed.")
            with os.fdopen(fd, "rb") as f:
                PA.copy_stream(f, inc, limit, lambda: self.prog_cancel,
                               lambda n: self._prog(("Copied %d MB" % (n >> 20))))
            info = PA.analyze(inc, root, name, self._prog, lambda: self.prog_cancel, limit)
            ws = info["ws"]
            self.prog_cur = ws
            try:
                open(os.path.join(root, "current.txt"), "w").write(ws)
            except Exception:
                pass
            try:
                PA.record_pattern(root, info)
            except Exception as e:
                self.err("prog pattern", e)
            self._say("Analyzed" + (" (from cache)" if info.get("cached") else "") + "\n"
                      + PA.run_tool(ws, "summarize_program", {})
                      + "\n\nNext: prog ask <question> | prog report | prog help")
        except PA.Cancelled:
            self._say("Analysis cancelled. Partial files were removed.")
        except PA.ProgError as e:
            self._say("Could not analyze this file: " + str(e))
        except MemoryError:
            self._say("Ran out of memory. Try a smaller file.")
        except Exception as e:
            self.err("prog import", e)
            self._say("Analysis failed: " + str(e)[:200])
        finally:
            self.prog_busy = False
            try:
                if os.path.exists(inc):
                    os.remove(inc)
            except Exception:
                pass

    def _prog_async(self, fn, label):
        def work():
            try:
                out = fn()
            except Exception as e:
                if e.__class__.__name__ not in ("ToolError", "ProgError", "BoostError"):
                    self.err("prog tool", e)
                out = "Error: " + str(e)[:300]
            self._say(out)
        threading.Thread(target=work, daemon=True).start()
        return label

    def _prog_evidence(self, ws, q):
        import proganalyze as PA
        ql = q.lower()
        parts = []
        done = set()

        def add(name, args=None):
            key = name + json.dumps(args or {}, sort_keys=True)
            if key in done:
                return
            done.add(key)
            try:
                parts.append("## " + name + (" " + json.dumps(args) if args else "") + "\n"
                             + PA.run_tool(ws, name, args or {}))
            except Exception:
                pass
        add("summarize_program")
        info = PA.load_info(ws)
        if any(w in ql for w in ("safe", "risk", "malware", "danger", "virus", "behav", "network", "permission", "capab", "suspicious", "what does", "analy")):
            add("list_capabilities")
        if "py" in info and any(w in ql for w in ("flow", "calls", "who calls", "structure", "work", "how", "main", "recreate", "explain")):
            add("call_graph")
        if any(w in ql for w in ("import", "call", "network", "system", "behav", "what does", "how does",
                                 "do", "risk", "security", "explain", "work")):
            add("list_imports")
        if any(w in ql for w in ("function", "class", "method", "structure", "how", "explain", "work", "main")):
            add("list_symbols")
        if "lines" in info and any(w in ql for w in ("how", "explain", "work", "flow", "logic", "main", "recreate")):
            add("read_source", {"start": 1, "end": 70})
        stop = ("this", "that", "with", "from", "what", "where", "which", "does", "explain", "find", "show",
                "code", "about", "have", "into", "their", "there", "program", "file", "work", "works",
                "please", "function", "functions", "recreate", "write")
        for w in [w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_\.]{3,}", q) if w.lower() not in stop][:4]:
            add("search_code", {"query": w})
        return "\n\n".join(parts)[:7500]

    def _prog_ask(self, q):
        ws = self._prog_ws()
        if not ws:
            return "No file loaded yet. Use: prog pick"

        def work():
            import proganalyze as PA
            import gemmaboost as GB
            root = self._prog_root()
            info = PA.load_info(ws)
            ev = self._prog_evidence(ws, q)
            les = GB.lessons_block(PA.search_lessons(root, q + " " + info.get("kind", ""), 5))
            kbt = GB.kb_block(GB.kb_sections(self.user_data_dir), q + " " + info.get("kind", ""), 3, 800)
            user = les + kbt + "QUESTION: " + q + "\n\nEVIDENCE:\n" + ev
            ans = ""
            try:
                ans = GB.tool_loop(self._boost_llm(), self.PROG_SYS, user,
                                   lambda n, a: PA.run_tool(ws, n, a))
            except Exception as e:
                self.err("prog gemma", str(e)[:100])
            if not ans and self.cfg.get("prog_cloud") and self.gem_ok():
                safe = PA.scrub(user)
                self._say("Local Gemma did not answer. Sending to Gemini: your question plus %d characters of "
                          "findings (names, imports, strings). Not sent: the file itself. Secret-looking values "
                          "and emails were removed." % len(safe))
                body = json.dumps({"systemInstruction": {"parts": [{"text": self.PROG_SYS}]},
                                   "contents": [{"role": "user", "parts": [{"text": safe}]}]}).encode()
                code, raw = gemini_try(self.gem_key(), body)
                if code == 200:
                    try:
                        ans = json.loads(raw)["candidates"][0]["content"]["parts"][0]["text"].strip()
                    except Exception as e:
                        self.err("prog gemini parse", e)
            if not ans:
                self._say("Local Gemma did not answer (start it in Termux). To let Gemini help say: prog cloud on. "
                          "Evidence found:\n\n" + ev[:3000])
                return
            bad = GB.unsupported_names(ans, ev + " " + les)
            self.prog_last = None if bad else (q, ans)
            if not bad:
                try:
                    PA.add_pending(root, q, ans)
                except Exception:
                    pass
            if bad:
                ans += ("\n\nCheck: these names are not in the extracted evidence, so they may be wrong: "
                        + ", ".join(bad) + " (prog good is disabled for this answer.)")
            self._say(ans + "\n\n(Right? prog good. Wrong? prog bad, then prog teach <fact>. Later: prog review.)")
        threading.Thread(target=work, daemon=True).start()
        return "Looking through the file..."

    def prog_route(self, text, low):
        if not (low in ("prog", "doc", "boost", "kb") or low.startswith(("prog ", "doc ", "boost ", "kb ",
                                                                 "analyze program", "reverse engineer"))):
            return None
        try:
            import proganalyze as PA
            import gemmaboost as GB
        except Exception as e:
            self.err("prog import", e)
            return "The analyzer files (proganalyze.py, gemmaboost.py) are not in this build."
        if not low.startswith(("prog", "doc", "boost", "kb")):
            self.on_prog_pick()
            return "Choose the file in the file picker. It is only read, never run."
        head = low.split(" ", 1)[0]
        rest = text[len(head):].strip()
        sub = rest.split(" ", 1)[0].lower() if rest else ""
        arg = rest.split(" ", 1)[1].strip() if " " in rest else ""
        if head == "doc":
            return self._doc_route(rest, sub, arg, GB)
        if head == "kb":
            return self._kb_route(rest, sub, arg, GB)
        if head == "boost":
            return self._boost_route(sub, GB, PA)
        root = self._prog_root()
        ws = self._prog_ws()
        if sub in ("", "help"):
            self.add_msg(self.PROG_HELP, False)
            return "Program Analyzer help is above."
        if sub in ("pick", "import", "open", "load"):
            self.on_prog_pick()
            return "Choose the file in the file picker. It is only read, never run."
        if sub == "cancel":
            self.prog_cancel = True
            return "Cancelling. Partial files will be removed."
        if sub == "review":
            pend = PA.list_pending(root)
            if not pend:
                return "Nothing waiting for approval. Answers you do not mark good are never learned."
            return ("Waiting for your approval (%d). approve N | approve all | reject N | reject all\n" % len(pend)
                    + "\n".join("[%d] %s" % (r["id"], r["text"][:230]) for r in pend[-8:]))
        if sub in ("approve", "reject"):
            which = "all" if arg.lower() == "all" else (int(arg) if arg.isdigit() else None)
            if which is None:
                return "Use: prog %s <number from prog review> or prog %s all" % (sub, sub)
            n = PA.approve_pending(root, which) if sub == "approve" else PA.reject_pending(root, which)
            return ("%d answer(s) %s." % (n, "learned as examples" if sub == "approve" else "discarded")) if n else "No such waiting answer."
        if sub == "teach":
            try:
                n = PA.add_lesson(root, arg, "fact")
                return "Learned (#%d). Gemma will see this when a question matches it." % n
            except Exception as e:
                return "Could not save: " + str(e)[:100]
        if sub == "lessons" and arg.lower() == "export":
            rows = [r for r in PA.list_lessons(root) if r["kind"] != "pending"]
            body = "\n".join("[%s] %s" % (r["kind"], r["text"]) for r in rows) or "No lessons yet."
            self._save_download("RAMBO_lessons.txt", body.encode("utf-8"), "text/plain")
            return "Saved %d lessons to Downloads as RAMBO_lessons.txt" % len(rows)
        if sub == "lessons":
            rows = PA.search_lessons(root, arg, 12) if arg else PA.list_lessons(root)[-12:]
            return ("Lessons (%d total):\n" % len(PA.list_lessons(root))
                    + "\n".join("[%d] (%s) %s" % (r["id"], r["kind"], r["text"][:160]) for r in rows)) if rows else "No lessons yet. Use: prog teach <fact>"
        if sub == "forget":
            return "Removed." if arg.isdigit() and PA.forget_lesson(root, int(arg)) else "Use: prog forget <number from prog lessons>"
        if sub == "good":
            last = getattr(self, "prog_last", None)
            if not last:
                return "Nothing to keep yet. Ask something first: prog ask ..."
            n = PA.add_lesson(root, "Example. Q: %s A: %s" % (last[0][:150], last[1][:450]), "example")
            try:
                PA.reject_pending(root, max([r["id"] for r in PA.list_pending(root)] + [0]))
            except Exception:
                pass
            return "Kept as an example (#%d). Similar questions will see it." % n
        if sub == "bad":
            self.prog_last = None
            return "Not saved. If you know the right fact, teach it: prog teach <fact>"
        if sub == "cloud":
            if arg.lower() in ("on", "yes", "enable"):
                self.cfg["prog_cloud"] = True
                return ("Cloud help is ON for this session. If local Gemma cannot answer, Gemini gets your question "
                        "plus up to ~7000 characters of findings. Not sent: the file. Secret-looking values and "
                        "emails are removed. You see a notice each time.")
            if arg.lower() in ("off", "no", "disable"):
                self.cfg["prog_cloud"] = False
                return "Cloud help is OFF. Everything stays on the phone."
            return "Cloud help is %s. Use: prog cloud on / off" % ("ON" if self.cfg.get("prog_cloud") else "OFF")
        if sub == "delete":
            try:
                if arg.lower() == "all":
                    PA.delete_all(root)
                    self.prog_cur = None
                    return "All analyzed files deleted. Lessons were kept (they are in prog lessons)."
                if not ws:
                    return "No file is loaded."
                PA.delete_all(root, ws)
                self.prog_cur = None
                return "Deleted the analysis of the current file."
            except Exception as e:
                return "Could not delete: " + str(e)[:120]
        if sub == "status":
            if not ws:
                return "No file loaded. Use: prog pick"
            i = PA.load_info(ws)
            return "Loaded: %s (%s, %d KB)" % (i["file_name"], i["kind"], i["size"] // 1024)
        if not ws:
            return "No file loaded yet. Use: prog pick"
        if sub == "report":
            save = arg.lower() == "save"

            def rep():
                i = PA.load_info(ws)
                body = PA.build_report(i)
                if save:
                    fname = "RAMBO_report_" + re.sub(r"[^A-Za-z0-9_.-]", "_", i["file_name"])[:50] + ".txt"
                    self._save_download(fname, body.encode("utf-8"), "text/plain")
                    return "Report saved to Downloads as " + fname
                return body
            return self._prog_async(rep, "Building the report...")
        if sub == "ask":
            if not arg:
                return "Use: prog ask <your question>"
            return self._prog_ask(arg)
        call = None
        if sub in ("summary", "info"):
            call = ("summarize_program", {})
        elif sub in ("imports", "libs"):
            call = ("list_imports", {"query": arg})
        elif sub in ("symbols", "functions", "funcs"):
            call = ("list_symbols", {"query": arg})
        elif sub == "strings" and arg:
            call = ("search_strings", {"query": arg})
        elif sub == "search" and arg:
            call = ("search_code", {"query": arg})
        elif sub == "function" and arg:
            call = ("show_function", {"name": arg})
        elif sub == "entries":
            call = ("list_entries", {"query": arg})
        elif sub == "source":
            nums = [int(x) for x in arg.split() if x.isdigit()]
            sargs = {}
            if nums:
                sargs["start"] = nums[0]
            if len(nums) > 1:
                sargs["end"] = nums[1]
            call = ("read_source", sargs)
        if call is not None:
            return self._prog_async(lambda: PA.run_tool(ws, call[0], call[1]), "Looking...")
        return "Unknown command. Say: prog help"

    # ----- documents (long text) -----

    def _doc_store(self):
        import gemmaboost as GB
        return GB.DocStore(os.path.join(self.user_data_dir, "docs.db"))

    def _doc_import(self, fd, name):
        import gemmaboost as GB
        try:
            with os.fdopen(fd, "rb") as f:
                raw = f.read(GB.MAX_DOC + 1)
            text = GB.read_any(raw[:GB.MAX_DOC], name)
            did, new = self._doc_store().add(name, text)
            i = self._doc_store().info(did)
            self._say(("Loaded " if new else "Already loaded ") + "%s: %d characters in %d parts. "
                      "Ask with: doc ask <question> | doc deep <question> | doc summary | doc outline" % (i[1], i[2], i[3])
                      + ("" if len(raw) <= GB.MAX_DOC else "\n(Only the first 6 MB was read.)"))
        except Exception as e:
            if e.__class__.__name__ != "BoostError":
                self.err("doc import", e)
            self._say("Could not read that document: " + str(e)[:150])

    def _doc_route(self, rest, sub, arg, GB):
        import proganalyze as PA
        if sub in ("pick", "import", "open", "load"):
            self._pick_file("doc")
            return "Choose a text, markdown, code or HTML file. It is read, not run."
        if sub in ("", "help"):
            self.add_msg(self.PROG_HELP, False)
            return "Help is above."
        st = self._doc_store()
        if sub == "list":
            rows = st.docs()
            cur = st.current()
            return "\n".join(("* " if r[0] == cur else "  ") + "%d  %s (%d chars)" % (r[0], r[1], r[2]) for r in rows) or "No documents. Use: doc pick"
        if sub == "use" and arg.isdigit():
            if st.info(int(arg)):
                st.set_current(int(arg))
                return "Now reading document %s." % arg
            return "No document with that number. Say: doc list"
        if sub == "delete":
            if arg.lower() == "all":
                st.delete()
                return "All documents deleted."
            did = int(arg) if arg.isdigit() else st.current()
            if did is None:
                return "No document to delete."
            st.delete(did)
            return "Deleted document %s." % did
        did = st.current()
        if did is None:
            return "No document loaded. Use: doc pick"
        llm = self._boost_llm()
        root = self._prog_root()
        if sub == "outline":
            rows = GB.outline(st, did)
            return "\n".join(rows) or "No headings found. The document is read as plain parts. Use: doc find TEXT"
        if sub == "find" and arg:
            hits = st.search(did, arg, 5)
            return "\n\n".join("[%d] %s" % (n, t[:350]) for n, t in hits) or "Nothing matches those words."
        if sub == "summary":
            def summ():
                return GB.summarize_long(llm, st, did, self._prog, lambda: False)
            return self._prog_async(summ, "Reading the document in parts. This takes a while on the phone...")
        deep = sub == "deep"
        question = arg if sub in ("ask", "deep") else rest
        if not question:
            return "Use: doc ask <question>"

        def ask():
            les = GB.lessons_block(PA.search_lessons(root, question, 3))
            use_deep = deep or GB.looks_hard(question)
            kbt = GB.kb_block(GB.kb_sections(self.user_data_dir), "reading " + question, 1, 700) if use_deep else ""
            steps = []
            if not use_deep:
                ans, warn, used = GB.answer_doc(llm, st, did, question, les)
                if warn and not ans.lower().startswith("not stated"):
                    use_deep = True
            if use_deep:
                ans, warn, used, steps = GB.deep_read(llm, st, did, question, les, kbt, self._prog)
            out = ans + "\n\n(from parts: %s)" % ", ".join(map(str, used))
            if steps:
                out += "\n(steps: " + "; ".join(steps) + ")"
            if warn:
                out += "\nCheck: " + "; ".join(warn)
            return out
        return self._prog_async(ask, "Searching the document..." + (" (deep read: several steps, slower)" if deep else ""))

    def _kb_route(self, rest, sub, arg, GB):
        secs = GB.kb_sections(self.user_data_dir)
        if sub in ("", "help"):
            return "Knowledge notes: kb QUESTION (search) | kb add TITLE: NOTE (save your own) | kb list (%d notes)" % len(secs)
        if sub == "list":
            return "\n".join("- " + t for t, _b in secs) or "No notes."
        if sub == "add":
            if ":" not in arg or len(arg.split(":", 1)[1].strip()) < 8:
                return "Use: kb add TITLE: the note text"
            title, body = arg.split(":", 1)
            GB.kb_add_note(self.user_data_dir, title, body)
            return "Saved. Gemma will search this note on later questions."
        hits = GB.kb_search(secs, rest, 3, 600)
        return "\n\n".join("%s\n%s" % (t, b) for t, b in hits) or "No notes match. Add one: kb add TITLE: NOTE"

    # ---------- v47: Gemma app agent (Gemma drives your apps; Gemini is an optional backup) ----------

    AGENT_HELP = ("Agent: Gemma operates your apps by reading the screen and tapping, one checked step at a time.\n"
                  "agent <task in plain words>   e.g. agent open YouTube and search lo-fi music\n"
                  "agent yes | agent no (answer a confirmation) | agent stop | agent status\n"
                  "agent cloud on | off (let Gemini help ONLY if Gemma gives unusable replies; sends scrubbed screen text)\n"
                  "agent stats (how often Gemma finished alone) | prog review / approve (teach it recipes that worked)\\n"
                  "Needs Accessibility ON for RAMBO AI (acc settings). It will not operate bank, wallet or password apps, "
                  "never types passwords or card numbers, and asks you before send, buy, delete, install and similar steps.")

    def _agent_phone(self):
        import appagent as AG
        app = self

        class P(object):
            def screen(s):
                short, full = app.acc_run("acc screen")
                if short.startswith(("Accessibility is OFF", "Accessibility code is not")):
                    raise AG.AgentError(short + " Say: acc settings, turn it on, then try again.")
                if not full:
                    m = re.search(r"app: (\S+)\)", short)
                    return (m.group(1) if m else ""), ""
                head, _, body = full.partition("\n")
                m = re.match(r"SCREEN \((.*)\)", head)
                return (m.group(1) if m else ""), body

            def open(s, name):
                return app.phone_action("open " + name)

            def do(s, act, arg):
                cmd = {"tap": "acc tap " + arg, "type": "acc type " + arg, "scroll": "acc scroll " + arg,
                       "back": "acc back", "home": "acc home"}.get(act)
                if cmd is None:
                    return True, "ok"
                short, _full = app.acc_run(cmd)
                return short.startswith(("Tapped", "Typed", "Scrolled", "Back", "Home")), short

            def resume(s, pkg):
                from jnius import autoclass
                act = autoclass("org.kivy.android.PythonActivity").mActivity
                i = act.getPackageManager().getLaunchIntentForPackage(pkg)
                if i is not None:
                    act.startActivity(i)
        return P()

    def _agent_llm(self):
        def llm(sysm, user):
            try:
                return gemma_chat(sysm, user, max_tokens=220, want_json=True, timeout=120)
            except Exception:
                return gemma_chat(sysm, user, max_tokens=220, timeout=120)
        return llm

    def _agent_cloud(self):
        if not (self.cfg.get("agent_cloud") and self.gem_ok()):
            return None
        import proganalyze as PA

        def fb(sysm, user):
            body = json.dumps({"systemInstruction": {"parts": [{"text": sysm}]},
                               "contents": [{"role": "user", "parts": [{"text": PA.scrub(user)}]}]}).encode()
            code, raw = gemini_try(self.gem_key(), body)
            if code != 200:
                raise Exception("Gemini %s" % code)
            return json.loads(raw)["candidates"][0]["content"]["parts"][0]["text"]
        return fb

    def _agent_stat(self, status, fallbacks):
        p = os.path.join(self._prog_root(), "agent_stats.json")
        try:
            d = json.load(open(p))
        except Exception:
            d = {}
        d["runs"] = d.get("runs", 0) + 1
        d[status] = d.get(status, 0) + 1
        d["cloud_steps"] = d.get("cloud_steps", 0) + fallbacks
        try:
            json.dump(d, open(p, "w"))
        except Exception:
            pass

    def _agent_start(self, task, pid=None):
        if getattr(self, "agent_busy", False):
            return "An agent task is already running. Say: agent stop"
        self.agent_busy = True
        self.agent_cancel = False
        self.agent_wait = None

        def confirm(reason):
            if pid is not None:
                return False
            ev = threading.Event()
            self.agent_wait = {"ev": ev, "ans": False}
            self._say("Confirm: I want to " + reason + ". Say: agent yes or agent no (waiting 2 minutes).")
            try:
                self.notify("RAMBO AI", "Confirm needed: " + reason[:80])
            except Exception:
                pass
            ev.wait(120)
            ans = bool(self.agent_wait and self.agent_wait["ans"])
            self.agent_wait = None
            return ans

        def say(m):
            if pid is not None:
                try:
                    self.db.add_plog(pid, "run", "agent: " + m)
                except Exception:
                    pass
            else:
                self._prog(m)

        def work():
            try:
                import appagent as AG
                import gemmaboost as GB
                import proganalyze as PA
                root = self._prog_root()
                rows = [r for r in PA.search_lessons(root, task, 6) if "Recipe for" in r["text"]][:2]
                rec = ("STEPS THAT WORKED BEFORE (approved by the user):\n" + "\n".join("- " + r["text"][:300] for r in rows) + "\n\n") if rows else ""
                kbt = GB.kb_block(GB.kb_sections(self.user_data_dir), "operating apps flows " + task, 2, 700)
                res = AG.run_agent(task, self._agent_llm(), self._agent_phone(), say, confirm,
                                   lambda: self.agent_cancel, rec, kbt, self._agent_cloud())
                self._agent_stat(res["status"], res.get("fallbacks", 0))
                out = res["answer"]
                if res["steps"]:
                    out += "\n(%d steps%s)" % (len(res["steps"]), ", Gemini helped %d time(s)" % res["fallbacks"] if res.get("fallbacks") else ", Gemma only")
                if res["status"] == "done" and res["steps"]:
                    try:
                        PA.add_pending(root, "agent: " + task, AG.recipe_text(task, res["steps"]))
                        out += "\nIf this worked well: prog review, then prog approve N, so I can reuse the steps."
                    except Exception:
                        pass
                if pid is not None:
                    self.db.add_plog(pid, "run", "agent result (" + res["status"] + "): " + out[:600])
                else:
                    self._say(out)
            except Exception as e:
                self.err("agent", e)
                msg = "Agent error: " + str(e)[:200]
                if pid is not None:
                    try:
                        self.db.add_plog(pid, "run", msg)
                    except Exception:
                        pass
                else:
                    self._say(msg)
            finally:
                self.agent_busy = False
        threading.Thread(target=work, daemon=True).start()
        return "On it. I will read the screen and work step by step. Say: agent stop to cancel."

    def agent_route(self, text, low):
        if not (low == "agent" or low.startswith("agent ")):
            return None
        rest = text[5:].strip()
        sub = rest.lower()
        if sub in ("", "help"):
            self.add_msg(self.AGENT_HELP, False)
            return "Agent help is above."
        if sub == "stop":
            self.agent_cancel = True
            w = getattr(self, "agent_wait", None)
            if w:
                w["ev"].set()
            return "Stopping after the current step."
        if sub in ("yes", "no", "y", "n"):
            w = getattr(self, "agent_wait", None)
            if not w:
                return "Nothing is waiting for confirmation."
            w["ans"] = sub in ("yes", "y")
            w["ev"].set()
            return "Okay." if w["ans"] else "Okay, I will not do that."
        if sub == "status":
            return "An agent task is running." if getattr(self, "agent_busy", False) else "No agent task is running."
        if sub.startswith("cloud"):
            arg = sub[5:].strip()
            if arg in ("on", "yes"):
                self.cfg["agent_cloud"] = True
                return ("Gemini backup is ON for the agent. It is used only when Gemma gives two unusable replies in a row. "
                        "Then the task, the current app name and the visible screen text (secret-looking values removed) are sent to Gemini.")
            if arg in ("off", "no"):
                self.cfg["agent_cloud"] = False
                return "Gemini backup is OFF. The agent uses Gemma only; nothing leaves the phone."
            return "Gemini backup is %s. Use: agent cloud on / off" % ("ON" if self.cfg.get("agent_cloud") else "OFF")
        if sub == "stats":
            try:
                d = json.load(open(os.path.join(self._prog_root(), "agent_stats.json")))
            except Exception:
                return "No agent runs yet."
            return ("Agent runs: %d | finished: %d | asked you: %d | stopped by safety: %d | stuck: %d | Gemini steps used: %d"
                    % (d.get("runs", 0), d.get("done", 0), d.get("ask", 0), d.get("blocked", 0) + d.get("declined", 0),
                       d.get("stuck", 0) + d.get("limit", 0), d.get("cloud_steps", 0)))
        return self._agent_start(rest)

    # ----- Gemma booster -----

    def _boost_route(self, sub, GB, PA):
        root = self._prog_root()
        if sub == "eval":
            def run():
                llm = self._boost_llm()
                a = GB.run_eval(llm, False)
                b = GB.run_eval(llm, True)
                sa, sb = sum(1 for x in a if x[1]), sum(1 for x in b if x[1])
                hist = GB.save_eval(root, "plain", sa, len(a))
                hist = GB.save_eval(root, "scaffold", sb, len(b))
                lines = ["Reading test (%d questions with known answers)" % len(a),
                         "Plain Gemma: %d/%d" % (sa, len(a)), "Gemma with the booster prompt: %d/%d" % (sb, len(b)), ""]
                for (q, ok1, a1), (_q, ok2, a2) in zip(a, b):
                    lines.append("%s | plain %s | booster %s" % (q[:45], "ok" if ok1 else "MISS", "ok" if ok2 else "MISS"))
                lines.append("\nThis is a small test, so treat it as a rough signal. Run it again after changing "
                             "models or settings to compare.")
                return "\n".join(lines)
            return self._prog_async(run, "Running the reading test (12 short questions)...")
        if sub == "status":
            n = len(PA.list_lessons(root))
            return ("Booster: document index, deep reading (widen words, extract, answer, check, repair), "
                    "knowledge notes, tool loop, %d approved lessons. Say: boost eval to measure it." % n)
        return ("Ways to make a small model read better, in order of effect: 1) use a bigger or newer Gemma "
                "build if your phone can run it (check the model file name in Termux), 2) give it less text at a "
                "time: doc pick then doc ask (it searches the document and shows only the best parts), 3) teach "
                "it facts with prog teach, 4) keep answers checked: it flags quotes and numbers that are not in "
                "the source, 5) run boost eval after any change to see if it helped.")

    # ---------- actions from buttons ----------

    def on_send(self, instance):
        text = self.msg_input.text.strip()
        self.msg_input.text = ""
        self.convo_active = False
        if getattr(self, "attach", None):
            self._send_attach(text)
            return
        if text:
            self.handle(text, False)

    def on_mic(self, instance):
        try:
            if self.tts is not None and self.tts_ok:
                self.tts.stop()
        except Exception:
            pass
        self.voice_target = None
        self.convo_active = bool(self.cfg.get("convo"))
        self.listen()

    def add_task(self, instance):

        task = self.task_input.text.strip()

        if task:

            self.db.add_task(task)

            self.db.log(
                f"Task added: {task}"
            )

            self.task_input.text = ""

            self.refresh()

    def add_finance(self, instance):

        try:
            amount = float(
                self.finance_amount.text
            )
        except ValueError:
            self.db.log(
                "Invalid financial amount."
            )
            self.refresh()
            return

        description = (
            self.finance_description.text.strip()
        )

        category = (
            self.finance_category.text.strip()
        )

        self.db.add_finance(
            description,
            amount,
            category
        )

        self.db.log(
            f"Finance entry added: ${amount:.2f}"
        )

        self.finance_description.text = ""
        self.finance_amount.text = ""
        self.finance_category.text = ""

        self.refresh()

    def queue_email(self, instance):

        recipient = self.email_to.text.strip()
        subject = self.email_subject.text.strip()
        body = self.email_body.text

        if recipient and subject:

            self.db.queue_email(
                recipient,
                subject,
                body
            )

            self.db.log(
                f"Email queued for {recipient}"
            )

            self.email_to.text = ""
            self.email_subject.text = ""
            self.email_body.text = ""

            self.refresh()

    def daily_report(self, instance):

        self.backend.daily_report()

        self.refresh()

    def queue_youtube(self, instance):

        url = self.youtube_url.text.strip()
        comment = self.youtube_comment.text.strip()

        if url and comment:

            self.db.queue_youtube(
                url,
                comment
            )

            self.db.log(
                "YouTube comment queued."
            )

            self.youtube_url.text = ""
            self.youtube_comment.text = ""

            self.refresh()

    def check_website(self, instance):

        url = self.website_url.text.strip()

        if url:

            self.backend.check_website(url)

            self.refresh()

    def phone_action(self, text):
        try:
            from jnius import autoclass
        except Exception:
            return "not on Android"
        try:
            PA = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            AlarmClock = autoclass("android.provider.AlarmClock")
            act = PA.mActivity
            verb, _, arg = text.strip().partition(" ")
            verb = verb.lower()
            arg = arg.strip()
            apps = {
                "youtube": "com.google.android.youtube",
                "gmail": "com.google.android.gm",
                "chrome": "com.android.chrome",
                "maps": "com.google.android.apps.maps",
                "camera": "com.android.camera",
                "settings": "com.android.settings",
                "tiktok": "com.zhiliaoapp.musically",
                "claude": "com.anthropic.claude",
                "chatgpt": "com.openai.chatgpt",
                "grok": "ai.x.grok",
            }
            if verb == "open":
                key = arg.lower()
                rest = ""
                first = key.split(" ")[0] if key else key
                if key not in apps and first in apps:
                    key = first
                    parts = arg.split(None, 1)
                    rest = parts[1] if len(parts) > 1 else ""
                if key in apps:
                    i = act.getPackageManager().getLaunchIntentForPackage(apps[key])
                    if i is not None and rest:
                        try:
                            try:
                                from kivy.core.clipboard import Clipboard
                                Clipboard.copy(rest)
                            except Exception:
                                pass
                            si = Intent(Intent.ACTION_SEND)
                            si.setType("text/plain")
                            si.putExtra(Intent.EXTRA_TEXT, rest)
                            si.setPackage(apps[key])
                            act.startActivity(si)
                            return "sent your question to " + key + " (also copied)"
                        except Exception:
                            pass
                    if i is not None:
                        act.startActivity(i)
                        if rest:
                            try:
                                from kivy.core.clipboard import Clipboard
                                Clipboard.copy(rest)
                                return "opened " + key + ". Your question is copied, paste it."
                            except Exception:
                                pass
                        return "opened " + key
                if "." not in key and "://" not in key:
                    pm = act.getPackageManager()
                    for ai in pm.getInstalledApplications(0).toArray():
                        label = str(pm.getApplicationLabel(ai))
                        if key in label.lower():
                            li = pm.getLaunchIntentForPackage(ai.packageName)
                            if li is not None:
                                act.startActivity(li)
                                return "opened " + label
                    return "no app named " + key
                url = arg if "://" in arg else "https://" + arg
                act.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                return "opened " + url
            if verb == "search":
                url = "https://www.google.com/search?q=" + Uri.encode(arg)
                act.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                return "searched " + arg
            if verb == "call":
                act.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + arg)))
                return "dialing " + arg
            if verb == "text":
                num, _, msg = arg.partition(" ")
                i = Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + num))
                i.putExtra("sms_body", msg)
                act.startActivity(i)
                return "text ready for " + num
            if verb == "timer":
                secs = int(float(arg) * 60)
                i = Intent(AlarmClock.ACTION_SET_TIMER)
                i.putExtra(AlarmClock.EXTRA_LENGTH, secs)
                i.putExtra(AlarmClock.EXTRA_SKIP_UI, True)
                try:
                    act.startActivity(i)
                except Exception:
                    i2 = Intent(AlarmClock.ACTION_SET_TIMER)
                    i2.putExtra(AlarmClock.EXTRA_LENGTH, secs)
                    act.startActivity(i2)
                return "timer set " + arg + " min"
            if verb == "alarm":
                h, m = arg.split(":")
                i = Intent(AlarmClock.ACTION_SET_ALARM)
                i.putExtra(AlarmClock.EXTRA_HOUR, int(h))
                i.putExtra(AlarmClock.EXTRA_MINUTES, int(m))
                i.putExtra(AlarmClock.EXTRA_SKIP_UI, True)
                act.startActivity(i)
                return "alarm set " + arg
            return "unknown command. Try: open, search, call, text, timer, alarm"
        except Exception as e:
            return "error: " + str(e)

    def listen(self):
        try:
            from jnius import autoclass
            from android import activity
            PA = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            RS = autoclass("android.speech.RecognizerIntent")
            i = Intent(RS.ACTION_RECOGNIZE_SPEECH)
            i.putExtra(RS.EXTRA_LANGUAGE_MODEL, RS.LANGUAGE_MODEL_FREE_FORM)
            i.putExtra(RS.EXTRA_PROMPT, "Listening...")
            activity.unbind(on_activity_result=self.on_speech)
            activity.bind(on_activity_result=self.on_speech)
            PA.mActivity.startActivityForResult(i, 4242)
        except Exception as e:
            self.convo_active = False
            self.err("mic", e)
            self.add_msg("Mic error: " + str(e)[:150], False)

    def on_speech(self, request, result, data):
        if request != 4242:
            return
        if result != -1 or data is None:
            self.convo_active = False
            return
        try:
            from jnius import autoclass
            RS = autoclass("android.speech.RecognizerIntent")
            said = str(data.getStringArrayListExtra(RS.EXTRA_RESULTS).get(0)).strip()
        except Exception as e:
            self.convo_active = False
            Clock.schedule_once(lambda dt: self.err("speech result", e), 0)
            return
        cb = self.voice_target
        self.voice_target = None
        if cb is not None:
            Clock.schedule_once(lambda dt: cb(said), 0)
            return
        Clock.schedule_once(lambda dt: self.handle(said, True), 0)

    # ---------- brain: local first, Gemini second ----------

    def handle(self, text, voice=False):
        text = text.strip()
        if not text:
            return
        low = text.lower().strip().rstrip(".!?")

        if low.startswith("setkey "):
            try:
                with open(self.key_path, "w") as f:
                    f.write(text[7:].strip())
                self.add_msg("setkey ****", True)
                self.reply("Key saved on this phone. Ask me anything.")
            except Exception as e:
                self.err("setkey", e)
                self.reply("Could not save the key.")
            return

        self.add_msg(text, True)
        self.hide_chips()
        try:
            self.db.add_chat("user", text)
        except Exception as e:
            self.err("chat save", e)
        self.hist.append(("user", text))
        self.hist = self.hist[-12:]

        if low in ("stop", "stop listening", "cancel", "goodbye",
                   "that's all", "thats all", "never mind", "nevermind"):
            self.convo_active = False
            self.reply("Okay.")
            return

        if low in ("approve", "approve it", "yes run it"):
            self._v72_approve()
            return
        if low.startswith("termux "):
            self._v72_chat_cmd(text[7:].strip())
            return
        if re.match(r"^(error logs?|show (the )?(errors?|logs?)|logs?|errors?)$", low):
            self._v73_logs()
            return
        if low.startswith("setexec "):
            try:
                _t = text.split(None, 1)[1].strip()
                with open(os.path.join(self.user_data_dir, "exec.token"), "w") as _f:
                    _f.write(_t)
                self.reply("Token saved. Now type: execstatus")
            except Exception as e:
                self.reply("Could not save the token: " + str(e)[:100])
            return
        if low == "execstatus":
            self._v72_bg("pwd && echo exec server ok")
            return
        if low in ("termuxperm", "termux perm", "termux status"):
            self._v73_perm()
            return
        try:
            self._v75_install()
        except Exception:
            pass
        if low in ("stop goal", "cancel goal") or (getattr(self, "_v78_on", False) and low in ("stop", "stop task", "stop auto running", "stop running", "cancel")):  # V79_STOPFIX
            self._v75_stop = True
            self._v78_on = False
            _ev = getattr(self, "_v75_ev_ok", None)
            if _ev is not None:
                _ev.set()
            self.reply("Stopping the goal.")
            return
        if low.startswith("goal ") or low.startswith("goal:"):
            self._v75_goal(re.sub(r"^goal\s*:?\s*", "", text, flags=re.I))
            return
        if low in ("save", "save this", "save to memory"):  # ASK_FIRST_V63
            self.save_last_mem()
            return
        try:
            r_rb = self._rb_cmd(text)
        except Exception as e:
            self.err("ask first v63", e)
            r_rb = "Could not open the app: " + str(e)[:150]
        if r_rb is not None:
            self.reply(r_rb)
            return
        force_ai = False
        if low.startswith(("ask ", "do ")):
            text = text.split(" ", 1)[1].strip()
            low = text.lower()
            force_ai = True

        if not force_ai:
            try:
                r = self.local_route(text, low)
            except Exception as e:
                self.err("route", e)
                r = None
            if r is not None:
                self.reply(r)
                return
        self.ask_gemini(text)

    def pa(self, cmd):
        res = self.phone_action(cmd)
        self.db.log("Phone: " + cmd + " -> " + res)
        return res[:1].upper() + res[1:]

    # ---------- accessibility (see the screen, tap, type) ----------

    def acc_route(self, text, low):
        m = re.match(r"^in\s+(\d{1,3})\s+(acc(?:\s.*)?)$", text, re.I)
        if m:
            secs = int(m.group(1))
            inner = m.group(2)

            def later():
                time.sleep(secs)
                try:
                    short, full = self.acc_run(inner)
                except Exception as e:
                    short, full = "acc error: " + str(e)[:120], None
                shown = full or short

                def post(dt):
                    self.add_msg(shown, False)
                    try:
                        self.notify("RAMBO AI", short[:100])
                    except Exception:
                        pass
                Clock.schedule_once(post, 0)

            threading.Thread(target=later, daemon=True).start()
            return "Okay. Running " + inner + " in %d seconds. Switch to the other app now." % secs
        if low == "acc" or low.startswith("acc "):
            short, full = self.acc_run(text)
            if full:
                self.add_msg(full, False)
            return short
        return None

    def acc_run(self, text):
        body = text.strip()[3:].strip()
        low = body.lower()
        try:
            from jnius import autoclass
            S = getattr(self, "_v81_S", None) or autoclass("org.rambo.acc.RamboAccService")  # V81_CLS
            self._v81_S = S
        except Exception as e:
            return ("Accessibility code is not in this build.", None)
        if low in ("", "help"):
            return (ACC_HELP, None)
        if low == "settings":
            PA = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            Settings = autoclass("android.provider.Settings")
            PA.mActivity.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            return ("Opened Accessibility settings. Find RAMBO AI and turn it on.", None)
        on = bool(S.isOn())
        if low == "status":
            return ("Accessibility is ON." if on else
                    "Accessibility is OFF. Say: acc settings, then turn on RAMBO AI.", None)
        if not on:
            return ("Accessibility is OFF. Say: acc settings, then turn on RAMBO AI.", None)
        if low == "screen":
            s = str(S.screenText() or "").strip()
            pkg = str(S.currentPackage() or "?")
            if not s:
                return ("Screen read came back empty (app: " + pkg + ").", None)
            n = len(s.splitlines())
            return ("Read %d lines from %s." % (n, pkg), "SCREEN (" + pkg + ")\n" + s[:3500])
        if low.startswith("tapxy "):
            p = body[6:].split()
            if len(p) != 2 or not all(x.isdigit() for x in p):
                return ("Use: acc tapxy 500 900", None)
            ok = bool(S.tap(int(p[0]), int(p[1])))
            return ("Tapped." if ok else "Tap failed.", None)
        if low.startswith("tap "):
            t = body[4:].strip()
            ok = bool(S.clickText(t))
            return (("Tapped " + t + ".") if ok else ("Could not find " + t + " on screen."), None)
        if low.startswith("type "):
            ok = bool(S.typeText(body[5:]))
            return ("Typed." if ok else "No text box found on screen.", None)
        if low.startswith("clip "):
            ok = bool(S.setClip(body[5:]))
            return ("Copied to clipboard." if ok else "Clipboard failed.", None)
        if low == "paste":
            ok = bool(S.pasteText())
            return ("Pasted." if ok else "Paste failed (no text box found).", None)
        if low in ("scroll down", "scroll up"):
            ok = bool(S.scroll(low == "scroll down"))
            return ("Scrolled." if ok else "Nothing to scroll.", None)
        if low == "back":
            return ("Back." if bool(S.back()) else "Back failed.", None)
        if low == "home":
            return ("Home." if bool(S.home()) else "Home failed.", None)
        return ("Unknown acc command. Say: acc help", None)

    def local_route(self, text, low):
        try:  # ASK_FIRST_V62
            r_first = self._rb_cmd(text)
        except Exception as e:
            self.err('ask first', e)
            r_first = 'Could not open the app: ' + str(e)[:150]
        if r_first is not None:
            return r_first
        try:
            self._auto_learn(text, low)
        except Exception as e:
            self.err("learn", e)
        if low in ("learning off", "stop learning", "learning on", "start learning"):
            self.cfg["learn"] = low in ("learning on", "start learning")
            self.save_settings()
            return "Auto-learning is " + ("ON." if self.cfg["learn"] else "OFF.")
        if low in ("forget last", "forget the last one", "undo remember"):
            gone = self.db.forget_last()
            return ("Forgot: " + gone) if gone else "Nothing to forget."
        try:
            r_ag = self.agent_route(text, low)
        except Exception as e:
            self.err("agent route", e)
            r_ag = "Agent error: " + str(e)[:150]
        if r_ag is not None:
            return r_ag
        try:
            r_prog = self.prog_route(text, low)
        except Exception as e:
            self.err("prog route", e)
            r_prog = "Program Analyzer error: " + str(e)[:150]
        if r_prog is not None:
            return r_prog
        try:
            r_apk = self.apk_route(text, low)
        except Exception as e:
            self.err("apk route", e)
            r_apk = "APK Analyzer error: " + str(e)[:150]
        if r_apk is not None:
            return r_apk
        r_acc = self.acc_route(text, low)
        if r_acc is not None:
            return r_acc
        if low.startswith("pc:"):
            self.db.add_job("pc", text[3:].strip())
            return "Queued for the PC. Nothing delivers PC jobs yet."

        m = re.match(r"^remember(?: that)?\s+(.+)$", text, re.I)
        if m:
            self.db.add_memory(m.group(1).strip())
            return "Got it. I will remember: " + m.group(1).strip()
        m = re.match(r"^forget(?: that| about)?\s+(.+)$", text, re.I)
        if m:
            n = self.db.forget(m.group(1).strip())
            return ("Forgot %d item(s)." % n) if n else "I had nothing saved matching that."
        if low in ("memories", "what do you remember", "what do you know about me",
                   "what do you remember about me", "list memories"):
            facts = self.db.memories()
            return ("I remember: " + "; ".join(facts)) if facts else "I have nothing saved yet. Say: remember ..."
        if low in ("help", "what can you do", "commands"):
            return HELP
        if low in ("test", "self test", "run tests", "test everything"):
            return self.run_tests()
        if low == "backup":
            return self.do_backup()
        if low == "restore":
            return self.do_restore()
        if low == "errors":
            rows = self.db.errors()
            if not rows:
                return "No errors logged."
            return "\n".join(r[0][5:16].replace("T", " ") + " " + r[1][:110] for r in rows)
        if low == "clear chat":
            self.db.clear_chat()
            self.chat_box.clear_widgets()
            self.hist = []
            return "Chat cleared."

        if low in ("what time is it", "what's the time", "whats the time",
                   "time", "current time", "what time is it now"):
            return "It is " + datetime.now().strftime("%I:%M %p").lstrip("0")
        if low in ("what is the date", "what's the date", "whats the date",
                   "what day is it", "what is today", "what's today",
                   "what is the date today", "what's the date today"):
            return "Today is " + datetime.now().strftime("%A, %B %d, %Y")

        m = re.match(r"^(?:add task|new task|add a task|remind me to)\s+(?:to\s+)?(.+)$", text, re.I)
        if m:
            self.db.add_task(m.group(1).strip())
            return "Task added: " + m.group(1).strip()
        if low in ("show my tasks", "list tasks", "list my tasks", "my tasks",
                   "what are my tasks", "show tasks"):
            t = self.db.list_tasks()
            return ("Your tasks: " + "; ".join(t)) if t else "You have no tasks."
        if low in ("how much have i spent", "finance total", "my finances",
                   "show my finances", "how much did i spend"):
            return "Your finance total is $%.2f" % self.db.finance_total()

        m = re.match(r"^(?:open|launch)\s+youtube[,\s]+(?:and\s+)?(?:then\s+)?(?:search|find)(?:\s+for)?(?:\s+on\s+youtube)?\s+(.+?)[,\s]+(?:and\s+)?(?:then\s+)?(?:play|watch|click)\b.*$", low)
        if m:
            return self.yt_play(m.group(1))
        m = (re.match(r"^(?:open|launch|go to)\s+youtube\s+and\s+(?:play|watch)\s+(.+)$", low)
             or re.match(r"^(?:play|watch)\s+(.+?)(?:\s+on youtube)?$", low))
        if m:
            return self.yt_play(m.group(1))
        m = re.match(r"^(?:open|launch|go to)\s+(.+?)\s+and\s+(play|search(?: for)?|look up|find|show me|show|google|watch)\s+(.+)$", low)
        if m:
            app, verb, q = m.group(1), m.group(2), m.group(3)
            if "youtube" in app or verb in ("play", "watch"):
                return self.pa("open https://www.youtube.com/results?search_query=" + quote(q))
            return self.pa("search " + q)
        m = re.match(r"^(?:play|watch)\s+(.+)$", low)
        if m:
            return self.pa("open https://www.youtube.com/results?search_query=" + quote(m.group(1)))
        # open X and search Y
        m = re.match(r"^(?:open|launch)\s+(.+?)\s+and\s+(?:search|look up|google)(?:\s+for)?\s+(.+)$", low)
        if m:
            app, q = m.group(1), m.group(2)
            if "youtube" in app:
                return self.pa("open https://www.youtube.com/results?search_query=" + quote(q))
            return self.pa("search " + q)
        m = (re.match(r"^(?:search|find)\s+(?:youtube\s+for|on youtube for)\s+(.+)$", low)
             or re.match(r"^search\s+(.+?)\s+on youtube$", low)
             or re.match(r"^play\s+(.+?)\s+on youtube$", low))
        if m:
            return self.pa("open https://www.youtube.com/results?search_query=" + quote(m.group(1)))

        # timers and alarms
        if "timer" in low and len(low.split()) <= 9:
            m = re.search(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)", low)
            if m:
                n = float(m.group(1))
                u = m.group(2)
                mins = n * 60 if u.startswith("h") else (n / 60.0 if u.startswith("s") else n)
                return self.pa("timer " + str(mins))
            m = re.match(r"^timer\s+(\d+(?:\.\d+)?)$", low)
            if m:
                return self.pa("timer " + m.group(1))
        m = re.match(r"^(?:set\s+)?(?:an?\s+)?alarm(?:\s+(?:for|at))?\s+(\d{1,2})(?::(\d{2}))?\s*([ap])?\.?m?\.?$", low)
        if m:
            h = int(m.group(1))
            mi = int(m.group(2) or 0)
            ap = m.group(3)
            if ap == "p" and h < 12:
                h += 12
            if ap == "a" and h == 12:
                h = 0
            if h > 23 or mi > 59:
                return "That time does not look right."
            return self.pa("alarm %02d:%02d" % (h, mi))

        m = re.match(r"^(?:open|launch)\s+(.+)$", text, re.I)
        if m:
            return self.pa("open " + m.group(1).strip())
        m = re.match(r"^(?:search|google|look up)\s+(?:for\s+)?(.+)$", text, re.I)
        if m:
            return self.pa("search " + m.group(1).strip())
        m = re.match(r"^call\s+([\d\s\-\+\(\)]{5,})$", text, re.I)
        if m:
            return self.pa("call " + m.group(1).strip())
        m = re.match(r"^text\s+([\d\+\-\(\)]{5,})\s+(.+)$", text, re.I)
        if m:
            return self.pa("text " + m.group(1) + " " + m.group(2))
        return None

    def _rb_needs_gemini(self, low):
        try:
            if not self.gem_ok():
                return False
        except Exception:
            return False
        try:
            if needs_live(low):
                return True
        except Exception:
            pass
        keys = ("python", "script", "debug", "write code", "write a program",
                "research", "regex", "javascript", "html", "sql")
        return any(k in low for k in keys)

    def ask_gemini(self, text):
        try:
            low = text.lower().strip()
            words = ("code", "script", "write ", "essay", "research", "analy",
                     "compare", "in detail", "plan ", "translate", "summar",
                     "debug", "calculate", "step by step")
            rc = self._rb_cmd(text)
            if rc:
                self.reply(rc)
                return
            qt = self._quick_time(text)
            if qt:
                self.reply(qt)
                return
            mg = re.match(r"^setgroq\s+(\S+)$", text.strip(), re.I)
            if mg:
                self.reply(_groq_save(self.user_data_dir, mg.group(1)))
                return
            qc = self._quick_calc(text)
            if qc:
                self.reply(qc)
                return
            hard = low.startswith("gemini") or len(text) > 1500 or self._rb_needs_gemini(low)
            if hard or not self.cfg.get("local", True):
                self._ask_cloud(text)
                return
            msgs = []
            for role, t in self.hist[-2:]:
                if not msgs and role != "user":
                    continue
                msgs.append({"role": "assistant" if role == "model" else "user", "content": t[:200]})
            if not msgs or msgs[-1]["role"] != "user":
                msgs.append({"role": "user", "content": text})
            merged = []
            for m in msgs:
                if merged and merged[-1]["role"] == m["role"]:
                    merged[-1] = {"role": m["role"],
                                  "content": merged[-1]["content"] + chr(10) + m["content"]}
                else:
                    merged.append(m)
            msgs = merged
            self.flash("Thinking on the phone...")
            try:
                facts = self.db.memories()
                notes = self.db.notes_search(text)
            except Exception:
                facts, notes = [], []
            threading.Thread(target=self._local_thread,
                             args=(text, msgs, facts, notes), daemon=True).start()
        except Exception as e:
            self.err("local route", e)
            self._ask_cloud(text)

    def _local_thread(self, text, msgs, facts=(), notes=()):
        out, err = "", ""
        try:
            import urllib.request
            sp = ("You are RAMBO AI, a smart, friendly assistant on the user's Android phone. "
                  ""
                  "If you are not sure, say so instead of guessing. ")
            if facts:
                sp += "Known facts about the user: " + "; ".join(facts) + ". "
            if notes:
                sp += ("Saved reference notes you wrote earlier. Use them when relevant and do not contradict them: "
                       + " || ".join(n[:300] for n in list(notes)[:2]) + " ")
            try:
                import gemmaboost as GB
                kbt = GB.kb_block(GB.kb_sections(self.user_data_dir), text, 1, 300)
                if kbt:
                    sp += " " + kbt
            except Exception:
                pass
            sp += _rp_extra(text)
            sysm = {"role": "system", "content": sp}
            body = json.dumps({"messages": [sysm] + msgs, "max_tokens": 250,
                                    "chat_template_kwargs": {"enable_thinking": False}}).encode()
            bd = json.loads(body.decode())
            bd["stream"] = True
            rq = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
                                        data=json.dumps(bd).encode(), headers={"Content-Type": "application/json"})
            acc = ""
            lastu = 0.0
            with urllib.request.urlopen(rq, timeout=150) as r:
                for raw in r:
                    line = raw.decode("utf-8", "ignore").strip()
                    if not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        piece = json.loads(chunk)["choices"][0]["delta"].get("content") or ""
                    except Exception:
                        continue
                    acc += piece
                    now = time.time()
                    if now - lastu > 0.3:
                        lastu = now
                        shown = re.sub(r"<think>.*?(</think>|$)", "", acc, flags=re.S).strip()
                        if shown:
                            Clock.schedule_once(lambda dt, tt=shown: self._stream_show(tt), 0)
            out = acc.strip()
            if out.upper().startswith("ESCALATE"):  # ESCALATE_CLAUDE
                if self.gem_ok():
                    Clock.schedule_once(lambda dt: (self._stream_clear(), self._ask_cloud(text)), 0)
                else:
                    Clock.schedule_once(lambda dt: (self._stream_clear(), self.reply(self.rb_send("claude", text))), 0)
                return
            out = re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
        except Exception as e:
            err = str(e)
        Clock.schedule_once(lambda dt: self._local_done(text, out, err), 0)

    def _quick_calc(self, text):
        import ast
        import operator
        t = text.lower().strip().rstrip("?.! ")
        pre = False
        for p in ("what is ", "what's ", "whats ", "calculate ", "compute ", "how much is ", "solve "):
            if t.startswith(p):
                t = t[len(p):]
                pre = True
                break
        t = t.replace(",", "")
        e = " " + t + " "
        words = False
        for a, b in ((" multiplied by ", "*"), (" times ", "*"), (" divided by ", "/"), (" over ", "/"),
                     (" plus ", "+"), (" minus ", "-"), (" to the power of ", "**"), (" x ", "*")):
            if a in e:
                words = True
                e = e.replace(a, b)
        e = e.replace("^", "**").strip()
        m = re.match(r"^([0-9.]+)\s*%\s*of\s*([0-9.]+)$", e)
        if m:
            e = "(%s/100)*%s" % m.groups()
            words = True
        if not re.fullmatch(r"[0-9.+\-*/() ]+", e) or not re.search(r"[0-9]", e):
            return None
        if not (pre or words or re.search(r"[+*/]", e)):
            return None
        ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
               ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
               ast.UAdd: operator.pos}

        def ev(n):
            if isinstance(n, ast.Expression):
                return ev(n.body)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
                return n.value
            if isinstance(n, ast.BinOp) and type(n.op) in ops:
                a, b = ev(n.left), ev(n.right)
                if isinstance(n.op, ast.Pow) and abs(b) > 100:
                    raise ValueError("power too large")
                return ops[type(n.op)](a, b)
            if isinstance(n, ast.UnaryOp) and type(n.op) in ops:
                return ops[type(n.op)](ev(n.operand))
            raise ValueError("not maths")

        try:
            v = ev(ast.parse(e, mode="eval"))
        except Exception:
            return None
        if isinstance(v, float) and v == int(v) and abs(v) < 1e15:
            v = int(v)
        shown = str(v) if isinstance(v, int) else ("%.10g" % v)
        return t.strip() + " = " + shown

    def _stream_show(self, t):
        try:
            row = getattr(self, "_stream_row", None)
            if row is None:
                self.remove_thinking()
                self._stream_row = self.add_msg(t, False)
            else:
                row.children[0].text = t
            Clock.schedule_once(lambda dt: setattr(self.chat_scroll, "scroll_y", 0), 0.05)
        except Exception as e:
            self.err("stream", e)

    def _stream_clear(self):
        row = getattr(self, "_stream_row", None)
        self._stream_row = None
        if row is not None:
            try:
                self.chat_box.remove_widget(row)
            except Exception:
                pass

    def _local_done(self, text, out, err):
        self._stream_clear()
        if out:
            self.reply(out)
            return
        if err and "refused" not in err.lower():
            self.err("local", err[:150])
        self._ask_cloud(text)

    def _ask_cloud(self, text):
        try:
            with open(self.key_path) as f:
                key = f.read().strip()
        except Exception:
            key = ""
        if not key:
            self.reply("I need a Gemini key for that. Type: setkey YOUR_KEY")
            return
        self._last_cloud_text = text
        if time.time() < getattr(self, "gem_down_until", 0):
            self._gemma_only(text)
            return
        contents = []
        for role, t in self.hist[-8:]:
            if not contents and role != "user":
                continue
            contents.append({"role": role, "parts": [{"text": t}]})
        if not contents:
            contents = [{"role": "user", "parts": [{"text": text}]}]
        ap = getattr(self, "_att_once", None)
        if ap:
            contents[-1] = {"role": "user", "parts": list(ap) + [{"text": text}]}
        payload = {
            "systemInstruction": {"parts": [{"text": build_system(self.db.memories())}]},
            "contents": contents,
            "generationConfig": {"responseMimeType": "application/json"},
        }
        self.thinking = self.add_msg("...", False)
        body = json.dumps(payload).encode()
        threading.Thread(target=self._gemini_thread, args=(key, body), daemon=True).start()

    def _gemini_thread(self, key, body):
        code, raw, err = 0, "", ""
        try:
            code, raw = gemini_try(key, body)
        except Exception as e:
            err = str(e)
        Clock.schedule_once(lambda dt: self.on_gemini(code, raw, err), 0)

    def on_gemini(self, code, raw, err):
        if err:
            self.err("gemini net", err)
            self.reply("I could not reach Gemini. Check your connection.")
            return
        if code == 429:
            self.gem_mark_down()
            self._gemma_only(getattr(self, "_last_cloud_text", ""))
            return
        if code != 200:
            self.err("gemini " + str(code), raw[:150])
            self.reply("Gemini error " + str(code) + ": " + gem_msg(raw))
            return
        try:
            txt = json.loads(raw)["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            self.reply("Gemini gave no answer to that.")
            return
        self.gem_mark_up()
        reply_text, cmds = txt, []
        try:
            t2 = txt
            if t2.startswith("```"):
                t2 = re.sub(r"^```(?:json)?|```$", "", t2, flags=re.M).strip()
            d = json.loads(t2)
            if isinstance(d, dict):
                reply_text = str(d.get("reply", "")) or "Done."
                cmds = [str(c) for c in d.get("commands", [])][:5]
        except Exception:
            pass
        self.reply(reply_text)
        for n, c in enumerate(cmds):
            Clock.schedule_once(lambda dt, c=c: self.run_cmd(c), 1.5 + 1.5 * n)

    def run_cmd(self, c):
        try:
            if c.lower().startswith("play "):
                self.yt_play(c[5:])
                return
            res = self.phone_action(c)
            self.db.log("Phone: " + c + " -> " + res)
            self.add_msg("> " + c + ": " + res, False)
        except Exception as e:
            self.err("run_cmd", e)

    # ---------- backup / restore ----------

    def do_backup(self):
        s = json.dumps(self.db.export_all())
        done = []
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(s)
            done.append("copied to the clipboard")
        except Exception as e:
            self.err("clipboard", e)
        try:
            from jnius import autoclass
            PA = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            i = Intent(Intent.ACTION_SEND)
            i.setType("text/plain")
            i.putExtra(Intent.EXTRA_TEXT, s)
            PA.mActivity.startActivity(Intent.createChooser(i, "Save RAMBO AI backup"))
            done.append("opened the share sheet")
        except Exception as e:
            self.err("share", e)
        if not done:
            return "Backup failed. Type errors to see why."
        return ("Backup " + " and ".join(done)
                + ". Save it somewhere safe (Gmail draft, Keep or Drive). "
                  "To restore, copy that text and type restore.")

    def do_restore(self):
        try:
            from kivy.core.clipboard import Clipboard
            data = json.loads(Clipboard.paste())
            n = self.db.import_all(data)
            self.refresh()
            return "Restored %d items from the clipboard backup." % n
        except Exception as e:
            self.err("restore", e)
            return "I could not restore from the clipboard. Copy the backup text first."

    # ---------- lifecycle ----------

    def refresh(self):
        try:
            total = self.db.finance_total()
            tasks = self.db.task_count()
            emails = self.db.email_count()
            comments = self.db.youtube_count()
            self.dashboard.text = (
                f"TASKS: {tasks}     FINANCES: ${total:.2f}\n"
                f"EMAIL QUEUE: {emails}     YOUTUBE QUEUE: {comments}     "
                f"JOBS: {self.db.job_count()}")
            logs = self.db.recent_logs()
            if logs:
                lines = []
                for timestamp, message in logs:
                    lines.append(timestamp.replace("T", " ")[:16] + "\n" + message)
                self.log_output.text = "\n\n".join(lines)
            else:
                self.log_output.text = "No activity yet."
        except Exception as e:
            self.log_output.text = "Dashboard error: " + str(e)

    def on_start(self):
        self.init_tts()
        Clock.schedule_interval(
            lambda dt: threading.Thread(target=self.gem_probe, daemon=True).start(), 60)
        try:
            from android.permissions import request_permissions
            request_permissions(["android.permission.POST_NOTIFICATIONS"])
        except Exception:
            pass
        try:
            if CRASH_PATH[0] and os.path.exists(CRASH_PATH[0]):
                with open(CRASH_PATH[0]) as f:
                    txt = f.read()
                self.db.log("ERROR crash: " + txt[-180:].replace("\n", " "))
                os.remove(CRASH_PATH[0])
                self.add_msg("Heads up: the app hit an error last time. "
                             "Type errors to see it.", False)
        except Exception:
            pass
        said_now = self._rambo_assist_hook()
        if self.cfg.get("auto") and not said_now:
            Clock.schedule_once(lambda dt: self.on_mic(None), 2.5)

    # ---------- hold-button overlay hands us what you said ----------

    def _rambo_say_check(self, intent):
        try:
            if intent is None:
                return False
            txt = intent.getStringExtra("rambo_say")
            if not txt:
                return False
            txt = str(txt).strip()
            try:
                ts = int(intent.getLongExtra("rambo_ts", 0))
            except Exception:
                ts = 0
            try:
                intent.removeExtra("rambo_say")
            except Exception:
                pass
            if ts and abs(time.time() * 1000 - ts) > 60000:
                return False
            if txt == getattr(self, "_rs_last", None) and time.time() - getattr(self, "_rs_t", 0) < 5:
                return False
            self._rs_last, self._rs_t = txt, time.time()
            Clock.schedule_once(lambda dt: self.handle(txt, True), 0.6)
            return True
        except Exception as e:
            self.err("assist say", e)
            return False

    def _rambo_overlay(self):
        # show the listening card over whatever app you were in; plain mic if anything fails
        try:
            from jnius import autoclass
            PA = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            act = PA.mActivity
            i = Intent()
            i.setClassName(act.getPackageName(), "org.rambo.acc.AssistOverlayActivity")
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | 0x00010000 | 0x08000000 | 0x00800000)
            act.startActivity(i)
            Clock.schedule_once(lambda dt: act.moveTaskToBack(True), 0.35)
        except Exception as e:
            self.err("overlay", e)
            try:
                self.on_mic(None)
            except Exception:
                pass

    def _rambo_intent(self, intent):
        # hold button = ASSIST intent: open the mic right away
        try:
            if intent is None:
                return False
            if self._rambo_say_check(intent):
                return True
            act = intent.getAction()
            if act is None or str(act) != "android.intent.action.ASSIST":
                return False
            if int(intent.getFlags()) & 0x00100000:
                return False  # restored from recents, not a fresh hold
            if time.time() - getattr(self, "_as_t", 0) < 4:
                return False
            self._as_t = time.time()
            Clock.schedule_once(lambda dt: self._rambo_overlay(), 0.2)
            return True
        except Exception as e:
            self.err("assist intent", e)
            return False

    def _rambo_assist_hook(self):
        try:
            from jnius import autoclass
            from android import activity
            PA = autoclass("org.kivy.android.PythonActivity")
            activity.bind(on_new_intent=self._rambo_intent)
            return self._rambo_intent(PA.mActivity.getIntent())
        except Exception as e:
            self.err("assist hook", e)
            return False

    def on_pause(self):
        return True

    def on_stop(self):
        if hasattr(self, "db"):
            self.db.close()


if __name__ == "__main__":
    BusinessDashboard().run()
