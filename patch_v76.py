import sys, shutil, py_compile
F = "main.py"
s = open(F, encoding="utf-8").read()
if "V76_SAFE" in s:
    sys.exit("Already patched (v76).")
shutil.copy(F, F + ".bak76")
A1 = ('    def _v72_is_safe(self, cmd):\n'
      '        return bool(self.V72_SAFE.match(cmd)) and not re.search(r"[;&|<>`$]", cmd)\n')
N1 = r'''    V77_ASK = re.compile(r"(\brm\b|\brmdir\b|\bmv\b|\bchmod\b|\bchown\b|\bkill(all)?\b|\bpkill\b|\bsudo\b|\bsu\b|\buninstall\b|\bpurge\b|\bpkg\s+(remove|autoclean)|\bgit\s+(push|reset|clean|checkout|rebase|restore)|\b(curl|wget|nc|ncat|ssh|scp|sftp|ftp|telnet|socat)\b|\btee\b|\bsed\s+-i|>|\btruncate\b|\bshred\b|\bcrontab\b|\bnohup\b|\beval\b|\bexec\b|\bam\s+start|\bpm\s+(clear|uninstall)|\.key\b|token|\.ssh|secret|password|termux\.properties|\.bashrc|\.env\b|os\.(remove|unlink|rmdir|system|popen|rename)|shutil|rmtree|subprocess|socket|urllib|requests\.|\bopen\([^)]*['\"][wa+])", re.I)

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
'''
A2 = ('        self._v75_say("Running in Termux: " + cmd[:100])\n'
      '        return self._v72_run_termux(cmd)\n')
N2 = ('        self._v75_say("Running in Termux: " + cmd[:100])\n'
      '        out = self._v72_run_termux(cmd)\n'
      '        self._v75_say("Result:\\n" + out[:700])\n'
      '        return out\n')
A3 = ('        if self._auto_risky(cmd) or not self._v72_is_safe(cmd):\n'
      '            ev = threading.Event()\n')
N3 = ('        if self._auto_risky(cmd) or self._v77_needs_ok(cmd):  # V77_AUTO\n'
      '            ev = threading.Event()\n')
try:
    for a in (A1, A2, A3):
        if s.count(a) != 1:
            raise Exception("anchor count %d for %r" % (s.count(a), a.strip()[:50]))
    s = s.replace(A1, N1, 1).replace(A2, N2, 1).replace(A3, N3, 1)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak76", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v76 OK")
