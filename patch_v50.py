# patch_v50: faster reactions. (1) simple maths is answered instantly by code (always right),
# (2) local Gemma replies appear word by word as they are written, (3) shorter chat history sent to
# Gemma so it starts answering sooner. Additive. Backup: main.py.bak50. Undo: cp main.py.bak50 main.py
import os, sys, shutil, py_compile

F = "main.py"
if not os.path.exists(F):
    sys.exit("STOPPED: main.py not found (run this inside ~/BusinessDashboard)")
src = open(F, encoding="utf-8").read()
if "_quick_calc" in src:
    sys.exit("Already patched (v50). Nothing to do.")
shutil.copy(F, F + ".bak50")


def swap(s, old, new, label):
    if s.count(old) != 1:
        raise Exception("anchor not unique or missing: " + label + " (%d)" % s.count(old))
    return s.replace(old, new, 1)


METHODS = r'''    def _quick_calc(self, text):
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

'''

STREAM = (
'            bd = json.loads(body.decode())\n'
'            bd["stream"] = True\n'
'            rq = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",\n'
'                                        data=json.dumps(bd).encode(), headers={"Content-Type": "application/json"})\n'
'            acc = ""\n'
'            lastu = 0.0\n'
'            with urllib.request.urlopen(rq, timeout=150) as r:\n'
'                for raw in r:\n'
'                    line = raw.decode("utf-8", "ignore").strip()\n'
'                    if not line.startswith("data:"):\n'
'                        continue\n'
'                    chunk = line[5:].strip()\n'
'                    if chunk == "[DONE]":\n'
'                        break\n'
'                    try:\n'
'                        piece = json.loads(chunk)["choices"][0]["delta"].get("content") or ""\n'
'                    except Exception:\n'
'                        continue\n'
'                    acc += piece\n'
'                    now = time.time()\n'
'                    if now - lastu > 0.3:\n'
'                        lastu = now\n'
'                        shown = re.sub(r"<think>.*?(</think>|$)", "", acc, flags=re.S).strip()\n'
'                        if shown:\n'
'                            Clock.schedule_once(lambda dt, tt=shown: self._stream_show(tt), 0)\n'
'            out = acc.strip()\n'
)

try:
    s = src
    s = swap(s, '            hard = low.startswith("gemini") or len(text) > 700\n',
             '            qc = self._quick_calc(text)\n            if qc:\n                self.reply(qc)\n                return\n'
             '            hard = low.startswith("gemini") or len(text) > 700\n', "calc")
    s = swap(s, '            msgs = []\n            for role, t in self.hist[-8:]:\n'
                '                if not msgs and role != "user":\n                    continue\n'
                '                msgs.append({"role": "assistant" if role == "model" else "user", "content": t})\n',
             '            msgs = []\n            for role, t in self.hist[-4:]:\n'
             '                if not msgs and role != "user":\n                    continue\n'
             '                msgs.append({"role": "assistant" if role == "model" else "user", "content": t[:400]})\n',
             "history")
    s = swap(s, '            rq = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",\n'
                '                                        data=body, headers={"Content-Type": "application/json"})\n'
                '            with urllib.request.urlopen(rq, timeout=150) as r:\n'
                '                d = json.loads(r.read().decode())\n'
                '            out = d["choices"][0]["message"]["content"].strip()\n',
             STREAM, "stream")
    s = swap(s, "    def _local_done(self, text, out, err):\n        if out:\n",
             METHODS + "    def _local_done(self, text, out, err):\n        self._stream_clear()\n        if out:\n", "done")
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak50", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v50 OK: instant maths, replies appear as they are written, shorter history to Gemma")
print("UNDO: cd ~/BusinessDashboard && cp main.py.bak50 main.py")
