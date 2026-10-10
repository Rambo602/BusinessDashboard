import os, sys, shutil, py_compile
F = "main.py"
src = open(F, encoding="utf-8").read()
if "def proj_share2" in src:
    sys.exit("Already patched (v55).")
shutil.copy(F, F + ".bak55")
notes = []
def swap(s, old, new, label, must):
    n = s.count(old)
    if n != 1:
        if must:
            raise Exception("anchor " + label + " count=" + str(n))
        notes.append("skipped " + label + " (" + str(n) + ")")
        return s
    return s.replace(old, new, 1)

SSL = '''from kivy.metrics import dp as _dp

try:
    import ssl as _ssl, certifi as _certifi
    os.environ["SSL_CERT_FILE"] = _certifi.where()
    _ssl._create_default_https_context = lambda *a, **k: _ssl.create_default_context(cafile=_certifi.where())
except Exception:
    pass
'''

SHARE = '''    def proj_share2(self, *a):
        try:
            title, text = self._proj_export()
            if not text:
                return
            from jnius import autoclass, cast
            Intent = autoclass("android.content.Intent")
            JString = autoclass("java.lang.String")
            PA = autoclass("org.kivy.android.PythonActivity")
            i = Intent()
            i.setAction(Intent.ACTION_SEND)
            i.setType("text/plain")
            i.putExtra(Intent.EXTRA_SUBJECT, JString(title))
            i.putExtra(Intent.EXTRA_TEXT, JString((title + "\\n\\n" + text)[:90000]))
            try:
                ch = Intent.createChooser(i, cast("java.lang.CharSequence", JString("Send to")))
            except Exception:
                ch = i
            PA.mActivity.startActivity(ch)
        except Exception as e:
            self.err("share", e)
            self.flash("Share failed: " + str(e)[:90])

'''
try:
    s = src
    s = swap(s, "from kivy.metrics import dp as _dp\n", SSL, "ssl", True)
    s = swap(s, "keyboard_suggestions=(not multiline)", "keyboard_suggestions=True", "spell", True)
    s = swap(s, "    def proj_copy(self, *a):\n", SHARE + "    def proj_copy(self, *a):\n", "share", True)
    s = swap(s, "self.proj_share, CYAN, 56)", "self.proj_share2, CYAN, 56)", "sharebtn", True)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
    sp = open("buildozer.spec", encoding="utf-8").read()
    if "certifi" not in sp:
        sp = sp.replace("kivy,sqlite3", "kivy,sqlite3,certifi,openssl", 1)
        open("buildozer.spec", "w", encoding="utf-8").write(sp)
except Exception as e:
    shutil.copy(F + ".bak55", F)
    sys.exit("STOPPED and rolled back: " + str(e))
for n in notes:
    print(n)
print("PATCHED v55 OK")
