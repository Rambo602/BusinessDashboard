import os, sys, shutil, py_compile
F = "main.py"
src = open(F, encoding="utf-8").read()
if "def proj_share" in src:
    sys.exit("Already patched (v53).")
shutil.copy(F, F + ".bak53")

def swap(s, old, new, label):
    if s.count(old) != 1:
        raise Exception("anchor " + label + " count=" + str(s.count(old)))
    return s.replace(old, new, 1)

BTNS = '''        self._btn(c, "MARK DONE", self.mark_done, MAGENTA)
        self._head(c, "WHAT TO DO WITH THE RESULT", GREEN)
        self._btn(c, "SHARE RESULT (Claude, ChatGPT, Grok, Gemini...)", self.proj_share, CYAN, 56)
        self._btn(c, "SAVE PDF", self.proj_pdf, GREEN)
        self._btn(c, "SAVE TEXT", self.proj_txt, GREEN)
        self._btn(c, "COPY RESULT", self.proj_copy, CYAN)
        self._btn(c, "SAVE TO MEMORY", self.proj_mem, AMBER)
        self._btn(c, "TIDY WITH GEMMA (clean summary)", self.proj_tidy, MAGENTA, 56)
        self.refresh_projects()
'''

METHODS = r'''    def _proj_export(self):
        if self.cur_proj is None:
            self.flash("Open a project first")
            return None, None
        p = self.db.get_project(self.cur_proj)
        rows = self.db.plog(self.cur_proj, 200)
        pal = [t for ts, k, t in rows if k == "pal"]
        summ = [t for t in pal if t.startswith("SUMMARY:")]
        body = summ[-1][8:].strip() if summ else "\n\n".join(pal)
        if not body:
            self.flash("Nothing to export yet")
            return None, None
        return p[1], "Goal: " + (p[2] or "") + "\n\n" + body

    def proj_share(self, *a):
        try:
            title, text = self._proj_export()
            if not text:
                return
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            PA = autoclass("org.kivy.android.PythonActivity")
            i = Intent(Intent.ACTION_SEND)
            i.setType("text/plain")
            i.putExtra(Intent.EXTRA_SUBJECT, title)
            i.putExtra(Intent.EXTRA_TEXT, (title + "\n\n" + text)[:100000])
            PA.mActivity.startActivity(Intent.createChooser(i, "Send to"))
        except Exception as e:
            self.err("share", e)
            self.flash("Share failed")

    def proj_copy(self, *a):
        try:
            title, text = self._proj_export()
            if not text:
                return
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(title + "\n\n" + text)
            self.flash("Result copied")
        except Exception as e:
            self.err("copy result", e)

    def _save_bytes(self, name, data):
        for d in ("/storage/emulated/0/Download", self.user_data_dir):
            try:
                path = os.path.join(d, name)
                with open(path, "wb") as f:
                    f.write(data)
                return path
            except Exception:
                continue
        return None

    def proj_txt(self, *a):
        title, text = self._proj_export()
        if not text:
            return
        nm = re.sub(r"[^A-Za-z0-9]+", "_", title)[:30] + "_" + datetime.now().strftime("%m%d_%H%M") + ".txt"
        path = self._save_bytes(nm, (title + "\n\n" + text).encode("utf-8"))
        self.flash("Saved: " + path if path else "Save failed")

    def proj_pdf(self, *a):
        try:
            title, text = self._proj_export()
            if not text:
                return
            nm = re.sub(r"[^A-Za-z0-9]+", "_", title)[:30] + "_" + datetime.now().strftime("%m%d_%H%M") + ".pdf"
            path = self._save_bytes(nm, self._mk_pdf(title, text))
            self.flash("Saved: " + path if path else "Save failed")
        except Exception as e:
            self.err("pdf", e)
            self.flash("PDF failed")

    def _mk_pdf(self, title, text):
        import textwrap
        lines = []
        for para in (title + "\n\n" + text).split("\n"):
            lines += textwrap.wrap(para, 88) or [""]
        pages = [lines[i:i + 52] for i in range(0, len(lines), 52)] or [[""]]
        n = len(pages)
        kids = " ".join("%d 0 R" % (4 + 2 * k) for k in range(n))
        objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
                ("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, n)).encode(),
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
        for k, pl in enumerate(pages):
            st = "BT /F1 11 Tf 14 TL 50 800 Td\n"
            for ln in pl:
                esc = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                st += "(" + esc + ") Tj T*\n"
            st += "ET"
            sb = st.encode("latin-1", "replace")
            objs.append(("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % (5 + 2 * k)).encode())
            objs.append(b"<< /Length %d >>\nstream\n" % len(sb) + sb + b"\nendstream")
        out = b"%PDF-1.4\n"
        offs = []
        for i, o in enumerate(objs):
            offs.append(len(out))
            out += b"%d 0 obj\n" % (i + 1) + o + b"\nendobj\n"
        xr = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        for o in offs:
            out += b"%010d 00000 n \n" % o
        out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xr)
        return out

    def proj_mem(self, *a):
        title, text = self._proj_export()
        if not text:
            return
        self.db.add_plog(self.cur_proj, "pal", "Saved result of " + title + ": " + text[:1500])
        self.flash("Saved to memory. Gemma can use it later")

    def proj_tidy(self, *a):
        title, text = self._proj_export()
        if not text:
            return
        self.flash("Gemma is tidying... (can take a minute)")
        pid = self.cur_proj
        threading.Thread(target=self._tidy_thread, args=(pid, title, text[:2500]), daemon=True).start()

    def _tidy_thread(self, pid, title, text):
        try:
            import urllib.request
            body = json.dumps({"messages": [
                {"role": "system", "content": "Rewrite the user's project notes as a clean, organised summary with short headings and bullet points. Keep every important fact. No preamble."},
                {"role": "user", "content": text}], "max_tokens": 600}).encode()
            rq = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
                                        data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(rq, timeout=240) as r:
                out = json.loads(r.read().decode())["choices"][0]["message"]["content"].strip()
            self.db.add_plog(pid, "pal", "SUMMARY: " + out)
            Clock.schedule_once(lambda dt: self.flash("Summary ready. Share or save it now"), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: self.flash("Tidy failed. Is the Gemma server running?"), 0)

'''
try:
    s = src
    s = swap(s, '        self._btn(c, "MARK DONE", self.mark_done, MAGENTA)\n        self.refresh_projects()\n', BTNS, "buttons")
    s = swap(s, "    def refresh_projects(self):\n", METHODS + "    def refresh_projects(self):\n", "methods")
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak53", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v53 OK")
