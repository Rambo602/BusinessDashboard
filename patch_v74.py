import sys, shutil, py_compile
F = "main.py"
s = open(F, encoding="utf-8").read()
if "V74_HTTP_EXEC" in s:
    sys.exit("Already patched (v74).")
shutil.copy(F, F + ".bak74")
A1 = "    def _v72_run_termux(self, cmd, wait=60):\n"
N1 = r'''    def _v72_run_termux(self, cmd, wait=60):  # V74_HTTP_EXEC
        tok = ""
        try:
            tp = os.path.join(self.user_data_dir, "exec.token")
            if os.path.exists(tp):
                tok = open(tp).read().strip()
        except Exception:
            tok = ""
        if not tok:
            return "No token yet. In Termux run: cat ~/.rambo_exec_token  then type here: setexec TOKEN"
        try:
            rq = urllib.request.Request("http://127.0.0.1:8765/run", data=cmd.encode("utf-8"),
                                        headers={"X-Token": tok}, method="POST")
            with urllib.request.urlopen(rq, timeout=wait + 10) as r:
                out = r.read().decode("utf-8", "replace")
            self._v73_diag = "http exec ok: " + cmd[:60]
            return out.strip()[-1500:] or "(no output)"
        except Exception as e:
            self._v73_diag = "http exec failed: " + str(e)[:120]
            return ("Exec server not reachable (" + str(e)[:80] + "). In Termux run: "
                    "nohup python ~/rambo_exec.py > ~/rambo_exec.log 2>&1 &")

''' + "    def _v72_run_termux_old(self, cmd, wait=60):\n"
A2 = '        if low in ("termuxperm", "termux perm", "termux status"):\n'
N2 = ('        if low.startswith("setexec "):\n'
      '            try:\n'
      '                _t = text.split(None, 1)[1].strip()\n'
      '                with open(os.path.join(self.user_data_dir, "exec.token"), "w") as _f:\n'
      '                    _f.write(_t)\n'
      '                self.reply("Token saved. Now type: execstatus")\n'
      '            except Exception as e:\n'
      '                self.reply("Could not save the token: " + str(e)[:100])\n'
      '            return\n'
      '        if low == "execstatus":\n'
      '            self._v72_bg("pwd && echo exec server ok")\n'
      '            return\n') + A2
try:
    for a in (A1, A2):
        if s.count(a) != 1:
            raise Exception("anchor count %d for %r" % (s.count(a), a.strip()[:50]))
    s = s.replace(A1, N1, 1).replace(A2, N2, 1)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak74", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v74 OK")
