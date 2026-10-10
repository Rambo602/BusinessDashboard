import sys, shutil, py_compile
F = "main.py"
s = open(F, encoding="utf-8").read()
if "PROJ_LAYOUT_V69" in s:
    sys.exit("Already patched (v69).")
shutil.copy(F, F + ".bak69")
R0 = ('        self.refresh_projects()\n'
      '        Clock.schedule_interval(lambda dt: self.update_proj_view(), 3)\n'
      '        return sv\n')
R1 = ('        self.refresh_projects()\n'
      '        Clock.schedule_interval(lambda dt: self.update_proj_view(), 3)\n'
      '        if _v69_bar is not None:\n'
      '            try:\n'
      '                _v69_box = BoxLayout(orientation="vertical")\n'
      '                _v69_box.add_widget(sv)\n'
      '                try:\n'
      '                    _v69_box.add_widget(_v69_bar)\n'
      '                except Exception:\n'
      '                    _v69_box.remove_widget(sv)\n'
      '                    raise\n'
      '                return _v69_box\n'
      '            except Exception as e:\n'
      '                self.err("v69 box", e)\n'
      '        return sv\n')
H = '''    def _v69_page(self, c):
        self.proj_name = mk_input("Project name")
        self.proj_goal = mk_input("Goal: what should it build or do?", multiline=True, height=100)
        nb = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None, height=0, opacity=0)
        nb.disabled = True
        nb.add_widget(self.proj_name)
        nb.add_widget(self.proj_goal)
        nb.add_widget(self._v68_row([("SPEAK", self.speak_project, GREEN),
                                     ("CREATE", self.new_project, MAGENTA),
                                     ("CREATE+RUN", self.create_run, GREEN)]))
        top = self._v68_btn("+ NEW PROJECT", lambda *a: None, MAGENTA)
        top.size_hint_y = None
        top.height = 48
        def tog(*a):
            o = nb.height == 0
            if o:
                nb.height = sum(w.height for w in nb.children) + 6 * (len(nb.children) - 1)
            else:
                nb.height = 0
            nb.opacity = 1 if o else 0
            nb.disabled = not o
        top.bind(on_release=tog)
        c.add_widget(top)
        c.add_widget(nb)
        self.proj_list = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None)
        self.proj_list.bind(minimum_height=self.proj_list.setter("height"))
        c.add_widget(self.proj_list)
        self.proj_title = autosize(Label(text="None selected.", color=TXT, bold=True))
        c.add_widget(self.proj_title)
        self.proj_status = autosize(Label(text="", color=GREEN))
        c.add_widget(self.proj_status)
        self.proj_log = autosize(Label(text="", color=TXT))
        c.add_widget(self.proj_log)
        self.proj_note = mk_input("Message this project", multiline=True, height=56)
        mic = NeonButton(glow=GREEN, text="MIC", size_hint_x=None, width=64, font_size="12sp")
        mic.bind(on_release=self.speak_note)
        snd = NeonButton(glow=CYAN, text="SEND", size_hint_x=None, width=80, font_size="12sp")
        snd.bind(on_release=self.add_note)
        r1 = BoxLayout(orientation="horizontal", spacing=6, size_hint_y=None, height=56)
        r1.add_widget(self.proj_note)
        r1.add_widget(mic)
        r1.add_widget(snd)
        r2 = self._v68_row([("RUN", self.auto_start, GREEN),
                            ("PAUSE", lambda *a: self.auto_stop("Paused."), AMBER),
                            ("CLAUDE", lambda *a: self.proj_to_app("claude"), CYAN),
                            ("MENU", self._v69_menu, MAGENTA)])
        bar = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None, height=124, padding=[0, 6, 0, 0])
        bar.add_widget(r1)
        bar.add_widget(r2)
        return bar

    def _v69_menu(self, *a):
        from kivy.uix.modalview import ModalView
        items = [("DONE (mark finished)", self.mark_done, MAGENTA),
                 ("SAVE TO MEMORY", self.proj_mem, AMBER),
                 ("SHARE (any app)", self.proj_share2, CYAN),
                 ("SEND TO CHATGPT", lambda *x: self.proj_to_app("chatgpt"), GREEN),
                 ("SAVE PDF", self.proj_pdf, GREEN),
                 ("SAVE TEXT", self.proj_txt, GREEN),
                 ("COPY RESULT", self.proj_copy, CYAN),
                 ("TIDY WITH GEMMA", self.proj_tidy, MAGENTA),
                 ("DELETE (tap twice)", self.proj_delete, AMBER)]
        n = len(items)
        mv = ModalView(size_hint=(0.92, None), height=n * 56 + (n - 1) * 6 + 16)
        box = BoxLayout(orientation="vertical", spacing=6, padding=8)
        for t, cb, g in items:
            def go(inst, cb=cb, keep=t.startswith("DELETE")):
                if not keep:
                    mv.dismiss()
                cb(inst)
            bt = self._v68_btn(t, go, g)
            box.add_widget(bt)
        mv.add_widget(box)
        mv.open()

'''
try:
    a = s.index('        self._head(c, "NEW PROJECT", MAGENTA)\n')
    e = '            self._v68_old_ctl(c)\n'
    b = s.index(e) + len(e)
    if b < a or s.count(R0) != 1:
        raise Exception("anchors order/count %d" % s.count(R0))
    old = s[a:b]
    NEWCALL = ('        _v69_bar = None  # PROJ_LAYOUT_V69\n'
               '        try:\n'
               '            _v69_bar = self._v69_page(c)\n'
               '        except Exception as e:\n'
               '            self.err("v69 page", e)\n'
               '            try:\n'
               '                c.clear_widgets()\n'
               '            except Exception:\n'
               '                pass\n'
               '            self._v69_old_page(c)\n')
    s = s[:a] + NEWCALL + s[b:]
    s = s.replace(R0, R1, 1)
    A = "    def _proj_export(self):\n"
    if s.count(A) != 1:
        raise Exception("export anchor %d" % s.count(A))
    s = s.replace(A, H + "    def _v69_old_page(self, c):\n" + old + "\n" + A, 1)
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
except Exception as e:
    shutil.copy(F + ".bak69", F)
    sys.exit("STOPPED and rolled back: " + str(e))
print("PATCHED v69 OK")
