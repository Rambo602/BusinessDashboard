import shutil
import sys

P = "main.py"
s = open(P, encoding="utf-8").read()


def cut(s, a, b, new):
    i = s.index(a)
    j = s.index(b, i)
    return s[:i] + new + s[j:]


def rep(s, old, new):
    if s.count(old) != 1:
        raise ValueError("anchor not unique or missing: " + old[:50])
    return s.replace(old, new)


BUBBLE = r'''class Bubble(Label):
    def __init__(self, mine=False, **kw):
        super().__init__(**kw)
        self.mine = mine
        self.size_hint_y = None
        self.halign = "left"
        self.valign = "middle" if mine else "top"
        self.font_size = "17sp"
        self.color = (1, 1, 1, 1) if mine else (0.92, 0.96, 1.0, 1)
        self._rect = None
        if mine:
            with self.canvas.before:
                Color(0.12, 0.17, 0.30, 1)
                self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[20])
        self.bind(pos=self._upd, size=self._upd,
                  width=self._tw, texture_size=self._th)

    def _tw(self, *a):
        pad = 28 if self.mine else 6
        self.text_size = (max(self.width - pad, 10), None)

    def _th(self, *a):
        self.height = self.texture_size[1] + (26 if self.mine else 14)

    def _upd(self, *a):
        if self._rect is not None:
            self._rect.pos = self.pos
            self._rect.size = self.size


'''

CHAT = r'''    def build_chat(self):
        v = BoxLayout(orientation="vertical", spacing=6)
        self.chat_view = v

        top = BoxLayout(size_hint_y=None, height=44, spacing=6)
        title = Label(text="RAMBO AI", color=TXT, bold=True, font_size="19sp",
                      halign="left", valign="middle", padding=[10, 0])
        title.bind(size=lambda w, sz: setattr(w, "text_size", sz))
        top.add_widget(title)
        newb = NeonButton(glow=MAGENTA, text="NEW CHAT", size_hint_x=0.34,
                          font_size="12sp")
        newb.bind(on_press=lambda *a: self.new_chat())
        top.add_widget(newb)
        v.add_widget(top)

        self.chat_scroll = ScrollView()
        self.chat_box = BoxLayout(orientation="vertical", size_hint_y=None,
                                  spacing=10, padding=[6, 6])
        self.chat_box.bind(minimum_height=self.chat_box.setter("height"))
        self.chat_scroll.add_widget(self.chat_box)
        v.add_widget(self.chat_scroll)

        self.chips_row = BoxLayout(size_hint_y=None, height=40, spacing=6)
        for label, cmd in (("YouTube", "open youtube"),
                           ("10 min timer", "set a timer for 10 minutes"),
                           ("My tasks", "show my tasks")):
            cb = NeonButton(glow=CYAN, text=label, font_size="12sp")
            cb.bind(on_press=lambda inst, c=cmd: self.chip_go(c))
            self.chips_row.add_widget(cb)
        v.add_widget(self.chips_row)

        pill = BoxLayout(size_hint_y=None, height=58, spacing=4,
                         padding=[14, 4, 4, 4])
        with pill.canvas.before:
            Color(0.09, 0.11, 0.19, 1)
            pr = RoundedRectangle(pos=pill.pos, size=pill.size, radius=[28])
            Color(0.0, 0.9, 1.0, 0.35)
            pl = Line(rounded_rectangle=(pill.x, pill.y, pill.width, pill.height, 28),
                      width=1.2)

        def _pill(*a):
            pr.pos = pill.pos
            pr.size = pill.size
            pl.rounded_rectangle = (pill.x, pill.y, pill.width, pill.height, 28)

        pill.bind(pos=_pill, size=_pill)
        self.msg_input = TextInput(input_type="text", keyboard_suggestions=True,
                                   hint_text="Message RAMBO AI",
                                   multiline=False, font_size="18sp",
                                   background_color=(0, 0, 0, 0),
                                   foreground_color=TXT, cursor_color=CYAN,
                                   hint_text_color=(0.4, 0.55, 0.65, 1),
                                   padding=[2, 15, 2, 0])
        self.msg_input.bind(on_text_validate=self.on_send)
        pill.add_widget(self.msg_input)
        mic = NeonButton(glow=GREEN, text="MIC", size_hint=(None, 1),
                         width=62, font_size="14sp")
        mic.bind(on_press=self.on_mic)
        pill.add_widget(mic)
        send = NeonButton(glow=CYAN, text="SEND", size_hint=(None, 1),
                          width=68, font_size="14sp")
        send.bind(on_press=self.on_send)
        pill.add_widget(send)
        v.add_widget(pill)
        return v

    def chip_go(self, cmd):
        self.convo_active = False
        self.handle(cmd, False)

    def hide_chips(self):
        try:
            if self.chips_row.parent is not None:
                self.chips_row.parent.remove_widget(self.chips_row)
        except Exception:
            pass

    def new_chat(self):
        try:
            self.convo_active = False
            self.db.clear_chat()
            self.chat_box.clear_widgets()
            self.hist = []
            self.thinking = None
            if self.chips_row.parent is None:
                self.chat_view.add_widget(self.chips_row, index=1)
            self.add_msg("New chat. What can I do for you?", False)
        except Exception as e:
            self.err("new chat", e)

    def build_tools(self):
        sv, c = self._scroll()
        self._head(c, "VOICE", MAGENTA)
        row = BoxLayout(size_hint_y=None, height=46, spacing=6)
        self.b_talk = NeonButton(glow=MAGENTA, font_size="13sp")
        self.b_convo = NeonButton(glow=MAGENTA, font_size="13sp")
        self.b_auto = NeonButton(glow=MAGENTA, font_size="13sp")
        self.b_talk.bind(on_press=lambda *a: self.tog("talk"))
        self.b_convo.bind(on_press=lambda *a: self.tog("convo"))
        self.b_auto.bind(on_press=lambda *a: self.tog("auto"))
        for b in (self.b_talk, self.b_convo, self.b_auto):
            row.add_widget(b)
        c.add_widget(row)
        self.upd_toggles()
        self._head(c, "TOOLS", CYAN)
        for name, label, col in (("PHONE", "PHONE", GREEN),
                                 ("LOOKUP", "LOOKUP", AMBER),
                                 ("TASKS", "TASKS", GREEN),
                                 ("MORE", "MORE (key, tests, backup, log)", CYAN)):
            self._btn(c, label, lambda *a, n=name: self.switch(n), col, 56)
        return sv

'''

