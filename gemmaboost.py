"""gemmaboost: makes a small local model (Gemma in Termux) read long text better.

Standard library only. It does not change the model. It gives the model what small models
lack: a searchable index of long documents (SQLite FTS5 + BM25), map-reduce summarizing,
answers that must cite numbered excerpts, a programmatic check that quotes and numbers in
an answer really appear in the source, a shared tool loop, lessons retrieval, and a small
built-in test so improvement can be measured instead of guessed.
"""
import hashlib
import html
import json
import os
import re
import sqlite3
import time

MAX_DOC = 6 * 1024 * 1024
STOP = set("the and for are but not you all can had her was one our out has his how its may new now "
           "old see two way who did get let put say she too use what when where which with from this "
           "that have will your about into than them then they were been does".split())


class BoostError(Exception):
    pass


# ------------------------------------------------------------------ text prep

def strip_html(t):
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"[ \t]+", " ", html.unescape(t))


def clean_text(raw, name=""):
    t = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    if "\x00" in t[:4000]:
        raise BoostError("That looks like a binary file, not text. Use: prog pick")
    if name.lower().endswith((".html", ".htm")) or t.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        t = strip_html(t)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def chunk_text(text, size=1800, overlap=200):
    chunks, cur = [], ""
    for p in re.split(r"\n\s*\n", text):
        p = p.strip()
        while len(p) > size:
            cut = p.rfind(". ", 0, size)
            cut = cut + 1 if cut > size // 2 else size
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(p[:cut].strip())
            p = p[cut:].strip()
        if not p:
            continue
        if cur and len(cur) + len(p) + 2 > size:
            chunks.append(cur)
            cur = cur[-overlap:].split(" ", 1)[-1] + "\n\n" + p
        else:
            cur = (cur + "\n\n" + p) if cur else p
    if cur.strip():
        chunks.append(cur)
    return [c.strip() for c in chunks if c.strip()]


def tokens(q):
    out = []
    for w in re.findall(r"[A-Za-z0-9_]{3,}", q.lower()):
        if w not in STOP and w not in out:
            out.append(w)
    return out[:12]


# ------------------------------------------------------------------ document store

class DocStore(object):
    def __init__(self, path):
        self.path = path
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        c = self._c()
        c.execute("CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, name TEXT, sha TEXT UNIQUE, "
                  "chars INTEGER, chunks INTEGER, ts INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS chunks(doc_id INTEGER, n INTEGER, text TEXT, "
                  "PRIMARY KEY(doc_id, n))")
        c.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
        try:
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(text, doc_id UNINDEXED, n UNINDEXED)")
            self.fts = True
        except sqlite3.OperationalError:
            self.fts = False
        c.commit()
        c.close()

    def _c(self):
        return sqlite3.connect(self.path, timeout=10)

    def add(self, name, text):
        text = text[:MAX_DOC]
        sha = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
        c = self._c()
        try:
            row = c.execute("SELECT id FROM docs WHERE sha=?", (sha,)).fetchone()
            if row:
                self.set_current(row[0])
                return row[0], False
            ch = chunk_structured(text)
            if not ch:
                raise BoostError("No readable text in that file.")
            cur = c.execute("INSERT INTO docs(name, sha, chars, chunks, ts) VALUES(?,?,?,?,?)",
                            (name[:120], sha, len(text), len(ch), int(time.time())))
            did = cur.lastrowid
            c.executemany("INSERT INTO chunks VALUES(?,?,?)", [(did, i + 1, t) for i, t in enumerate(ch)])
            if self.fts:
                c.executemany("INSERT INTO fts(text, doc_id, n) VALUES(?,?,?)",
                              [(t, did, i + 1) for i, t in enumerate(ch)])
            c.commit()
        finally:
            c.close()
        self.set_current(did)
        return did, True

    def set_current(self, did):
        c = self._c()
        c.execute("INSERT OR REPLACE INTO meta VALUES('cur', ?)", (str(did),))
        c.commit()
        c.close()

    def current(self):
        c = self._c()
        try:
            r = c.execute("SELECT v FROM meta WHERE k='cur'").fetchone()
            if not r:
                return None
            d = c.execute("SELECT id FROM docs WHERE id=?", (int(r[0]),)).fetchone()
            return d[0] if d else None
        finally:
            c.close()

    def docs(self):
        c = self._c()
        try:
            return c.execute("SELECT id, name, chars, chunks FROM docs ORDER BY id DESC LIMIT 50").fetchall()
        finally:
            c.close()

    def info(self, did):
        c = self._c()
        try:
            return c.execute("SELECT id, name, chars, chunks FROM docs WHERE id=?", (did,)).fetchone()
        finally:
            c.close()

    def get_all(self, did):
        c = self._c()
        try:
            return c.execute("SELECT n, text FROM chunks WHERE doc_id=? ORDER BY n", (did,)).fetchall()
        finally:
            c.close()

    def search(self, did, q, k=5):
        toks = tokens(q)
        if not toks:
            return []
        c = self._c()
        try:
            if self.fts:
                try:
                    m = " OR ".join('"%s"' % t for t in toks)
                    rows = c.execute("SELECT n, text FROM fts WHERE fts MATCH ? AND doc_id=? "
                                     "ORDER BY bm25(fts) LIMIT ?", (m, did, k)).fetchall()
                    if rows:
                        return sorted(rows)
                except sqlite3.OperationalError:
                    pass
            scored = []
            for n, t in c.execute("SELECT n, text FROM chunks WHERE doc_id=?", (did,)):
                low = t.lower()
                s = sum(low.count(w) for w in toks)
                if s:
                    scored.append((s, n, t))
            scored.sort(key=lambda x: -x[0])
            return sorted((n, t) for _s, n, t in scored[:k])
        finally:
            c.close()

    def delete(self, did=None):
        c = self._c()
        try:
            if did is None:
                for t in ("docs", "chunks", "meta"):
                    c.execute("DELETE FROM " + t)
                if self.fts:
                    c.execute("DELETE FROM fts")
            else:
                c.execute("DELETE FROM docs WHERE id=?", (did,))
                c.execute("DELETE FROM chunks WHERE doc_id=?", (did,))
                if self.fts:
                    c.execute("DELETE FROM fts WHERE doc_id=?", (did,))
            c.commit()
        finally:
            c.close()


