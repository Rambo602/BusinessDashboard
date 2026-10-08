import shutil, sys
P = "main.py"
s = open(P, encoding="utf-8").read()

old1 = '''                "tiktok": "com.zhiliaoapp.musically",
            }
'''
new1 = '''                "tiktok": "com.zhiliaoapp.musically",
                "claude": "com.anthropic.claude",
                "chatgpt": "com.openai.chatgpt",
                "grok": "ai.x.grok",
            }
'''

old2 = '''            if verb == "open":
                key = arg.lower()
                if key in apps:
                    i = act.getPackageManager().getLaunchIntentForPackage(apps[key])
                    if i is None:
                        return "app not found: " + key
                    act.startActivity(i)
                    return "opened " + key
'''
new2 = '''            if verb == "open":
                key = arg.lower()
                rest = ""
                first = key.split(" ")[0] if key else key
                if key not in apps and first in apps:
                    key = first
                    parts = arg.split(None, 1)
                    rest = parts[1] if len(parts) > 1 else ""
                if key in apps:
                    i = act.getPackageManager().getLaunchIntentForPackage(apps[key])
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
'''

old3 = '''    def ask_gemini(self, text):
'''
new3 = '''    def ask_gemini(self, text):
        try:
            low = text.lower().strip()
            words = ("code", "script", "write ", "essay", "research", "analy",
                     "compare", "in detail", "plan ", "translate", "summar",
                     "debug", "calculate", "step by step")
            hard = len(text) > 220 or low.startswith("gemini") or any(w in low for w in words)
            if hard or not self.cfg.get("local", True):
                self._ask_cloud(text)
                return
            msgs = []
            for role, t in self.hist[-8:]:
                if not msgs and role != "user":
                    continue
                msgs.append({"role": "assistant" if role == "model" else "user", "content": t})
            if not msgs or msgs[-1]["role"] != "user":
                msgs.append({"role": "user", "content": text})
            msgs[-1] = {"role": "user", "content": "/no_think " + msgs[-1]["content"]}
            self.flash("Thinking on the phone...")
            threading.Thread(target=self._local_thread, args=(text, msgs), daemon=True).start()
        except Exception as e:
            self.err("local route", e)
            self._ask_cloud(text)

    def _local_thread(self, text, msgs):
        out, err = "", ""
        try:
            import urllib.request
            sysm = {"role": "system", "content": "You are RAMBO AI, a helpful assistant on the user's Android phone. Answer in one to four short sentences."}
            body = json.dumps({"messages": [sysm] + msgs, "max_tokens": 200}).encode()
            rq = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
                                        data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(rq, timeout=90) as r:
                d = json.loads(r.read().decode())
            out = d["choices"][0]["message"]["content"].strip()
            out = re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
        except Exception as e:
            err = str(e)
        Clock.schedule_once(lambda dt: self._local_done(text, out, err), 0)

    def _local_done(self, text, out, err):
        if out:
            self.reply(out)
            return
        if err and "refused" not in err.lower():
            self.err("local", err[:150])
        self._ask_cloud(text)

    def _ask_cloud(self, text):
'''

for name, o in (("1", old1), ("2", old2), ("3", old3)):
    if s.count(o) != 1:
        print("ABORT: block " + name + " not found exactly once")
        sys.exit(1)

shutil.copy(P, P + ".bak27")
s = s.replace(old1, new1).replace(old2, new2).replace(old3, new3)
open(P, "w", encoding="utf-8").write(s)
print("PATCH_V27_OK")
