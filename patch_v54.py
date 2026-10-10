import os, sys, shutil, py_compile
F = "main.py"
src = open(F, encoding="utf-8").read()
if "def proj_delete" in src:
    sys.exit("Already patched (v54).")
shutil.copy(F, F + ".bak54")
notes = []
def swap(s, old, new, label, must):
    n = s.count(old)
    if n != 1:
        if must:
            raise Exception("anchor " + label + " count=" + str(n))
        notes.append("skipped " + label + " (" + str(n) + ")")
        return s
    return s.replace(old, new, 1)

SAVE = '''    def _save_bytes(self, name, data):
        try:
            from jnius import autoclass
            PA = autoclass("org.kivy.android.PythonActivity")
            CV = autoclass("android.content.ContentValues")
            MS = autoclass("android.provider.MediaStore$Downloads")
            cr = PA.mActivity.getContentResolver()
            cv = CV()
            cv.put("_display_name", name)
            cv.put("mime_type", "application/pdf" if name.endswith(".pdf") else "text/plain")
            cv.put("relative_path", "Download")
            uri = cr.insert(MS.EXTERNAL_CONTENT_URI, cv)
            o = cr.openOutputStream(uri)
            o.write(bytearray(data))
            o.close()
            return "Download/" + name
        except Exception as e:
            self.err("mediastore", e)
            return self._save_bytes_old(name, data)

    def _save_bytes_old(self, name, data):
'''

DEL = '''    def proj_delete(self, *a):
        import time as _t
        if self.cur_proj is None:
            self.flash("Open a project first")
            return
        if _t.time() - getattr(self, "_del_t", 0) > 5:
            self._del_t = _t.time()
            self.flash("Tap DELETE PROJECT again to confirm")
            return
        self.db.delete_project(self.cur_proj)
        self.cur_proj = None
        self.auto_on = False
        self.proj_title.text = "None selected."
        self.proj_status.text = ""
        self.proj_log.text = ""
        self.refresh_projects()
        self.flash("Project deleted")

'''

DBDEL = '''    def delete_project(self, pid):
        self.conn.execute("DELETE FROM project_log WHERE project_id=?", (pid,))
        self.conn.execute("DELETE FROM projects WHERE id=?", (pid,))
        self.conn.commit()

'''
try:
    s = src
    s = swap(s, "    def _save_bytes(self, name, data):\n", SAVE, "save", True)
    s = swap(s, "    def refresh_projects(self):\n", DEL + "    def refresh_projects(self):\n", "del", True)
    s = swap(s, "    def set_pstatus(self, pid, status):\n", DBDEL + "    def set_pstatus(self, pid, status):\n", "dbdel", True)
    s = swap(s, '        self._btn(c, "MARK DONE", self.mark_done, MAGENTA)\n',
             '        self._btn(c, "MARK DONE", self.mark_done, MAGENTA)\n        self._btn(c, "DELETE PROJECT (tap twice)", self.proj_delete, AMBER)\n', "delbtn", True)
    s = swap(s, "Answer clearly and accurately in two to five practical sentences. ",
             "Answer in one to three short sentences. ", "sp", False)
    s = swap(s, "for role, t in self.hist[-4:]:", "for role, t in self.hist[-2:]:", "hist", False)
    s = swap(s, '"content": t[:400]', '"content": t[:200]', "cut", False)
    s = swap(s, '"max_tokens": 400,', '"max_tokens": 250,', "maxtok", False)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak54", F)
    sys.exit("STOPPED and rolled back: " + str(e))
for n in notes:
    print(n)
print("PATCHED v54 OK")