# ------------------------------------------------------------------ prompts

DOC_SYS = ("You answer questions about a document using ONLY the numbered excerpts you are given. "
           "Rules: 1) Find the sentence that answers the question first, then answer. 2) Put the "
           "excerpt number in square brackets after each fact, like [3]. 3) If the excerpts do not "
           "contain the answer, say exactly: Not stated in the document. Never guess. 4) Copy numbers, "
           "names and dates exactly. 5) Keep it short.")
MAP_SYS = ("You read one part of a long document. Write 3 short bullet points with only facts that are "
           "written in the text: names, numbers, dates, decisions, definitions. Do not add anything.")
REDUCE_SYS = ("You combine bullet notes from the parts of a document into one clear summary. Keep every "
              "name, number and date exactly as written. Do not add facts that are not in the notes.")


# ------------------------------------------------------------------ verification

def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s\.]", " ", s.lower())).strip()


def verify(answer, hits):
    """Cheap, non-model check. Returns a list of warnings about things not found in the excerpts."""
    src = " ".join(t for _n, t in hits)
    nsrc = _norm(src)
    warn = []
    valid = {n for n, _t in hits}
    cited = {int(x) for x in re.findall(r"\[(\d{1,4})\]", answer)}
    bad = sorted(cited - valid)
    if bad:
        warn.append("cites excerpt(s) %s which were not given" % ", ".join(map(str, bad)))
    if not cited and "not stated" not in answer.lower():
        warn.append("no excerpt numbers cited, so it cannot be checked")
    for q in re.findall(r'"([^"]{6,200})"', answer):
        if _norm(q) not in nsrc:
            warn.append('quote not found in the document: "%s"' % q[:60])
    body = re.sub(r"\[\d{1,4}\]", " ", answer)
    for num in set(re.findall(r"\b\d[\d,]*\.?\d*\b", body)):
        v = num.rstrip(".").replace(",", "")
        if len(v) >= 2 and v not in src.replace(",", ""):
            warn.append("number %s is not in the excerpts" % num)
    return warn[:6]


# ------------------------------------------------------------------ reading

def _short(s, n):
    return s if len(s) <= n else s[:n]


