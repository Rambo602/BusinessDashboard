import os, sys, shutil, py_compile
F = "main.py"
src = open(F, encoding="utf-8").read()
if "def _quick_time" in src:
    sys.exit("Already patched (v57).")
shutil.copy(F, F + ".bak57")
def swap(s, old, new, label):
    if s.count(old) != 1:
        raise Exception("anchor " + label + " count=" + str(s.count(old)))
    return s.replace(old, new, 1)

METHODS = r'''    def _quick_time(self, text):
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

'''
try:
    s = src
    s = swap(s, "    def proj_copy(self, *a):\n", METHODS + "    def proj_copy(self, *a):\n", "methods")
    s = swap(s, '            qc = self._quick_calc(text)\n            if qc:\n                self.reply(qc)\n                return\n',
             '            qt = self._quick_time(text)\n            if qt:\n                self.reply(qt)\n                return\n'
             '            qc = self._quick_calc(text)\n            if qc:\n                self.reply(qc)\n                return\n', "route")
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak57", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v57 OK")
