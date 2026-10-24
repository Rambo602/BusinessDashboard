p = "/data/data/com.termux/files/home/BusinessDashboard/main.py"
s = open(p).read()
A = "        if self._auto_risky(cmd) or self._v77_needs_ok(cmd):  # V77_AUTO"
N = ('        _safe83 = bool(re.match(r"^(am start|monkey -p)\\b", cmd.strip())) and not re.search(r"[;&|`$<>]", cmd)\n'
     "        if not _safe83 and (self._auto_risky(cmd) or self._v77_needs_ok(cmd)):  # V77_AUTO")
if s.count(A) != 1:
    raise SystemExit("ANCHOR PROBLEM, nothing changed")
open(p, "w").write(s.replace(A, N))
print("patched")