def answer_doc(llm, store, did, question, lessons="", k=5):
    hits = store.search(did, question, k)
    if not hits:
        return "Not stated in the document (no part of it matches those words). Try different words: doc find TEXT", [], []
    ex = "\n\n".join("[%d] %s" % (n, _short(t, 1800)) for n, t in hits)
    user = (lessons + "QUESTION: " + question + "\n\nEXCERPTS:\n" + ex +
            "\n\nAnswer now, citing excerpt numbers.")
    ans = llm(DOC_SYS, user, 450).strip()
    return ans, verify(ans, hits), [n for n, _ in hits]


def summarize_long(llm, store, did, progress=None, cancel=None, max_chunks=24):
    ch = store.get_all(did)
    if not ch:
        raise BoostError("Document is empty.")
    if len(ch) > max_chunks:
        step = len(ch) / float(max_chunks)
        ch = [ch[int(i * step)] for i in range(max_chunks)]
        sampled = True
    else:
        sampled = False
    notes = []
    for i, (n, t) in enumerate(ch):
        if cancel and cancel():
            raise BoostError("Cancelled.")
        if progress:
            progress("Reading part %d of %d" % (i + 1, len(ch)))
        notes.append("Part %d:\n%s" % (n, llm(MAP_SYS, _short(t, 1800), 220).strip()))
    while sum(len(x) for x in notes) > 5500 and len(notes) > 1:
        merged, cur = [], ""
        for x in notes:
            if cur and len(cur) + len(x) > 3500:
                merged.append(llm(REDUCE_SYS, cur, 300).strip())
                cur = ""
            cur += x + "\n"
        if cur:
            merged.append(llm(REDUCE_SYS, cur, 300).strip())
        if len(merged) >= len(notes):
            break
        notes = merged
    out = llm(REDUCE_SYS, "\n".join(notes), 500).strip()
    if sampled:
        out += "\n\n(The document is long, so %d evenly spaced parts were read. Ask doc ask <question> for details.)" % len(ch)
    return out


# ------------------------------------------------------------------ shared tool loop

def extract_json(txt):
    t = txt.strip()
    if t.startswith("```"):
        t = t.strip("`").replace("json", "", 1).strip()
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        v = json.loads(t[a:b + 1])
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def tool_loop(llm, sysm, user, run_tool, rounds=3, max_tokens=600):
    """Let the model ask for tools by replying with only {"tool":..., "args":{...}}.
    run_tool(name, args) must validate everything itself and raise on bad input."""
    seen = set()
    for _ in range(rounds):
        txt = llm(sysm, user, max_tokens)
        req = extract_json(txt) if txt.strip().startswith(("{", "`")) else None
        if not req or "tool" not in req:
            return txt
        key = json.dumps(req, sort_keys=True)[:300]
        if key in seen:
            user += "\n\n(You already asked for that. Answer now with what you have.)"
            continue
        seen.add(key)
        try:
            out = run_tool(req.get("tool"), req.get("args"))
        except Exception as e:
            out = "Tool refused: " + str(e)[:200]
        user += "\n\n## TOOL RESULT " + key[:200] + "\n" + str(out)[:3000]
    return llm(sysm, user + "\n\nAnswer now with the evidence you have. Do not request more tools.", max_tokens)


# ------------------------------------------------------------------ built-in test

EVAL = (
    ("The Alder Street library opens at 9 a.m. on weekdays and 11 a.m. on Saturdays. It is closed on "
     "Sundays. Late fees were removed in 2022, but damaged books still cost the replacement price.",
     "What time does the library open on Saturday?", r"\b11\b"),
    ("The Alder Street library opens at 9 a.m. on weekdays and 11 a.m. on Saturdays. It is closed on "
     "Sundays. Late fees were removed in 2022, but damaged books still cost the replacement price.",
     "Does the library charge late fees today?", r"removed|no late|no longer|not charge|doesn.t charge|\bno\b"),
    ("Team A shipped 14 units in May and twice as many in June. Team B shipped 30 units in June.",
     "How many more units did Team B ship in June than Team A?", r"(?<![\d.])2(?![\d.])"),
    ("The recipe needs 2 eggs and 200 g of flour. Bake for 25 minutes.",
     "How much sugar does the recipe need?",
     r"not (stated|mention|specif|given|say|listed|included)|doesn.t (say|mention|state|specif|list)|cannot be determined|no (mention|information)"),
    ("Maya said she would not attend the Monday meeting but would join on Tuesday.",
     "On which day will Maya attend?", r"tuesday"),
    ("The warning label reads: Keep below 30 degrees Celsius. Do not freeze.",
     "What temperature limit does the label give?", r"\b30\b"),
)


