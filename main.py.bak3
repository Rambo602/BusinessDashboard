__version__ = "0.1.0"

import os
import sqlite3
import urllib.request
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView


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

        self.title = "Business Command Center"

        os.makedirs(
            self.user_data_dir,
            exist_ok=True
        )

        db_path = os.path.join(
            self.user_data_dir,
            "business.db"
        )

        self.db = Database(db_path)

        self.backend = BusinessBackend(
            self.db
        )

        root = BoxLayout(
            orientation="vertical",
            padding=8,
            spacing=8
        )

        title = Label(
            text="BUSINESS COMMAND CENTER",
            font_size="22sp",
            size_hint_y=None,
            height=50
        )

        root.add_widget(title)

        self.dashboard = Label(
            text="Loading...",
            size_hint_y=None,
            height=100
        )

        root.add_widget(
            self.dashboard
        )

        scroll = ScrollView()

        content = BoxLayout(
            orientation="vertical",
            spacing=8,
            size_hint_y=None
        )

        content.bind(
            minimum_height=content.setter("height")
        )

        # TASKS

        content.add_widget(
            Label(
                text="TASKS",
                font_size="18sp",
                size_hint_y=None,
                height=40
            )
        )

        self.task_input = TextInput(
            hint_text="Enter task",
            multiline=False,
            size_hint_y=None,
            height=45
        )

        content.add_widget(
            self.task_input
        )

        button = Button(
            text="ADD TASK",
            size_hint_y=None,
            height=45
        )

        button.bind(
            on_press=self.add_task
        )

        content.add_widget(button)

        # FINANCES

        content.add_widget(
            Label(
                text="FINANCES",
                font_size="18sp",
                size_hint_y=None,
                height=40
            )
        )

        self.finance_description = TextInput(
            hint_text="Description",
            multiline=False,
            size_hint_y=None,
            height=45
        )

        content.add_widget(
            self.finance_description
        )

        self.finance_amount = TextInput(
            hint_text="Amount",
            multiline=False,
            input_filter="float",
            size_hint_y=None,
            height=45
        )

        content.add_widget(
            self.finance_amount
        )

        self.finance_category = TextInput(
            hint_text="Category",
            multiline=False,
            size_hint_y=None,
            height=45
        )

        content.add_widget(
            self.finance_category
        )

        button = Button(
            text="ADD FINANCE",
            size_hint_y=None,
            height=45
        )

        button.bind(
            on_press=self.add_finance
        )

        content.add_widget(button)

        # GMAIL

        content.add_widget(
            Label(
                text="GMAIL",
                font_size="18sp",
                size_hint_y=None,
                height=40
            )
        )

        self.email_to = TextInput(
            hint_text="Recipient email",
            multiline=False,
            size_hint_y=None,
            height=45
        )

        content.add_widget(
            self.email_to
        )

        self.email_subject = TextInput(
            hint_text="Subject",
            multiline=False,
            size_hint_y=None,
            height=45
        )

        content.add_widget(
            self.email_subject
        )

        self.email_body = TextInput(
            hint_text="Email message",
            multiline=True,
            size_hint_y=None,
            height=120
        )

        content.add_widget(
            self.email_body
        )

        button = Button(
            text="QUEUE EMAIL",
            size_hint_y=None,
            height=45
        )

        button.bind(
            on_press=self.queue_email
        )

        content.add_widget(button)

        button = Button(
            text="CREATE DAILY REPORT",
            size_hint_y=None,
            height=45
        )

        button.bind(
            on_press=self.daily_report
        )

        content.add_widget(button)

        # YOUTUBE

        content.add_widget(
            Label(
                text="YOUTUBE",
                font_size="18sp",
                size_hint_y=None,
                height=40
            )
        )

        self.youtube_url = TextInput(
            hint_text="Video URL",
            multiline=False,
            size_hint_y=None,
            height=45
        )

        content.add_widget(
            self.youtube_url
        )

        self.youtube_comment = TextInput(
            hint_text="Comment",
            multiline=True,
            size_hint_y=None,
            height=100
        )

        content.add_widget(
            self.youtube_comment
        )

        button = Button(
            text="QUEUE COMMENT",
            size_hint_y=None,
            height=45
        )

        button.bind(
            on_press=self.queue_youtube
        )

        content.add_widget(button)

        # WEBSITE

        content.add_widget(
            Label(
                text="WEBSITE ANALYTICS",
                font_size="18sp",
                size_hint_y=None,
                height=40
            )
        )

        self.website_url = TextInput(
            hint_text="Website URL",
            multiline=False,
            size_hint_y=None,
            height=45
        )

        content.add_widget(
            self.website_url
        )

        button = Button(
            text="CHECK WEBSITE",
            size_hint_y=None,
            height=45
        )

        button.bind(
            on_press=self.check_website
        )

        content.add_widget(button)

        # ACTIVITY

        content.add_widget(
            Label(
                text="ACTIVITY LOG",
                font_size="18sp",
                size_hint_y=None,
                height=40
            )
        )

        self.log_output = Label(
            text="Ready.",
            size_hint_y=None,
            height=200
        )

        content.add_widget(
            self.log_output
        )

        scroll.add_widget(content)

        job_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=110,
            spacing=8
        )
        self.job_input = TextInput(
            hint_text="Command (start with pc: for PC jobs)",
            multiline=False
        )
        job_btn = Button(text="Send", size_hint_x=0.25)
        job_btn.bind(on_press=self.add_job)
        job_row.add_widget(self.job_input)
        job_row.add_widget(job_btn)
        root.add_widget(job_row)

        root.add_widget(scroll)

        self.refresh()

        Clock.schedule_interval(
            lambda dt: self.refresh(),
            5
        )

        return root

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

    def add_job(self, instance):
        text = self.job_input.text.strip()
        if text:
            target = "phone"
            if text.lower().startswith("pc:"):
                target = "pc"
                text = text[3:].strip()
            if target == "phone":
                result = self.phone_action(text)
                self.db.log(f"Phone: {text} -> {result}")
            else:
                self.db.add_job(target, text)
                self.db.log(f"Job queued for {target}: {text}")
            self.job_input.text = ""
            self.refresh()

    def refresh(self):

        try:

            total = self.db.finance_total()

            tasks = self.db.task_count()

            emails = self.db.email_count()

            comments = self.db.youtube_count()

            self.dashboard.text = (
                f"TASKS: {tasks}     "
                f"FINANCES: ${total:.2f}\n"
                f"EMAIL QUEUE: {emails}     "
                f"YOUTUBE QUEUE: {comments}     JOBS: {self.db.job_count()}"
            )

            logs = self.db.recent_logs()

            if logs:

                lines = []

                for timestamp, message in logs:

                    timestamp = timestamp.replace(
                        "T",
                        " "
                    )[:16]

                    lines.append(
                        f"{timestamp}\n{message}"
                    )

                self.log_output.text = (
                    "\n\n".join(lines)
                )

            else:

                self.log_output.text = (
                    "No activity yet."
                )

        except Exception as e:

            self.log_output.text = (
                f"Dashboard error: {e}"
            )

    def on_stop(self):

        if hasattr(self, "db"):
            self.db.close()


if __name__ == "__main__":
    BusinessDashboard().run()

