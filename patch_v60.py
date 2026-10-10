import os, sys, shutil, py_compile
F = "main.py"
src = open(F, encoding="utf-8").read()
if "def _groq_fallback" in src:
    sys.exit("Already patched (v60).")
shutil.copy(F, F + ".bak60")

def swap(s, old, new, label):
    if s.count(old) != 1:
        raise Exception("anchor " + label + " count=" + str(s.count(old)))
    return s.replace(old, new, 1)

FUNCS = r'''_GROQ = {"key": "", "path": ""}


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


'''
CMD = ('            mg = re.match(r"^setgroq\\s+(\\S+)$", text.strip(), re.I)\n'
       '            if mg:\n'
       '                self.reply(_groq_save(self.user_data_dir, mg.group(1)))\n'
       '                return\n')
try:
    s = src
    s = swap(s, "def gemini_try(key, body):\n", FUNCS + "def gemini_try(key, body):\n", "funcs")
    s = swap(s, "        if code not in (429, 500, 503):\n            return code, raw\n    return code, raw\n",
             "        if code not in (429, 500, 503):\n            return code, raw\n    return _groq_fallback(body, code, raw)\n", "tail")
    s = swap(s, '        self.key_path = os.path.join(self.user_data_dir, "gemini.key")\n',
             '        self.key_path = os.path.join(self.user_data_dir, "gemini.key")\n'
             '        _GROQ["path"] = os.path.join(self.user_data_dir, "groq.key")\n', "path")
    s = swap(s, "            qc = self._quick_calc(text)\n            if qc:\n", CMD + "            qc = self._quick_calc(text)\n            if qc:\n", "cmd")
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak60", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v60 OK")