def run_eval(llm, scaffold):
    results = []
    for passage, q, pat in EVAL:
        if scaffold:
            user = "QUESTION: " + q + "\n\nEXCERPTS:\n[1] " + passage + "\n\nAnswer now, citing excerpt numbers."
            ans = llm(DOC_SYS, user, 150)
        else:
            ans = llm("", passage + "\n\n" + q, 150)
        ok = bool(re.search(pat, ans.lower()))
        results.append((q, ok, ans.strip()[:80]))
    return results


def save_eval(root, label, score, total):
    p = os.path.join(root, "evals.json")
    try:
        rows = json.load(open(p))
    except (OSError, ValueError):
        rows = []
    rows.append({"label": label, "score": score, "total": total, "ts": int(time.time())})
    tmp = p + ".part"
    json.dump(rows[-100:], open(tmp, "w"))
    os.replace(tmp, p)
    return rows[-10:]


def lessons_block(rows):
    if not rows:
        return ""
    return ("NOTES FROM THE USER (may help, but the document wins if they disagree):\n" +
            "\n".join("- " + r["text"][:300] for r in rows) + "\n\n")


def unsupported_names(answer, evidence, limit=5):
    """Names in an answer (snake_case, dotted, CamelCase) that never appear in the evidence."""
    ev = evidence.lower()
    out = []
    for w in re.findall(r"[A-Za-z_][A-Za-z0-9_\.]{5,60}", answer):
        w = w.strip(".")
        if not (("_" in w) or ("." in w and re.search(r"[A-Za-z]\.[A-Za-z]", w)) or re.search(r"[a-z][A-Z]", w)):
            continue
        if w.lower() not in ev and w not in out:
            out.append(w)
        if len(out) >= limit:
            break
    return out


# ================================================================== v46 additions
import io
import zipfile
import zlib
import csv as _csv

_HEAD_RE = re.compile(r"^(#{1,6}\s+.+|[A-Z][A-Z0-9 \-:&,/]{3,70}|(?:\d+\.)+\d*\s+[A-Z].{2,70}|"
                      r"(?:Chapter|Section|Part|Article)\s+[\w\.]+.{0,60})$")


def chunk_structured(text, size=1800):
    """Like chunk_text but each part starts with its section heading, so a part that says
    'it must be below 30 C' still tells the model which section it belongs to."""
    lines = text.split("\n")
    sections, head, buf = [], "", []
    for ln in lines:
        s = ln.strip()
        if s and len(s) <= 80 and _HEAD_RE.match(s) and not s.endswith((".", ",", ";")):
            if buf:
                sections.append((head, "\n".join(buf)))
            head, buf = s.lstrip("# ").strip(), []
        else:
            buf.append(ln)
    if buf:
        sections.append((head, "\n".join(buf)))
    out = []
    for h, body in sections:
        for c in chunk_text(body, size - 60 if h else size):
            out.append(("[Section: %s]\n" % h[:70] + c) if h else c)
    return out or chunk_text(text, size)


def outline(store, did, limit=40):
    seen, rows = set(), []
    for n, t in store.get_all(did):
        m = re.match(r"\[Section: (.+?)\]", t)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            rows.append("%d  %s" % (n, m.group(1)))
    return rows[:limit]


# ----- readers for more file types (standard library only) -----

def _xml_text(xml):
    xml = re.sub(r"</(w:p|text:p|text:h|p|div|br|li|tr)[^>]*>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    return re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", "", xml)))


def _pdf_text(raw):
    """Best effort for simple text PDFs only: Flate streams, Tj/TJ text operators.
    Scanned PDFs, custom fonts and encrypted files will not work."""
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
        d = m.group(1)
        try:
            d = zlib.decompress(d)
        except zlib.error:
            continue
        if b"BT" not in d:
            continue
        for bt in re.findall(rb"BT(.*?)ET", d, re.S):
            line = []
            for arr in re.findall(rb"\[(.*?)\]\s*TJ|\((.*?)(?<!\\)\)\s*Tj", bt, re.S):
                a = arr[0] or arr[1]
                for s in re.findall(rb"\(((?:\\.|[^\\)])*)\)", a) or ([a] if arr[1] else []):
                    s = re.sub(rb"\\(.)", rb"\1", s)
                    line.append(s.decode("latin-1", "replace"))
            if line:
                out.append("".join(line))
    t = "\n".join(out)
    if len(re.findall(r"[A-Za-z]{3,}", t)) < 20:
        raise BoostError("Could not read text from that PDF (scanned, encrypted or unusual fonts). "
                         "Attach it with + so Gemini can read it, or copy the text out.")
    return t


