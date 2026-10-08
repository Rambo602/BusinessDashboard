import shutil, sys
s = open("main.py", encoding="utf-8").read()
b = open("buildozer.spec", encoding="utf-8").read()


def rep(t, o, n):
    if t.count(o) != 1:
        print("ABORT: " + o[:40])
        sys.exit(1)
    return t.replace(o, n)


UI = '''        self._head(c, "APP UPDATE", AMBER)
        self.gh_in = mk_input("GitHub token (paste once)", password=True)
        self._row(c, self.gh_in, "SAVE", self.save_gh_token, AMBER)
        self._btn(c, "CHECK + INSTALL UPDATE", self.check_update, AMBER, 56)
        import updater
        self.upd_out = autosize(Label(text="Installed: " + updater.cur_ver(), color=TXT))
        c.add_widget(self.upd_out)
'''
METH = '''    def _gh_file(self):
        return os.path.join(os.path.dirname(self.key_path) or ".", "gh_token.txt")

    def upd_set(self, t):
        Clock.schedule_once(lambda dt: setattr(self.upd_out, "text", t), 0)

    def save_gh_token(self, *a):
        t = self.gh_in.text.strip()
        if t:
            open(self._gh_file(), "w").write(t)
            self.gh_in.text = ""
        self.upd_set("Token SAVED." if t else "Paste a token first.")

    def check_update(self, *a):
        import threading, updater
        if not os.path.exists(self._gh_file()):
            return self.upd_set("Save a GitHub token first.")
        threading.Thread(target=updater.run, args=(self._gh_file(), self.upd_set),
                         daemon=True).start()

'''
s = rep(s, '        self._head(c, "SELF TEST", GREEN)\n', UI + '        self._head(c, "SELF TEST", GREEN)\n')
s = rep(s, "    # ---------- projects and auto run ----------\n", METH + "    # ---------- projects and auto run ----------\n")
compile(s, "main.py", "exec")
shutil.copy("main.py", "main.py.bak31")
open("main.py", "w", encoding="utf-8").write(s)
open("buildozer.spec", "w", encoding="utf-8").write(b)
print("PATCH_V31_OK")
