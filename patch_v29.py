import shutil, sys
P = "main.py"
s = open(P, encoding="utf-8").read()

old1 = '''            msgs[-1] = {"role": "user", "content": "/no_think " + msgs[-1]["content"]}
'''
new1 = '''            merged = []
            for m in msgs:
                if merged and merged[-1]["role"] == m["role"]:
                    merged[-1] = {"role": m["role"],
                                  "content": merged[-1]["content"] + chr(10) + m["content"]}
                else:
                    merged.append(m)
            msgs = merged
'''

old2 = '''"messages": [sysm] + msgs, "max_tokens": 250}'''
new2 = '''"messages": [sysm] + msgs, "max_tokens": 250,
                                    "chat_template_kwargs": {"enable_thinking": False}}'''

for name, o in (("1", old1), ("2", old2)):
    if s.count(o) != 1:
        print("ABORT: block " + name + " not found exactly once")
        sys.exit(1)

shutil.copy(P, P + ".bak29")
s = s.replace(old1, new1).replace(old2, new2)
open(P, "w", encoding="utf-8").write(s)
print("PATCH_V29_OK")