def read_any(raw, name=""):
    """Turn a file's bytes into clean text. Raises BoostError with a clear reason."""
    n = name.lower()
    head = raw[:8]
    if head[:2] == b"PK":
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            raise BoostError("That zip file is damaged.")
        names = zf.namelist()
        if "word/document.xml" in names:
            return clean_text(_xml_text(zf.read("word/document.xml").decode("utf-8", "replace")), "x.txt")
        if "content.xml" in names:
            return clean_text(_xml_text(zf.read("content.xml").decode("utf-8", "replace")), "x.txt")
        pages = sorted(x for x in names if x.lower().endswith((".xhtml", ".html", ".htm")))
        if pages:
            return clean_text("\n\n".join(strip_html(zf.read(p).decode("utf-8", "replace")) for p in pages[:300]), "x.txt")
        raise BoostError("That zip has no readable text document in it (it may be a program: use prog pick).")
    if head[:4] == b"%PDF" or n.endswith(".pdf"):
        return clean_text(_pdf_text(raw), "x.txt")
    if head[:5] == b"{\\rtf":
        t = raw.decode("latin-1", "replace")
        t = re.sub(r"\\par[d]?", "\n", t)
        t = re.sub(r"\\'[0-9a-f]{2}|\\[a-z]+-?\d* ?|[{}]", "", t)
        return clean_text(t, "x.txt")
    t = clean_text(raw, name)
    if n.endswith(".csv") or n.endswith(".tsv"):
        try:
            rows = list(_csv.reader(io.StringIO(t), delimiter="\t" if n.endswith(".tsv") else ","))
            if rows and len(rows) > 1:
                hdr = [h.strip() for h in rows[0]]
                t = "\n".join("Row %d: " % (i + 1) + "; ".join("%s = %s" % (h, v.strip()) for h, v in zip(hdr, r) if v.strip())
                               for i, r in enumerate(rows[1:]))
        except _csv.Error:
            pass
    elif n.endswith(".json"):
        try:
            t = json.dumps(json.loads(t), indent=1, ensure_ascii=False)
        except ValueError:
            pass
    return t


# ----- knowledge: bundled file (rambo_knowledge.py) plus the user's own notes -----

def _split_sections(txt):
    secs = []
    for p in re.split(r"(?m)^## ", txt)[1:]:
        title, _, body = p.partition("\n")
        secs.append((title.strip(), body.strip()))
    return secs


def kb_sections(user_dir=None):
    secs = []
    try:
        import rambo_knowledge
        secs += _split_sections(rambo_knowledge.TEXT)
    except Exception:
        pass
    if user_dir:
        try:
            secs += _split_sections(open(os.path.join(user_dir, "my_knowledge.md"), encoding="utf-8").read())
        except OSError:
            pass
    return secs


def kb_add_note(user_dir, title, body):
    p = os.path.join(user_dir, "my_knowledge.md")
    with open(p, "a", encoding="utf-8") as f:
        f.write("\n## %s\n%s\n" % (title.strip()[:70], body.strip()[:1500]))


def kb_search(secs, query, k=3, maxchars=1500):
    """Keyword scoring with a title bonus over the knowledge sections."""
    generic = {"file", "files", "program", "code", "text", "answer", "document", "work", "works", "thing",
               "make", "use", "used", "using", "tell", "show", "give", "does", "doing", "need", "like", "also"}
    toks = [w for w in tokens(query) if w not in generic]
    if not secs or not toks:
        return []
    scored = []
    for title, body in secs:
        tl, bl = title.lower(), body.lower()
        s = 0.0
        for w in toks:
            c = bl.count(w)
            if c:
                s += 2 + min(c - 1, 2)
            if w in tl:
                s += 4
        if s > 0:
            scored.append((s, title, body))
    scored.sort(key=lambda x: -x[0])
    return [(t, b[:maxchars]) for _s, t, b in scored[:k] if _s >= 2]


def kb_block(secs, query, k=3, maxchars=900):
    hits = kb_search(secs, query, k, maxchars)
    if not hits:
        return ""
    return ("REFERENCE NOTES (general background; the file or document evidence wins if they differ):\n" +
            "\n".join("- %s: %s" % (t, b.replace("\n", " ")) for t, b in hits) + "\n\n")