ADD_MSG = r'''    def add_msg(self, text, mine):
        b = Bubble(mine=mine, text=text)
        row = BoxLayout(size_hint_y=None, height=b.height, spacing=6)
        b.bind(height=lambda w, h: setattr(row, "height", h))
        if mine:
            b.size_hint_x = 0.82
            row.add_widget(Widget(size_hint_x=0.18))
            row.add_widget(b)
        else:
            b.size_hint_x = 1
            row.add_widget(b)
        self.chat_box.add_widget(row)
        Clock.schedule_once(lambda dt: setattr(self.chat_scroll, "scroll_y", 0), 0.15)
        return row

'''

BAR = r'''        bar = BoxLayout(size_hint_y=None, height=54, spacing=6)
        self.tab_btns = {}
        self.tab_views = {}
        builders = [("TALK", self.build_chat), ("PHONE", self.build_phone),
                    ("LOOKUP", self.build_lookup), ("PROJECT", self.build_projects),
                    ("TASKS", self.build_tasks), ("MORE", self.build_more),
                    ("TOOLS", self.build_tools)]
        for name, fn in builders:
            self.tab_views[name] = fn()
        for name, label, col in (("TALK", "CHAT", CYAN),
                                 ("PROJECT", "PROJECT", MAGENTA),
                                 ("TOOLS", "TOOLS", GREEN)):
            b = NeonButton(glow=col, text=label, font_size="14sp")
            b.bind(on_press=lambda inst, n=name: self.switch(n))
            self.tab_btns[name] = b
            bar.add_widget(b)
        root.add_widget(bar)
'''

try:
    s = cut(s, "class Bubble(Label):", "from kivy.graphics import Line", BUBBLE)
    s = cut(s, "    def build_chat(self):", "    def phone_go(self, cmd):", CHAT)
    s = cut(s, "    def add_msg(self, text, mine):", "    def remove_thinking(self):", ADD_MSG)
    s = cut(s, "        bar = BoxLayout(size_hint_y=None, height=58, spacing=5)",
            '        self.switch("TALK")', BAR)
    s = rep(s, "        for n, b in self.tab_btns.items():\n            b.set_active(n == name)",
            '        grp = "TOOLS" if name in ("PHONE", "LOOKUP", "TASKS", "MORE", "TOOLS") else name\n'
            "        for n, b in self.tab_btns.items():\n            b.set_active(n == grp)")
    s = rep(s, '        self.add_msg(text, True)\n        try:\n            self.db.add_chat("user", text)',
            '        self.add_msg(text, True)\n        self.hide_chips()\n        try:\n            self.db.add_chat("user", text)')
    s = rep(s, "        rows = self.db.recent_chat(30)\n",
            "        rows = self.db.recent_chat(30)\n        if rows:\n            self.hide_chips()\n")
    s = rep(s, "Hi! Tap the green button and say something like ",
            "Hi, I am RAMBO AI. Tap MIC and say something like ")
    if s.count("You are Pocket Pal,") != 2:
        raise ValueError("expected 2 'You are Pocket Pal,' prompts")
    s = s.replace("You are Pocket Pal,", "You are RAMBO AI,")
    s = rep(s, 'self.title = "Pocket Pal"', 'self.title = "RAMBO AI"')
    s = rep(s, "Save Pocket Pal backup", "Save RAMBO AI backup")
except ValueError as e:
    print("ABORT: " + str(e))
    sys.exit(1)

shutil.copy(P, "main.py.bak22")
open(P, "w", encoding="utf-8").write(s)
print("PATCH_V22_OK")
