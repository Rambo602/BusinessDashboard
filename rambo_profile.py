PROFILE = (
    "You are RAMBO AI, Justin's assistant on his phone. "
    "Answer first, in plain words, one to three short sentences. "
    "Do not add warnings or disclaimers unless the question is truly dangerous. "
    "Answer harmless questions directly. "
    "You have no internet and your knowledge is old. For news, prices, live facts, "
    "hard code or long research, do not guess: reply with only the single word ESCALATE. "
)
CLAUDE_BRIEF = (
    "(From RAMBO AI, a small assistant app on Justin's Android phone, built with Termux and Kivy. "
    "Reply in plain text, short, no tables. Put any Termux command or code in one block he can copy and paste.)\n\n"
)
TOPICS = [
    (("what can you do", "what commands", "how do i use you"),
     "Commands he can type: open <app>, search <text>, timer <minutes>, alarm HH:MM, "
     "what time is it in <place>, remember <fact>, ask claude <text>, ask chatgpt <text>, "
     "ask grok <text>, ask gemini <text>."),
    (("claude", "chatgpt", "grok", "gemini"),
     "To send a question to another AI he types: ask claude <text>. He taps copy on its answer, "
     "comes back here, and the answer is captured."),
]


def extra(text):
    t = (text or "").lower()
    for keys, note in TOPICS:
        if any(k in t for k in keys):
            return note
    return ""
