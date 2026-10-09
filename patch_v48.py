# patch_v48: picture/file preview above the message box with an X to remove it before sending,
# and the picture shows in the chat after sending. Additive. Backup: main.py.bak48.
# Run inside ~/BusinessDashboard. Undo: cp main.py.bak48 main.py
import os, sys, shutil, py_compile

F = "main.py"
if not os.path.exists(F):
    sys.exit("STOPPED: main.py not found (run this inside ~/BusinessDashboard)")
src = open(F, encoding="utf-8").read()
if "_att_preview" in src:
    sys.exit("Already patched (v48). Nothing to do.")
if "_send_attach" not in src:
    sys.exit("STOPPED: v44 is not applied, so there is nothing to attach to.")
shutil.copy(F, F + ".bak48")


def swap(s, old, new, label):
    if s.count(old) != 1:
        raise Exception("anchor not unique or missing: " + label + " (%d)" % s.count(old))
    return s.replace(old, new, 1)


METHODS = r'''    # ---------- attachment preview (thumbnail + X above the message box) ----------

    def _att_make_strip(self):
        from kivy.uix.image import Image as KImage
        strip = BoxLayout(size_hint_y=None, height=0, spacing=8,
                          padding=[10, 0, 4, 0], opacity=0, disabled=True)
        thumb = KImage(size_hint=(None, 1), width=0)
        try:
            thumb.fit_mode = "contain"
        except Exception:
            pass
        lab = Label(text="", color=TXT, font_size="13sp", halign="left", valign="middle")
        lab.bind(size=lambda w, sz: setattr(w, "text_size", sz))
        rm = NeonButton(glow=MAGENTA, text="X", size_hint=(None, 1), width=52, font_size="20sp")
        rm.bind(on_press=lambda *a: self._att_remove())
        strip.add_widget(thumb)
        strip.add_widget(lab)
        strip.add_widget(rm)
        self.att_strip, self.att_thumb, self.att_lab = strip, thumb, lab
        return strip

    def _att_show(self, on):
        s = getattr(self, "att_strip", None)
        if s is None:
            return
        s.height = 76 if on else 0
        s.opacity = 1 if on else 0
        s.disabled = not on

    def _att_dir(self):
        d = os.path.join(self.user_data_dir, "att_prev")
        os.makedirs(d, exist_ok=True)
        try:
            cut = time.time() - 7 * 86400
            for f in os.listdir(d):
                p = os.path.join(d, f)
                if os.path.getmtime(p) < cut:
                    os.remove(p)
        except Exception:
            pass
        return d

    def _att_preview(self, name, mime, raw):
        path = None
        ext = os.path.splitext(name)[1].lower()
        if mime.startswith("image/") and ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
            path = os.path.join(self._att_dir(), "%d%s" % (int(time.time() * 1000), ext))
            with open(path, "wb") as f:
                f.write(raw)
        self.attach["preview"] = path
        th = self.att_thumb
        if path:
            th.source = path
            try:
                th.reload()
            except Exception:
                pass
            th.width = 64
        else:
            th.source = ""
            th.width = 0
        kind = "Image" if path else ((mime.split("/")[-1] or "File").upper())
        kb = max(1, len(raw) // 1024)
        self.att_lab.text = (name + "\n" + kind + ", " + str(kb)
                             + " KB. Type a question and press SEND, or tap X to remove.")
        self._att_show(True)

    def _att_remove(self):
        att = getattr(self, "attach", None)
        self.attach = None
        self._att_show(False)
        try:
            if att and att.get("preview") and os.path.exists(att["preview"]):
                os.remove(att["preview"])
        except Exception:
            pass
        self.flash("Attachment removed")

    def _att_bubble(self, path):
        if not path or not os.path.exists(path):
            return
        try:
            from kivy.uix.image import Image as KImage
            row = BoxLayout(size_hint_y=None, height=190, spacing=6)
            row.add_widget(Widget(size_hint_x=0.35))
            img = KImage(source=path, size_hint_x=0.65)
            try:
                img.fit_mode = "contain"
            except Exception:
                pass
            row.add_widget(img)
            self.chat_box.add_widget(row)
            Clock.schedule_once(lambda dt: setattr(self.chat_scroll, "scroll_y", 0), 0.15)
        except Exception as e:
            self.err("attach bubble", e)

'''

try:
    s = src
    s = swap(s, "        v.add_widget(pill)\n        return v\n",
             "        v.add_widget(self._att_make_strip())\n        v.add_widget(pill)\n        return v\n",
             "strip")
    s = swap(s, "    def _send_attach(self, text):\n", METHODS + "    def _send_attach(self, text):\n", "methods")
    s = swap(s, "        att = self.attach\n        self.attach = None\n",
             "        att = self.attach\n        self.attach = None\n        self._att_show(False)\n", "hide")
    s = swap(s, "        shown = text + \"\\n(file: \" + att[\"name\"] + \")\"\n        self.add_msg(shown, True)\n",
             "        shown = text + \"\\n(file: \" + att[\"name\"] + \")\"\n"
             "        self._att_bubble(att.get(\"preview\"))\n        self.add_msg(shown, True)\n", "bubble")
    s = swap(s, "        self.attach = {\"name\": name, \"parts\": parts}\n"
                "        kb = max(1, len(raw) // 1024)\n"
                "        self.add_msg(\"Attached: \" + name + \" (\" + str(kb) + \" KB). Type your question and \"\n"
                "                     \"press SEND, or just press SEND to get a summary. Tap + to pick a different file.\", False)\n",
             "        self.attach = {\"name\": name, \"parts\": parts, \"preview\": None}\n"
             "        try:\n            self._att_preview(name, mime, raw)\n        except Exception as e:\n"
             "            self.err(\"attach preview\", e)\n"
             "            self.add_msg(\"Attached: \" + name + \". Type your question and press SEND.\", False)\n",
             "attached")
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak48", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v48 OK: picture preview with X above the message box; picture shows in chat after sending")
print("UNDO: cd ~/BusinessDashboard && cp main.py.bak48 main.py")
