import os, sys, shutil, py_compile
F = "main.py"
src = open(F, encoding="utf-8").read()
if "i2 = Intent(AlarmClock.ACTION_SET_TIMER)" in src:
    sys.exit("Already patched (v52).")
shutil.copy(F, F + ".bak52")
notes = []
def swap(s, old, new, label, must):
    n = s.count(old)
    if n != 1:
        if must:
            raise Exception("anchor " + label + " count=" + str(n))
        notes.append("skipped " + label + " (" + str(n) + ")")
        return s
    return s.replace(old, new, 1)
try:
    s = src
    s = swap(s, 'if low.startswith("gemini:") or needs_live(low) or len(low) > 400:',
                'if low.startswith("gemini:") or needs_live(low):', "pick1", True)
    s = swap(s, '    if any(w in low for w in HEAVY_WORDS):\n        return "gemini"\n    return "gemma"',
                '    return "gemma"', "pick2", True)
    s = swap(s, 'hard = low.startswith("gemini") or len(text) > 700',
                'hard = low.startswith("gemini") or len(text) > 1500', "hard", True)
    s = swap(s, '"Known facts about the user: " + "; ".join(facts)',
                '"Known facts about the user: " + "; ".join(list(facts)[:6])', "facts", False)
    s = swap(s, '+ " || ".join(notes) + " ")',
                '+ " || ".join(n[:300] for n in list(notes)[:2]) + " ")', "notes", False)
    s = swap(s, 'GB.kb_sections(self.user_data_dir), text, 2, 600)',
                'GB.kb_sections(self.user_data_dir), text, 1, 300)', "kb", False)
    s = swap(s,
        '                i.putExtra(AlarmClock.EXTRA_SKIP_UI, True)\n                act.startActivity(i)\n                return "timer set "',
        '                i.putExtra(AlarmClock.EXTRA_SKIP_UI, True)\n'
        '                try:\n'
        '                    act.startActivity(i)\n'
        '                except Exception:\n'
        '                    i2 = Intent(AlarmClock.ACTION_SET_TIMER)\n'
        '                    i2.putExtra(AlarmClock.EXTRA_LENGTH, secs)\n'
        '                    act.startActivity(i2)\n'
        '                return "timer set "', "timer", True)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak52", F)
    sys.exit("STOPPED and rolled back: " + str(e))
for n in notes:
    print(n)
print("PATCHED v52 OK")
