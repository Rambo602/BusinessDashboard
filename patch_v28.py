import shutil, sys
P = "main.py"
s = open(P, encoding="utf-8").read()

if "_local_thread" not in s:
    print("ABORT: v1.5.0 (patch_v27) is not in main.py")
    sys.exit(1)

old1 = '''    def task_rows(self, n=30):
'''
new1 = '''    def notes_search(self, query, limit=3):
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

    def task_rows(self, n=30):
'''

old2 = '''            self.flash("Thinking on the phone...")
            threading.Thread(target=self._local_thread, args=(text, msgs), daemon=True).start()
'''
new2 = '''            self.flash("Thinking on the phone...")
            try:
                facts = self.db.memories()
                notes = self.db.notes_search(text)
            except Exception:
                facts, notes = [], []
            threading.Thread(target=self._local_thread,
                             args=(text, msgs, facts, notes), daemon=True).start()
'''

old3 = '''    def _local_thread(self, text, msgs):
'''
new3 = '''    def _local_thread(self, text, msgs, facts=(), notes=()):
'''

old4 = '''            sysm = {"role": "system", "content": "You are RAMBO AI, a helpful assistant on the user's Android phone. Answer in one to four short sentences."}
'''
new4 = '''            sp = ("You are RAMBO AI, a smart, friendly assistant on the user's Android phone. "
                  "Answer clearly and accurately in two to five practical sentences. "
                  "If you are not sure, say so instead of guessing. For safety topics put the warning first. ")
            if facts:
                sp += "Known facts about the user: " + "; ".join(facts) + ". "
            if notes:
                sp += ("Saved reference notes you wrote earlier. Use them when relevant and do not contradict them: "
                       + " || ".join(notes) + " ")
            sysm = {"role": "system", "content": sp}
'''

old5 = '''"max_tokens": 200}).encode()'''
new5 = '''"max_tokens": 250}).encode()'''

old6 = '''urlopen(rq, timeout=90)'''
new6 = '''urlopen(rq, timeout=150)'''

old7 = '''                    if i is not None:
                        act.startActivity(i)
                        if rest:
'''
new7 = '''                    if i is not None and rest:
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
'''

pairs = [("1", old1, new1), ("2", old2, new2), ("3", old3, new3), ("4", old4, new4),
         ("5", old5, new5), ("6", old6, new6), ("7", old7, new7)]
for name, o, n in pairs:
    if s.count(o) != 1:
        print("ABORT: block " + name + " not found exactly once")
        sys.exit(1)

shutil.copy(P, P + ".bak28")
for name, o, n in pairs:
    s = s.replace(o, n)
open(P, "w", encoding="utf-8").write(s)
print("PATCH_V28_OK")
