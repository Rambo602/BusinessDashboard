import sys, shutil, py_compile
F = "main.py"
s = open(F, encoding="utf-8").read()
if "V73_DIAG" in s:
    sys.exit("Already patched (v73).")
shutil.copy(F, F + ".bak73")
A1 = '            i.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", ["-c", "( " + cmd + " ) 2>&1 | curl -s -m 20 --data-binary @- http://127.0.0.1:%d/o" % port])\n'
N1 = r'''            _JS = autoclass("java.lang.String")  # V73_DIAG
            _AR = autoclass("java.lang.reflect.Array")
            _line = ("( " + cmd + " ) > $HOME/.rambo_out.txt 2>&1; echo \"$(date) exit=$?\" >> $HOME/rambo_term.log; "
                     "curl -s -m 20 --data-binary @$HOME/.rambo_out.txt http://127.0.0.1:%d/o" % port)
            _arr = _AR.newInstance(_JS, 2)
            _AR.set(_arr, 0, _JS("-c"))
            _AR.set(_arr, 1, _JS(_line))
            i.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", _arr)
'''
A2 = '            i.putExtra("com.termux.RUN_COMMAND_BACKGROUND", True)\n            act.startService(i)\n'
N2 = ('            i.putExtra("com.termux.RUN_COMMAND_BACKGROUND", True)\n'
      '            _cn = act.startService(i)\n'
      '            self._v73_diag = "startService component=" + str(_cn) + " port=" + str(port) + " cmd=" + cmd[:60]\n')
A3 = '            return "TIMEOUT: no output. Check the Termux permission for RAMBO AI and allow-external-apps."\n'
N3 = ('            return ("TIMEOUT: Termux did not call back. In Termux run: cat ~/rambo_term.log  "\n'
      '                    "(a new line means the command ran). Then type: logs  and  termuxperm")\n')
A4 = '        if low in ("save", "save this", "save to memory"):  # ASK_FIRST_V63\n'
N4 = ('        if re.match(r"^(error logs?|show (the )?(errors?|logs?)|logs?|errors?)$", low):\n'
      '            self._v73_logs()\n'
      '            return\n'
      '        if low in ("termuxperm", "termux perm", "termux status"):\n'
      '            self._v73_perm()\n'
      '            return\n') + A4
A5 = "    def _v72_newproj(self, *a):\n"
H = r'''    def _v73_logs(self):
        try:
            rows = self.db.errors(10)
        except Exception as e:
            rows = "could not read: " + str(e)[:100]
        d = getattr(self, "_v73_diag", "no Termux run yet this session")
        self.reply("LAST TERMUX RUN: " + d + "\nAPP ERRORS:\n" + str(rows)[:1400])

    def _v73_perm(self):
        P = "com.termux.permission.RUN_COMMAND"
        try:
            from jnius import autoclass
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            pi = act.getPackageManager().getPackageInfo(act.getPackageName(), 4096)
            rp = [str(x) for x in (pi.requestedPermissions or [])]
            declared = P in rp
            granted = act.checkSelfPermission(P) == 0
            msg = ("package " + str(act.getPackageName()) + "; declared in this APK: " + str(declared)
                   + "; granted: " + str(granted))
            if declared and not granted:
                JS = autoclass("java.lang.String")
                AR = autoclass("java.lang.reflect.Array")
                arr = AR.newInstance(JS, 1)
                AR.set(arr, 0, JS(P))
                act.requestPermissions(arr, 73)
                msg += ". Asked Android for it. Tap Allow if a prompt appears, then try: termux ls"
            elif not declared:
                msg += ". This APK does not contain the permission, so the build must be redone."
            self.reply(msg)
        except Exception as e:
            self.reply("termuxperm failed: " + str(e)[:200])

'''
try:
    for a in (A1, A2, A3, A4, A5):
        if s.count(a) != 1:
            raise Exception("anchor count %d for %r" % (s.count(a), a.strip()[:50]))
    s = s.replace(A1, N1, 1).replace(A2, N2, 1).replace(A3, N3, 1).replace(A4, N4, 1).replace(A5, H + A5, 1)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak73", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v73 OK")
