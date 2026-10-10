
ROUTE = re.compile(r"^\s*(?:please\s+)?(?:ask|tell|send to|use)\s+(claude|gemini|groq|chatgpt)\b[\s,:-]*", re.I)

def route(text):
    m = ROUTE.match(text)
    if not m:
        return None, text
    return m.group(1).lower(), text[m.end():].strip()