# ----- multi-step reading pipeline -----

EXPAND_SYS = ("You help search a document. Given a question, list 6 to 10 search words or short phrases that "
              "could appear in the passage that answers it: key nouns, synonyms, number words, related terms. "
              "Reply with only the words, separated by commas.")
EXTRACT_SYS = ("You read ONE excerpt and a question. Copy the sentences or numbers from the excerpt that help answer "
               "the question, exactly as written. If nothing in the excerpt helps, reply only: NONE. Do not add anything.")
REPAIR_SYS = ("You fix an answer. Using ONLY the numbered excerpts, rewrite the answer so every fact is in the excerpts "
              "and cites its number like [3]. Remove anything the excerpts do not support. If the excerpts do not "
              "answer the question, say exactly: Not stated in the document.")


def expand_query(llm, question):
    base = tokens(question)
    try:
        txt = llm(EXPAND_SYS, question, 60)
    except Exception:
        return base
    extra = []
    for w in re.split(r"[,\n;]", txt):
        for t in tokens(w):
            if t not in base and t not in extra:
                extra.append(t)
    return (base + extra)[:18]


def _rerank(hits, question, keep):
    qt = set(tokens(question))
    ql = question.lower()
    sc = []
    for n, t in hits:
        low = t.lower()
        s = sum(1 for w in qt if w in low) + (2 if any(p in low for p in re.findall(r'"([^"]+)"', ql)) else 0)
        sc.append((s, n, t))
    sc.sort(key=lambda x: -x[0])
    return sorted((n, t) for _s, n, t in sc[:keep])


def deep_read(llm, store, did, question, lessons="", kb_text="", progress=None, keep=5):
    """Expand the question, retrieve, extract facts per excerpt, answer with citations,
    check, and repair once if the check fails. Returns (answer, warnings, used, steps)."""
    def say(m):
        if progress:
            progress(m)
    steps = []
    say("1/5 Widening the search words")
    terms = expand_query(llm, question)
    steps.append("search words: " + ", ".join(terms[:10]))
    hits = store.search(did, " ".join(terms), 10) or store.search(did, question, 10)
    if not hits:
        return "Not stated in the document (no part of it matches). Try: doc find TEXT", [], [], steps
    hits = _rerank(hits, question, keep)
    say("2/5 Reading %d best parts" % len(hits))
    notes, kept = [], []
    for n, t in hits:
        r = llm(EXTRACT_SYS, "QUESTION: %s\n\nEXCERPT:\n%s" % (question, _short(t, 1800)), 160).strip()
        if r and not r.upper().startswith("NONE"):
            notes.append("[%d] %s" % (n, r))
            kept.append((n, t))
    steps.append("%d of %d parts had relevant facts" % (len(kept), len(hits)))
    if not kept:
        return "Not stated in the document.", [], [n for n, _ in hits], steps
    say("3/5 Writing the answer")
    ex = "\n\n".join("[%d] %s" % (n, _short(t, 1500)) for n, t in kept)
    user = (lessons + kb_text + "QUESTION: " + question + "\n\nKEY FACTS FOUND:\n" + "\n".join(notes) +
            "\n\nFULL EXCERPTS:\n" + ex + "\n\nAnswer now, citing excerpt numbers.")
    ans = llm(DOC_SYS, user, 450).strip()
    say("4/5 Checking against the source")
    warn = verify(ans, kept)
    if warn and not ans.lower().startswith("not stated"):
        say("5/5 Fixing unsupported parts")
        fix = llm(REPAIR_SYS, "QUESTION: %s\n\nANSWER TO FIX:\n%s\n\nPROBLEMS FOUND: %s\n\nEXCERPTS:\n%s"
                  % (question, ans, "; ".join(warn), ex), 400).strip()
        w2 = verify(fix, kept)
        steps.append("repaired once (%d problems -> %d)" % (len(warn), len(w2)))
        if len(w2) <= len(warn) and fix:
            ans, warn = fix, w2
    return ans, warn, [n for n, _ in kept], steps


def looks_hard(question):
    q = question.lower()
    return (len(q) > 140 or q.count("?") > 1 or any(w in q for w in (
        "compare", "difference", "versus", " vs ", "why ", "how many", "total", "list all", "every ", "both",
        "summarize the", "explain how", "and also")))
