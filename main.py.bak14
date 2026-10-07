__version__ = "1.3.6"
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
    s = ('You are Pocket Pal, a friendly voice assistant on the user\'s Android phone. '
         'Reply ONLY with JSON: {"commands": [], "reply": "what you say to the user"}. '
         'Keep the reply short and natural because it is spoken aloud. No markdown. '
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
    conn.setConnectTimeout(30000)
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


def mk_input(hint, multiline=False, height=45, **kw):
    return TextInput(input_type="text", keyboard_suggestions=(not multiline),
                     hint_text=hint, multiline=multiline,
                     size_hint_y=None, height=height, **style_in(kw))


class Bubble(Label):
    def __init__(self, mine=False, **kw):
        super().__init__(**kw)
        self.mine = mine
        self.size_hint_y = None
        self.halign = "left"
        self.valign = "middle"
        self.font_size = "17sp"
        with self.canvas.before:
            if mine:
                Color(0.0, 0.5, 0.7, 1)
            else:
                Color(0.17, 0.09, 0.32, 1)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[16])
        self.bind(pos=self._upd, size=self._upd,
                  width=self._tw, texture_size=self._th)

    def _tw(self, *a):
        self.text_size = (max(self.width - 24, 10), None)

    def _th(self, *a):
        self.height = self.texture_size[1] + 24

    def _upd(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size


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
        self.title = "Pocket Pal"
        Window.softinput_mode = "below_target"
        Window.clearcolor = BG
        os.makedirs(self.user_data_dir, exist_ok=True)
        CRASH_PATH[0] = os.path.join(self.user_data_dir, "crash.log")
        self.cfg_path = os.path.join(self.user_data_dir, "settings.json")
        self.key_path = os.path.join(self.user_data_dir, "gemini.key")
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
        self.auto_on = False
        self.auto_steps = 0

        root = BoxLayout(orientation="vertical", padding=6, spacing=6)
        self.body = BoxLayout()
        root.add_widget(self.body)
        self.flash_lbl = Label(text="Ready.", color=GREEN, font_size="13sp",
                               size_hint_y=None, height=26, shorten=True,
                               halign="center", valign="middle")
        self.flash_lbl.bind(size=lambda w, v: setattr(w, "text_size", v))
        root.add_widget(self.flash_lbl)
        bar = BoxLayout(size_hint_y=None, height=58, spacing=5)
        self.tab_btns = {}
        self.tab_views = {}
        tabs = [("TALK", self.build_chat, CYAN), ("PHONE", self.build_phone, GREEN),
                ("LOOKUP", self.build_lookup, AMBER), ("PROJECT", self.build_projects, MAGENTA),
                ("TASKS", self.build_tasks, GREEN),
                ("MORE", self.build_more, CYAN)]
        for name, fn, col in tabs:
            self.tab_views[name] = fn()
            b = NeonButton(glow=col, text=name, font_size="11sp")
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
        for n, b in self.tab_btns.items():
            b.set_active(n == name)

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
        b = NeonButton(glow=col, text=t, size_hint_y=None, height=h)
        b.bind(on_press=self._wrap(cb))
        c.add_widget(b)
        return b

    def _row(self, c, inp, label, cb, col=CYAN):
        r = BoxLayout(size_hint_y=None, height=48, spacing=6)
        r.add_widget(inp)
        b = NeonButton(glow=col, text=label, size_hint_x=0.32)
        b.bind(on_press=self._wrap(cb))
        r.add_widget(b)
        c.add_widget(r)

    # ---------- tabs ----------

    def build_chat(self):
        v = BoxLayout(orientation="vertical", spacing=6)
        self.chat_scroll = ScrollView()
        self.chat_box = BoxLayout(orientation="vertical", size_hint_y=None,
                                  spacing=8, padding=6)
        self.chat_box.bind(minimum_height=self.chat_box.setter("height"))
        self.chat_scroll.add_widget(self.chat_box)
        v.add_widget(self.chat_scroll)

        trow = BoxLayout(size_hint_y=None, height=46, spacing=6)
        self.b_talk = NeonButton(glow=MAGENTA, font_size="13sp")
        self.b_convo = NeonButton(glow=MAGENTA, font_size="13sp")
        self.b_auto = NeonButton(glow=MAGENTA, font_size="13sp")
        self.b_talk.bind(on_press=lambda *a: self.tog("talk"))
        self.b_convo.bind(on_press=lambda *a: self.tog("convo"))
        self.b_auto.bind(on_press=lambda *a: self.tog("auto"))
        for b in (self.b_talk, self.b_convo, self.b_auto):
            trow.add_widget(b)
        v.add_widget(trow)
        self.upd_toggles()

        irow = BoxLayout(size_hint_y=None, height=64, spacing=6)
        self.msg_input = TextInput(input_type="text", keyboard_suggestions=True,
                                   hint_text="Type a message or command",
                                   multiline=False, font_size="18sp",
                                   **style_in({}))
        self.msg_input.bind(on_text_validate=self.on_send)
        send = NeonButton(glow=CYAN, text="SEND", size_hint_x=0.28, font_size="16sp")
        send.bind(on_press=self.on_send)
        irow.add_widget(self.msg_input)
        irow.add_widget(send)
        v.add_widget(irow)

        mic = NeonButton(glow=GREEN, text="TAP TO TALK", size_hint_y=None,
                         height=110, font_size="22sp")
        mic.bind(on_press=self.on_mic)
        v.add_widget(mic)
        return v

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
        g = GridLayout(cols=2, spacing=8, size_hint_y=None, height=4 * 56 + 3 * 8)
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

    # ---------- projects and auto run ----------

    def build_projects(self):
        sv, c = self._scroll()
        self._head(c, "NEW PROJECT", MAGENTA)
        self.proj_name = mk_input("Project name (business, game, workout...)")
        c.add_widget(self.proj_name)
        self.proj_goal = mk_input("Goal: what should it build or do?", multiline=True, height=100)
        c.add_widget(self.proj_goal)
        self._btn(c, "CREATE PROJECT", self.new_project, MAGENTA)

        self._head(c, "YOUR PROJECTS (tap to open)", CYAN)
        self.proj_list = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None)
        self.proj_list.bind(minimum_height=self.proj_list.setter("height"))
        c.add_widget(self.proj_list)

        self._head(c, "SELECTED PROJECT", GREEN)
        self.proj_title = autosize(Label(text="None selected.", color=TXT, bold=True))
        c.add_widget(self.proj_title)
        self.proj_status = autosize(Label(text="", color=GREEN))
        c.add_widget(self.proj_status)
        self._btn(c, "AUTO RUN", self.auto_start, GREEN, 56)
        self._btn(c, "PAUSE", lambda *a: self.auto_stop("Paused."), AMBER)
        self.proj_note = mk_input("Add a note, or answer its question", multiline=True, height=90)
        c.add_widget(self.proj_note)
        self._btn(c, "ADD NOTE / ANSWER", self.add_note, CYAN)
        self._btn(c, "MARK DONE", self.mark_done, MAGENTA)

        self._head(c, "PROJECT LOG", AMBER)
        self.proj_log = autosize(Label(text="", color=TXT))
        c.add_widget(self.proj_log)
        self.refresh_projects()
        Clock.schedule_interval(lambda dt: self.update_proj_view(), 3)
        return sv

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
            self.proj_status.text = "Status: " + p[3] + ("  (auto run ON)" if self.auto_on else "")
            lines = []
            for ts, kind, text in self.db.plog(self.cur_proj, 20):
                who = {"pal": "Pal", "you": "You", "run": "Ran", "ask": "ASKS"}.get(kind, kind)
                lines.append(ts[5:16].replace("T", " ") + " " + who + ": " + text)
            self.proj_log.text = "\n\n".join(lines) if lines else "No log yet."
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
        if p and p[3] == "waiting":
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
        if not os.path.exists(self.key_path):
            self.proj_status.text = "Auto run needs a Gemini key. Save it in MORE, GEMINI KEY."
            self.flash("Need a Gemini key first: MORE tab, GEMINI KEY.")
            return
        self.auto_on = True
        self.auto_steps = 0
        self.db.set_pstatus(self.cur_proj, "running")
        self.refresh_projects()
        self.update_proj_view()
        Clock.schedule_once(self.auto_next, 0.5)

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
            "You are Pocket Pal, working on a long project for the user, one small step per turn. "
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
        if err:
            self.err("auto net", err)
            self.auto_stop("No connection. Paused.")
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
            self.notify("Pocket Pal needs you: " + pname, question)
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

    def _auto_cmd(self, pid, cm):
        try:
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
            r = BoxLayout(size_hint_y=None, height=56, spacing=5)
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

    # ---------- chat helpers ----------

    def add_msg(self, text, mine):
        b = Bubble(mine=mine, text=text)
        row = BoxLayout(size_hint_y=None, height=b.height, spacing=6)
        b.bind(height=lambda w, h: setattr(row, "height", h))
        b.size_hint_x = 0.85
        if mine:
            row.add_widget(Widget(size_hint_x=0.15))
            row.add_widget(b)
        else:
            row.add_widget(b)
            row.add_widget(Widget(size_hint_x=0.15))
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
        for role, text in rows:
            self.add_msg(text, role == "user")
        self.hist = [("user" if r == "user" else "model", t) for r, t in rows][-8:]
        if not rows:
            self.add_msg("Hi! Tap the green button and say something like "
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
            self.tts.speak(t, TTS.QUEUE_FLUSH, None, "pp")
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

    # ---------- actions from buttons ----------

    def on_send(self, instance):
        text = self.msg_input.text.strip()
        self.msg_input.text = ""
        self.convo_active = False
        if text:
            self.handle(text, False)

    def on_mic(self, instance):
        try:
            if self.tts is not None and self.tts_ok:
                self.tts.stop()
        except Exception:
            pass
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
            }
            if verb == "open":
                key = arg.lower()
                if key in apps:
                    i = act.getPackageManager().getLaunchIntentForPackage(apps[key])
                    if i is None:
                        return "app not found: " + key
                    act.startActivity(i)
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
                act.startActivity(i)
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

    def local_route(self, text, low):
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

    def ask_gemini(self, text):
        try:
            with open(self.key_path) as f:
                key = f.read().strip()
        except Exception:
            key = ""
        if not key:
            self.reply("I need a Gemini key for that. Type: setkey YOUR_KEY")
            return
        wait = int(self.cool_until - time.time())
        if wait > 0:
            self.reply("Gemini is resting after hitting its free limit. Try again in "
                       + str(wait) + " seconds. Simple commands like open, search, "
                       "timer and alarm still work.")
            return
        contents = []
        for role, t in self.hist[-8:]:
            if not contents and role != "user":
                continue
            contents.append({"role": role, "parts": [{"text": t}]})
        if not contents:
            contents = [{"role": "user", "parts": [{"text": text}]}]
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
            code, raw = gemini_post(key, body)
        except Exception as e:
            err = str(e)
        Clock.schedule_once(lambda dt: self.on_gemini(code, raw, err), 0)

    def on_gemini(self, code, raw, err):
        if err:
            self.err("gemini net", err)
            self.reply("I could not reach Gemini. Check your connection.")
            return
        if code == 429:
            self.cool_until = time.time() + 60
            self.reply("Gemini's free limit was hit. I will rest for a minute. "
                       "Simple commands still work.")
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
            PA.mActivity.startActivity(Intent.createChooser(i, "Save Pocket Pal backup"))
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
        if self.cfg.get("auto"):
            Clock.schedule_once(lambda dt: self.on_mic(None), 2.5)

    def on_pause(self):
        return True

    def on_stop(self):
        if hasattr(self, "db"):
            self.db.close()


if __name__ == "__main__":
    BusinessDashboard().run()
