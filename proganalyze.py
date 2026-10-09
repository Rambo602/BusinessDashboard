"""proganalyze: static analysis of any file or program for RAMBO AI, plus a lessons memory.

Standard library only. It NEVER runs, imports or installs the file it reads. It parses
headers (ELF, PE), extracts strings, parses Python with ast, scans scripts with regex, and
lists archives. It does not disassemble machine code.
"""
import ast
import hashlib
import json
import math
import os
import re
import shutil
import struct
import time
import zipfile

SCHEMA = 1
VERSION = 46
MAX_FILE = 300 * 1024 * 1024
MAX_SRC = 3 * 1024 * 1024
MAX_STR = 400000
MAX_SYMS = 200000
MAX_OUT = 3500


class ProgError(Exception):
    pass


class Cancelled(Exception):
    pass


class ToolError(Exception):
    pass


# ------------------------------------------------------------------ helpers

def copy_stream(src, dst, limit=MAX_FILE, cancel=None, progress=None):
    h = hashlib.sha256()
    n = 0
    tmp = dst + ".part"
    try:
        with open(tmp, "wb") as out:
            while True:
                if cancel and cancel():
                    raise Cancelled()
                b = src.read(1 << 20)
                if not b:
                    break
                n += len(b)
                if n > limit:
                    raise ProgError("The file is larger than the %d MB limit." % (limit >> 20))
                h.update(b)
                out.write(b)
                if progress:
                    progress(n)
        os.replace(tmp, dst)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return n, h.hexdigest()


def entropy(b):
    if not b:
        return 0.0
    c = [0] * 256
    for x in b:
        c[x] += 1
    n = float(len(b))
    return -sum((v / n) * math.log(v / n, 2) for v in c if v)


MAGIC = ((b"\x7fELF", "elf"), (b"MZ", "pe"), (b"PK\x03\x04", "zip"), (b"%PDF", "pdf"),
         (b"\x1f\x8b", "gzip"), (b"SQLite format 3\x00", "sqlite"), (b"dex\n", "dex"),
         (b"\xca\xfe\xba\xbe", "java_class_or_macho_fat"), (b"\xcf\xfa\xed\xfe", "macho"),
         (b"\xfe\xed\xfa\xcf", "macho"), (b"\xce\xfa\xed\xfe", "macho"),
         (b"7z\xbc\xaf\x27\x1c", "7z"), (b"Rar!", "rar"), (b"BZh", "bzip2"),
         (b"\x89PNG", "png"), (b"\xff\xd8\xff", "jpeg"), (b"GIF8", "gif"), (b"\xfd7zXZ", "xz"))


def detect(path, head):
    for m, k in MAGIC:
        if head.startswith(m):
            return k
    if head.startswith(b"#!"):
        first = head.split(b"\n", 1)[0].decode("latin-1").lower()
        if "python" in first:
            return "python"
        if "node" in first:
            return "javascript"
        return "shell"
    if b"\x00" in head[:4096]:
        return "binary"
    ext = os.path.splitext(path.lower())[1]
    return {".py": "python", ".sh": "shell", ".js": "javascript", ".mjs": "javascript",
            ".json": "json", ".html": "html", ".htm": "html", ".xml": "xml", ".c": "c",
            ".h": "c", ".cpp": "c", ".java": "java", ".kt": "kotlin", ".php": "php",
            ".rb": "ruby", ".pl": "perl", ".lua": "lua", ".go": "go", ".rs": "rust",
            ".ps1": "powershell", ".bat": "batch", ".cmd": "batch"}.get(ext, "text")


# ------------------------------------------------------------------ knowledge table
# what common imported functions usually mean (starting knowledge; lessons add to it)
API = {
    "socket": "creates a network socket", "connect": "opens a network connection",
    "bind": "listens on a port", "listen": "accepts incoming connections", "accept": "accepts a client",
    "send": "sends network data", "recv": "receives network data", "getaddrinfo": "DNS lookup",
    "gethostbyname": "DNS lookup", "curl_easy_perform": "HTTP request (libcurl)",
    "SSL_connect": "TLS connection (OpenSSL)", "SSL_read": "reads TLS data", "SSL_write": "writes TLS data",
    "fork": "creates a child process", "execve": "runs another program", "execl": "runs another program",
    "execv": "runs another program", "execvp": "runs another program", "system": "runs a shell command",
    "popen": "runs a shell command and reads output", "posix_spawn": "starts a process",
    "ptrace": "debugging or anti-debugging", "dlopen": "loads a library at runtime",
    "dlsym": "looks up a function at runtime", "mmap": "maps memory or a file",
    "mprotect": "changes memory permissions (look for exec)", "open": "opens a file",
    "fopen": "opens a file", "read": "reads a file or descriptor", "write": "writes a file or descriptor",
    "unlink": "deletes a file", "remove": "deletes a file", "rename": "renames a file",
    "chmod": "changes file permissions", "chown": "changes file owner", "stat": "reads file info",
    "opendir": "lists a directory", "readdir": "lists a directory", "malloc": "allocates memory",
    "free": "frees memory", "memcpy": "copies memory", "strcpy": "unbounded string copy (bug risk)",
    "strcat": "unbounded string append (bug risk)", "gets": "unsafe input (bug risk)",
    "sprintf": "unbounded format (bug risk)", "printf": "prints text", "puts": "prints text",
    "getenv": "reads environment variable", "setenv": "sets environment variable",
    "signal": "installs a signal handler", "sigaction": "installs a signal handler",
    "pthread_create": "starts a thread", "getuid": "checks user id", "setuid": "changes user id",
    "ioctl": "device control call", "uname": "reads system info", "gettimeofday": "reads time",
    "time": "reads time", "sleep": "waits", "usleep": "waits", "rand": "random numbers (weak)",
    "EVP_EncryptInit_ex": "encryption (OpenSSL)", "EVP_DecryptInit_ex": "decryption (OpenSSL)",
    "MD5_Init": "MD5 hash", "SHA256_Init": "SHA-256 hash",
    "CreateProcessA": "starts a process (Windows)", "CreateProcessW": "starts a process (Windows)",
    "WinExec": "runs a program (Windows)", "ShellExecuteA": "runs a program or opens a file (Windows)",
    "ShellExecuteW": "runs a program or opens a file (Windows)",
    "VirtualAlloc": "allocates memory (Windows)", "VirtualProtect": "changes memory permissions (Windows)",
    "WriteProcessMemory": "writes into another process (injection risk)",
    "ReadProcessMemory": "reads another process", "CreateRemoteThread": "runs code in another process (injection risk)",
    "LoadLibraryA": "loads a DLL", "LoadLibraryW": "loads a DLL", "GetProcAddress": "looks up a function at runtime",
    "RegOpenKeyExA": "reads the registry", "RegSetValueExA": "writes the registry",
    "RegSetValueExW": "writes the registry", "InternetOpenA": "HTTP via WinINet",
    "InternetOpenUrlA": "downloads a URL", "URLDownloadToFileA": "downloads a file",
    "WSAStartup": "starts Winsock networking", "IsDebuggerPresent": "anti-debugging check",
    "CreateFileA": "opens a file (Windows)", "CreateFileW": "opens a file (Windows)",
    "DeleteFileA": "deletes a file (Windows)", "GetTickCount": "reads time (Windows)",
    "CryptEncrypt": "encryption (Windows)", "CryptDecrypt": "decryption (Windows)",
}
PY_RISK = {"eval": "runs text as code", "exec": "runs text as code", "compile": "compiles code from text",
           "__import__": "dynamic import", "os.system": "runs a shell command",
           "subprocess": "runs other programs", "pickle.loads": "unsafe deserialization",
           "marshal.loads": "loads raw code objects", "ctypes": "calls native libraries",
           "socket": "network sockets", "requests": "HTTP requests", "urllib": "HTTP requests",
           "base64.b64decode": "decodes hidden data", "os.remove": "deletes files",
           "shutil.rmtree": "deletes folders", "input": "reads user input"}
STR_CATS = (
    ("urls", re.compile(r"(?:https?|wss?|ftp)://[^\s\"'<>\\]{4,200}")),
    ("ips", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?\b")),
    ("paths", re.compile(r"(?:/(?:etc|proc|sys|dev|tmp|data|system|usr|bin|var|home)/[\w./\-]{2,80}|[A-Za-z]:\\[\w\\. \-]{3,80})")),
    ("commands", re.compile(r"\b(?:/bin/(?:ba)?sh|cmd\.exe|powershell|chmod \+x|curl |wget |nc -|rm -rf|su -c)[^\n]{0,60}")),
)
SECRET_RE = re.compile(
    r"AIza[0-9A-Za-z_\-]{35}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"xox[baprs]-[0-9A-Za-z\-]{10,}|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{24,}|"
    r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{1,200}\.[A-Za-z]{2,}")


def mask(s):
    s = str(s)
    return s[:6] + "...(%d chars)" % len(s)


def scrub(text):
    text = SECRET_RE.sub("[REDACTED]", text)
    text = EMAIL_RE.sub("[EMAIL]", text)
    return re.sub(r"(?i)(bearer|api[_-]?key|secret|password|token)(\W{0,3})[A-Za-z0-9_\-\.]{12,}",
                  r"\1\2[REDACTED]", text)


# ------------------------------------------------------------------ ELF

MACHINE = {3: "x86", 8: "MIPS", 20: "PowerPC", 40: "ARM", 62: "x86-64", 183: "AArch64",
           243: "RISC-V", 21: "PowerPC64", 164: "Hexagon"}
ETYPE = {1: "relocatable", 2: "executable", 3: "shared object / PIE", 4: "core dump"}


def parse_elf(f, size):
    f.seek(0)
    h = f.read(64)
    if len(h) < 52 or h[:4] != b"\x7fELF":
        raise ProgError("Not an ELF file.")
    is64 = h[4] == 2
    e = "<" if h[5] == 1 else ">"
    if is64:
        (et, em, _v, entry, _phoff, shoff, _fl, _eh, _phs, _phn, shentsize, shnum,
         shstr) = struct.unpack_from(e + "HHIQQQIHHHHHH", h, 16)
    else:
        (et, em, _v, entry, _phoff, shoff, _fl, _eh, _phs, _phn, shentsize, shnum,
         shstr) = struct.unpack_from(e + "HHIIIIIHHHHHH", h, 16)
    out = {"bits": 64 if is64 else 32, "endian": "little" if e == "<" else "big",
           "type": ETYPE.get(et, str(et)), "machine": MACHINE.get(em, "id %d" % em),
           "entry": "0x%x" % entry, "sections": [], "needed": [], "soname": "", "interp": "",
           "symbols": [], "stripped": True, "notes": []}
    if not shoff or not shnum or shoff + shnum * (64 if is64 else 40) > size:
        out["notes"].append("No usable section table (stripped or packed). Symbols may be missing.")
        return out
    fmt = e + ("IIQQQQIIQQ" if is64 else "IIIIIIIIII")
    sz = 64 if is64 else 40
    f.seek(shoff)
    raw = f.read(sz * shnum)
    secs = []
    for i in range(shnum):
        if (i + 1) * sz > len(raw):
            break
        t = struct.unpack_from(fmt, raw, i * sz)
        if is64:
            nm, ty, fl, addr, off, ssize, link, info, _al, ent = t
        else:
            nm, ty, fl, addr, off, ssize, link, info, _al, ent = t
        secs.append({"name_off": nm, "type": ty, "flags": fl, "addr": addr, "off": off,
                     "size": ssize, "link": link, "ent": ent})

    def sec_data(s, cap=64 * 1024 * 1024):
        if s["type"] == 8 or s["size"] > cap or s["off"] + s["size"] > size:
            return b""
        f.seek(s["off"])
        return f.read(s["size"])

    names = b""
    if 0 <= shstr < len(secs):
        names = sec_data(secs[shstr])

    def cstr(buf, o):
        if o >= len(buf):
            return ""
        e2 = buf.find(b"\0", o)
        return buf[o:e2 if e2 >= 0 else len(buf)].decode("utf-8", "replace")
    for s in secs:
        s["name"] = cstr(names, s["name_off"])
        if s["name"]:
            out["sections"].append("%s (%d bytes)" % (s["name"], s["size"]))
    out["sections"] = out["sections"][:60]
    for s in secs:
        if s["name"] == ".interp":
            out["interp"] = cstr(sec_data(s), 0)
        if s["type"] == 6 and s["link"] < len(secs):  # dynamic
            d = sec_data(s)
            strtab = sec_data(secs[s["link"]])
            esz = 16 if is64 else 8
            for k in range(0, len(d) - esz + 1, esz):
                tag, val = struct.unpack_from(e + ("qQ" if is64 else "iI"), d, k)
                if tag == 0:
                    break
                if tag == 1:
                    out["needed"].append(cstr(strtab, val))
                elif tag == 14:
                    out["soname"] = cstr(strtab, val)
        if s["type"] in (2, 11) and s["link"] < len(secs):  # symtab, dynsym
            if s["type"] == 2:
                out["stripped"] = False
            strtab = sec_data(secs[s["link"]])
            d = sec_data(s)
            esz = 24 if is64 else 16
            for k in range(0, len(d) - esz + 1, esz):
                if len(out["symbols"]) >= MAX_SYMS:
                    out["notes"].append("Symbol list cut at %d." % MAX_SYMS)
                    break
                if is64:
                    nm, info, _o, shndx, val, ssz = struct.unpack_from(e + "IBBHQQ", d, k)
                else:
                    nm, val, ssz, info, _o, shndx = struct.unpack_from(e + "IIIBBH", d, k)
                name = cstr(strtab, nm)
                if not name:
                    continue
                kind = {0: "notype", 1: "object", 2: "func", 3: "section", 4: "file"}.get(info & 15, "other")
                out["symbols"].append([name, "undef" if shndx == 0 else "defined", kind, val, ssz])
    seen = set()
    uniq = []
    for sy in out["symbols"]:
        key = (sy[0], sy[1])
        if key not in seen:
            seen.add(key)
            uniq.append(sy)
    out["symbols"] = uniq
    return out


# ------------------------------------------------------------------ PE

def parse_pe(f, size):
    f.seek(0)
    h = f.read(64)
    if len(h) < 64 or h[:2] != b"MZ":
        raise ProgError("Not a PE file.")
    pe = struct.unpack_from("<I", h, 0x3C)[0]
    if pe + 24 > size:
        raise ProgError("Not a Windows PE (MZ only, probably a DOS stub).")
    f.seek(pe)
    hd = f.read(24)
    if hd[:4] != b"PE\0\0":
        raise ProgError("PE signature missing.")
    mach, nsec, ts, _sp, _ns, optsz, chars = struct.unpack_from("<HHIIIHH", hd, 4)
    f.seek(pe + 24)
    opt = f.read(optsz)
    magic = struct.unpack_from("<H", opt, 0)[0] if len(opt) >= 2 else 0
    is64 = magic == 0x20B
    ddoff = 112 if is64 else 96
    out = {"machine": {0x14c: "x86", 0x8664: "x86-64", 0x1c0: "ARM", 0xaa64: "ARM64"}.get(mach, hex(mach)),
           "bits": 64 if is64 else 32, "dll": bool(chars & 0x2000), "timestamp": ts,
           "sections": [], "imports": {}, "notes": []}
    sec = []
    f.seek(pe + 24 + optsz)
    sraw = f.read(40 * nsec)
    for i in range(min(nsec, len(sraw) // 40)):
        nm = sraw[i * 40:i * 40 + 8].rstrip(b"\0").decode("latin-1")
        vs, va, rs, rp = struct.unpack_from("<IIII", sraw, i * 40 + 8)
        sec.append((va, max(vs, rs), rp, rs))
        out["sections"].append("%s (%d bytes)" % (nm, rs))

    def rva(r):
        for va, vs, rp, rs in sec:
            if va <= r < va + vs:
                return rp + (r - va)
        return None
    try:
        idir = struct.unpack_from("<II", opt, ddoff + 8)
    except struct.error:
        idir = (0, 0)
    o = rva(idir[0]) if idir[0] else None
    if o is not None:
        n = 0
        while n < 300:
            f.seek(o + 20 * n)
            d = f.read(20)
            if len(d) < 20 or d == b"\0" * 20:
                break
            oft, _t, _fc, nm_rva, ft = struct.unpack("<IIIII", d)
            no = rva(nm_rva)
            if no is None:
                break
            f.seek(no)
            dll = f.read(80).split(b"\0")[0].decode("latin-1")
            thunk = rva(oft or ft)
            funcs = []
            if thunk is not None:
                esz = 8 if is64 else 4
                for k in range(2000):
                    f.seek(thunk + k * esz)
                    t = f.read(esz)
                    if len(t) < esz:
                        break
                    v = int.from_bytes(t, "little")
                    if v == 0:
                        break
                    if v >> (esz * 8 - 1):
                        funcs.append("#%d" % (v & 0xFFFF))
                        continue
                    fo = rva(v)
                    if fo is None:
                        continue
                    f.seek(fo + 2)
                    funcs.append(f.read(100).split(b"\0")[0].decode("latin-1"))
            out["imports"][dll] = funcs
            n += 1
    else:
        out["notes"].append("No import table found (packed or unusual).")
    return out


# ------------------------------------------------------------------ source languages

def parse_python(text):
    tree = ast.parse(text)
    imports, funcs, classes, calls, risks = set(), [], [], {}, {}
    consts = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                imports.add(a.name)
        elif isinstance(n, ast.ImportFrom):
            imports.add((n.module or "") + (" (" + ", ".join(a.name for a in n.names[:4]) + ")"))
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in n.args.args][:8]
            funcs.append({"name": n.name, "line": n.lineno, "end": getattr(n, "end_lineno", n.lineno),
                          "args": args, "doc": (ast.get_docstring(n) or "")[:120]})
        elif isinstance(n, ast.ClassDef):
            classes.append({"name": n.name, "line": n.lineno, "end": getattr(n, "end_lineno", n.lineno),
                            "methods": [m.name for m in n.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))][:30],
                            "doc": (ast.get_docstring(n) or "")[:120]})
        elif isinstance(n, ast.Call):
            nm = _dotted(n.func)
            if nm:
                calls[nm] = calls.get(nm, 0) + 1
                for k, why in PY_RISK.items():
                    if nm == k or nm.startswith(k + "."):
                        risks[k] = why
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(consts) < 20:
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    consts.append(t.id)
    for i in imports:
        base = i.split(" ")[0].split(".")[0]
        if base in ("socket", "requests", "urllib", "subprocess", "ctypes", "pickle", "marshal"):
            risks.setdefault(base, PY_RISK.get(base, "notable import"))
    funcs.sort(key=lambda x: x["line"])
    classes.sort(key=lambda x: x["line"])
    return {"imports": sorted(imports)[:120], "functions": funcs[:600], "classes": classes[:200],
            "top_calls": sorted(calls.items(), key=lambda kv: -kv[1])[:30], "risks": risks,
            "constants": consts, "doc": (ast.get_docstring(tree) or "")[:300]}


def _dotted(n):
    parts = []
    while isinstance(n, ast.Attribute):
        parts.append(n.attr)
        n = n.value
    if isinstance(n, ast.Name):
        parts.append(n.id)
        return ".".join(reversed(parts))
    return ""


def parse_generic_source(text, kind):
    funcs = []
    pats = {
        "shell": r"^\s*(?:function\s+)?([A-Za-z_][\w\-]*)\s*\(\)\s*\{?",
        "javascript": r"(?:function\s+([A-Za-z_$][\w$]*)\s*\(|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\([^)]*\)\s*=>))",
        "c": r"^[A-Za-z_][\w\s\*]*?\b([A-Za-z_]\w*)\s*\([^;{]*\)\s*\{",
        "java": r"^\s*(?:public|private|protected|static|final|\s)+[\w<>\[\],\s]+\s+(\w+)\s*\([^;{]*\)\s*(?:throws [\w, ]+)?\{",
        "kotlin": r"\bfun\s+(?:<[^>]+>\s*)?(?:[\w.]+\.)?(\w+)\s*\(",
        "go": r"^func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(",
        "rust": r"\bfn\s+(\w+)",
        "php": r"\bfunction\s+(\w+)\s*\(",
        "ruby": r"^\s*def\s+([\w.?!]+)",
        "perl": r"^\s*sub\s+(\w+)",
        "lua": r"\bfunction\s+([\w.:]+)\s*\(",
        "powershell": r"^\s*function\s+([\w\-]+)",
    }
    pat = pats.get(kind)
    if pat:
        rx = re.compile(pat, re.M)
        for m in rx.finditer(text):
            name = next((g for g in m.groups() if g), "")
            if name and name not in ("if", "for", "while", "switch", "return", "catch"):
                funcs.append({"name": name, "line": text.count("\n", 0, m.start()) + 1,
                              "args": [], "doc": ""})
            if len(funcs) >= 600:
                break
    imports = set()
    imp = {"shell": r"^\s*(?:source|\.)\s+(\S+)", "javascript": r"(?:require\(['\"]([^'\"]+)|from\s+['\"]([^'\"]+))",
           "c": r"#include\s*[<\"]([^>\"]+)", "java": r"^import\s+([\w.*]+);", "kotlin": r"^import\s+([\w.*]+)",
           "go": r"^\s*\"([\w./\-]+)\"$", "rust": r"^use\s+([\w:]+)", "php": r"(?:require|include)(?:_once)?\s*\(?['\"]([^'\"]+)",
           "ruby": r"require\s+['\"]([^'\"]+)", "perl": r"^use\s+([\w:]+)"}.get(kind)
    if imp:
        for m in re.finditer(imp, text, re.M):
            imports.add(next((g for g in m.groups() if g), ""))
    cmds = {}
    if kind in ("shell", "batch", "powershell"):
        for w in re.findall(r"(?:^|[|;&]\s*|\$\()\s*([a-z][\w\-\.]{1,20})\b", text, re.M):
            cmds[w] = cmds.get(w, 0) + 1
    risky = []
    for pat2, why in ((r"\beval\b", "runs text as code"), (r"\bexec\b", "runs another program or code"),
                      (r"curl[^\n|]*\|\s*(?:ba)?sh", "downloads and runs code"),
                      (r"wget[^\n|]*\|\s*(?:ba)?sh", "downloads and runs code"),
                      (r"rm\s+-rf", "recursive delete"), (r"chmod\s+\+?[0-7x]*", "changes permissions"),
                      (r"base64\s+-d|atob\(|b64decode", "decodes hidden data"),
                      (r"\bsu\b\s+-c|\bsudo\b", "elevated privileges"),
                      (r"/dev/tcp/|\bnc\s+-", "raw network connection"),
                      (r"document\.write|innerHTML", "writes HTML dynamically")):
        if re.search(pat2, text):
            risky.append(why + " (" + pat2.split("\\")[0][:20] + ")")
    return {"functions": funcs, "imports": sorted(imports)[:100],
            "commands": sorted(cmds.items(), key=lambda kv: -kv[1])[:30], "risks": risky}


# ------------------------------------------------------------------ strings

def extract_strings(f, size, out_path, cancel=None, minlen=5):
    rx = re.compile(rb"[\x20-\x7e]{%d,}" % minlen)
    n = 0
    cats = {k: set() for k, _ in STR_CATS}
    secrets = set()
    f.seek(0)
    carry = b""
    off = 0
    with open(out_path, "w", encoding="utf-8") as fo:
        while True:
            if cancel and cancel():
                raise Cancelled()
            chunk = f.read(4 << 20)
            last = not chunk
            buf = carry + chunk
            carry = b""
            ms = list(rx.finditer(buf))
            if ms and ms[-1].end() == len(buf) and not last:
                carry = ms[-1].group(0)[-512:]
                ms = ms[:-1]
            for m in ms:
                if n >= MAX_STR:
                    break
                s = m.group(0).decode("ascii", "replace")[:400]
                fo.write(s + "\n")
                n += 1
                if "/" in s or "." in s or "\\" in s:
                    for k, r in STR_CATS:
                        if len(cats[k]) < 200:
                            for mm in r.finditer(s):
                                cats[k].add(mm.group(0).rstrip(".,;)"))
                if len(s) >= 16 and len(secrets) < 30:
                    for mm in SECRET_RE.finditer(s):
                        secrets.add(mask(mm.group(0)))
            if last or n >= MAX_STR:
                break
            off += len(chunk)
    return n, {k: sorted(v)[:60] for k, v in cats.items()}, sorted(secrets)


# ------------------------------------------------------------------ analyze

def analyze(src_path, root, orig_name="", progress=None, cancel=None, max_bytes=MAX_FILE):
    def say(m):
        if progress:
            progress(m)

    def chk():
        if cancel and cancel():
            raise Cancelled()
    t0 = time.time()
    say("1/5 Checking and hashing")
    if not os.path.isfile(src_path):
        raise ProgError("File not found.")
    size = os.path.getsize(src_path)
    if size == 0:
        raise ProgError("The file is empty.")
    if size > max_bytes:
        raise ProgError("The file is larger than the %d MB limit." % (max_bytes >> 20))
    h = hashlib.sha256()
    with open(src_path, "rb") as f:
        while True:
            chk()
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    sha = h.hexdigest()
    ws = os.path.join(root, "p_" + sha[:16])
    cache = os.path.join(ws, "info.json")
    if os.path.exists(cache):
        try:
            old = json.load(open(cache, encoding="utf-8"))
            if old.get("schema") == SCHEMA and old.get("sha256") == sha:
                old["cached"] = True
                os.remove(src_path)
                return old
        except (ValueError, OSError):
            pass
    os.makedirs(ws, exist_ok=True)
    target = os.path.join(ws, "target.bin")
    try:
        os.replace(src_path, target)
        with open(target, "rb") as f:
            head = f.read(8192)
        kind = detect(orig_name or target, head)
        info = {"schema": SCHEMA, "sha256": sha, "size": size, "file_name": orig_name or "file",
                "kind": kind, "limits": [], "cached": False, "ws": ws, "notes": []}
        with open(target, "rb") as f:
            say("2/5 Measuring entropy")
            sample = f.read(4 << 20)
            info["entropy"] = round(entropy(sample), 2)
            if info["entropy"] > 7.4 and kind not in ("zip", "gzip", "png", "jpeg", "xz", "7z", "bzip2", "rar"):
                info["notes"].append("Very high entropy (%.2f of 8): the data may be packed, "
                                     "encrypted or compressed, which hides its real content." % info["entropy"])
            say("3/5 Reading the structure (%s)" % kind)
            try:
                if kind == "elf":
                    info["elf"] = parse_elf(f, size)
                elif kind == "pe":
                    info["pe"] = parse_pe(f, size)
            except (ProgError, struct.error, IndexError, OverflowError, MemoryError) as e:
                info["limits"].append("Header parse failed: %s. Falling back to strings." % str(e)[:80])
            if kind in ("zip",):
                try:
                    with zipfile.ZipFile(target) as zf:
                        ents = zf.infolist()
                        info["entries"] = [[z.filename, z.file_size] for z in ents[:5000]]
                        info["n_entries"] = len(ents)
                        nm = [z.filename for z in ents]
                        if "AndroidManifest.xml" in nm:
                            info["notes"].append("This is an Android APK. Use: apk pick for the full APK analysis.")
                        elif "META-INF/MANIFEST.MF" in nm:
                            info["notes"].append("Looks like a Java JAR.")
                        elif "[Content_Types].xml" in nm:
                            info["notes"].append("Looks like an Office document package.")
                except zipfile.BadZipFile:
                    info["limits"].append("ZIP structure damaged.")
            text = None
            if kind in ("python", "shell", "javascript", "json", "html", "xml", "c", "java", "kotlin",
                        "php", "ruby", "perl", "lua", "go", "rust", "powershell", "batch", "text"):
                if size <= MAX_SRC:
                    with open(target, "rb") as g:
                        text = g.read().decode("utf-8", "replace")
                    info["lines"] = text.count("\n") + 1
                else:
                    info["limits"].append("Text file is over %d MB; only strings were scanned." % (MAX_SRC >> 20))
            if text is not None:
                if kind == "python":
                    try:
                        info["py"] = parse_python(text)
                    except (SyntaxError, ValueError, RecursionError) as e:
                        info["limits"].append("Python could not be parsed (%s). Showing regex results." % str(e)[:60])
                        info["src"] = parse_generic_source(text, "python")
                elif kind not in ("json", "html", "xml", "text"):
                    info["src"] = parse_generic_source(text, kind)
                else:
                    info["src"] = parse_generic_source(text, "javascript" if kind == "html" else kind)
            chk()
            say("4/5 Extracting strings")
            n, cats, secrets = extract_strings(f, size, os.path.join(ws, "strings.txt"), cancel)
        info["n_strings"] = n
        info["str_cats"] = cats
        info["secrets"] = secrets
        say("5/5 Writing results")
        if kind in ("elf", "pe") and "elf" not in info and "pe" not in info:
            info["limits"].append("Structure could not be read; use strings only.")
        info["limits"].append("Machine code is not disassembled. Function names, imports and strings are real; "
                              "what the code does is inferred from them. Ghidra, radare2 or objdump on a "
                              "computer show instructions.")
        info["limits"].append("The file was never run. Behavior that only appears at runtime is not visible.")
        info["seconds"] = round(time.time() - t0, 1)
        tmp = cache + ".part"
        with open(tmp, "w", encoding="utf-8") as fo:
            json.dump(info, fo)
        os.replace(tmp, cache)
        return info
    except BaseException:
        shutil.rmtree(ws, ignore_errors=True)
        raise


# ------------------------------------------------------------------ tools

def load_info(ws):
    p = os.path.join(ws, "info.json")
    if not os.path.isfile(p):
        raise ToolError("No analyzed file. Use: prog pick")
    return json.load(open(p, encoding="utf-8"))


def _clip(s, n=MAX_OUT):
    return s if len(s) <= n else s[:n - 40] + "\n... (cut, ask for a narrower search)"


def grep(path, q, limit=40, maxlen=220):
    out = []
    ql = q.lower()
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if ql in line.lower():
                out.append(line.rstrip("\n")[:maxlen])
                if len(out) >= limit:
                    break
    return out


def _all_funcs(i):
    if "py" in i:
        return i["py"]["functions"], i["py"]["classes"]
    if "src" in i:
        return i["src"]["functions"], []
    return [], []


def _imports(i):
    """Returns list of (library, [names])."""
    out = []
    if "elf" in i:
        und = [s[0].split("@")[0] for s in i["elf"]["symbols"] if s[1] == "undef"]
        for lib in i["elf"]["needed"]:
            out.append((lib, []))
        out.append(("(imported symbols)", sorted(set(und))))
    if "pe" in i:
        out += [(d, fs) for d, fs in i["pe"]["imports"].items()]
    if "py" in i:
        out.append(("(python imports)", i["py"]["imports"]))
    elif "src" in i and i["src"].get("imports"):
        out.append(("(source imports)", i["src"]["imports"]))
    return out


def meaning(name):
    base = name.split("@")[0].lstrip("_")
    return API.get(base) or API.get(base.rstrip("AW")) or ""


def t_summary(ws, a):
    i = load_info(ws)
    out = ["%s  (%s)" % (i["file_name"], i["kind"]),
           "%d KB, entropy %.2f, %d strings" % (i["size"] // 1024, i.get("entropy", 0), i.get("n_strings", 0))]
    if "elf" in i:
        e = i["elf"]
        out.append("ELF %d-bit %s, %s, %s" % (e["bits"], e["machine"], e["type"], "stripped" if e["stripped"] else "has symbols"))
        out.append("Needs libraries: " + (", ".join(e["needed"][:12]) or "none (static?)"))
        d = [s for s in e["symbols"] if s[1] == "defined" and s[2] == "func"]
        u = [s for s in e["symbols"] if s[1] == "undef"]
        out.append("%d defined functions, %d imported symbols" % (len(d), len(u)))
    if "pe" in i:
        p = i["pe"]
        out.append("Windows PE %d-bit %s%s" % (p["bits"], p["machine"], " DLL" if p["dll"] else ""))
        out.append("Imports from: " + (", ".join(list(p["imports"])[:10]) or "none"))
    if "py" in i:
        p = i["py"]
        out.append("Python: %d functions, %d classes, %d lines" % (len(p["functions"]), len(p["classes"]), i.get("lines", 0)))
        out.append("Imports: " + ", ".join(p["imports"][:15]))
        if p["doc"]:
            out.append("Docstring: " + p["doc"][:200])
        if p["risks"]:
            out.append("Notable: " + "; ".join("%s (%s)" % kv for kv in list(p["risks"].items())[:8]))
    elif "src" in i:
        s = i["src"]
        out.append("%d lines, %d functions" % (i.get("lines", 0), len(s["functions"])))
        if s.get("imports"):
            out.append("Imports/includes: " + ", ".join(s["imports"][:12]))
        if s.get("commands"):
            out.append("Commands used: " + ", ".join(k for k, _ in s["commands"][:15]))
        if s.get("risks"):
            out.append("Notable: " + "; ".join(s["risks"][:6]))
    if i.get("n_entries"):
        out.append("Archive with %d entries" % i["n_entries"])
    for n in i.get("notes", []):
        out.append("Note: " + n)
    c = i.get("str_cats", {})
    if c.get("urls"):
        out.append("URLs: " + ", ".join(c["urls"][:5]))
    return _clip("\n".join(out))


def t_symbols(ws, a):
    i = load_info(ws)
    q = a.get("query", "").lower()
    out = []
    if "elf" in i:
        rows = [s for s in i["elf"]["symbols"] if s[1] == "defined" and s[2] in ("func", "object") and q in s[0].lower()]
        out.append("%d defined symbols match:" % len(rows))
        out += ["  %s  %s  @0x%x size %d" % (s[0], s[2], s[3], s[4]) for s in rows[:a.get("limit", 60)]]
        if i["elf"]["stripped"] and not rows:
            out.append("The binary is stripped: no function names are stored.")
    fs, cs = _all_funcs(i)
    if fs or cs:
        for c in cs:
            if q in c["name"].lower():
                out.append("class %s  line %d  methods: %s" % (c["name"], c["line"], ", ".join(c["methods"][:10])))
        for f in fs:
            if q in f["name"].lower():
                out.append("def %s(%s)  line %d%s" % (f["name"], ", ".join(f["args"]), f["line"],
                                                      "  - " + f["doc"][:80] if f["doc"] else ""))
    return _clip("\n".join(out[:a.get("limit", 60) + 5])) if out else "No symbols or functions match '%s'." % q


def t_imports(ws, a):
    i = load_info(ws)
    q = a.get("query", "").lower()
    out = []
    for lib, names in _imports(i):
        rows = [n for n in names if q in n.lower() or q in lib.lower()]
        if not rows and names:
            continue
        out.append(lib)
        for n in rows[:40]:
            m = meaning(n)
            out.append("  " + n + ("  -> " + m if m else ""))
        if len(rows) > 40:
            out.append("  ... %d more" % (len(rows) - 40))
    return _clip("\n".join(out)) if out else "No imports match."


def t_strings(ws, a):
    q = a["query"]
    rows = grep(os.path.join(ws, "strings.txt"), q, a.get("limit", 40))
    return _clip("%d string(s) with '%s':\n" % (len(rows), q) + "\n".join("  " + r for r in rows)) if rows else "No strings contain '%s'." % q


def t_entries(ws, a):
    i = load_info(ws)
    q = a.get("query", "").lower()
    rows = [e for e in i.get("entries", []) if q in e[0].lower()]
    return _clip("\n".join("  %d bytes  %s" % (e[1], e[0]) for e in rows[:60])) if rows else "No archive entries match."


def _src_lines(ws):
    p = os.path.join(ws, "target.bin")
    if os.path.getsize(p) > MAX_SRC:
        raise ToolError("File too large to show as source.")
    return open(p, encoding="utf-8", errors="replace").read().split("\n")


def t_source(ws, a):
    i = load_info(ws)
    if "lines" not in i:
        raise ToolError("This is not a text file, so there is no source to show. Try: prog strings TEXT")
    L = _src_lines(ws)
    s = max(1, a.get("start", 1))
    e = min(len(L), a.get("end", s + 59), s + 119)
    return _clip("\n".join("%d: %s" % (n + 1, L[n][:200]) for n in range(s - 1, e)), 5000)


def t_function(ws, a):
    i = load_info(ws)
    name = a["name"]
    fs, cs = _all_funcs(i)
    for it in fs + cs:
        if it["name"] == name or it["name"].endswith("." + name):
            L = _src_lines(ws)
            s, e = it["line"], min(it.get("end", it["line"] + 40), it["line"] + 119)
            return _clip("%s (lines %d-%d)\n" % (name, s, e) + "\n".join(
                "%d: %s" % (n + 1, L[n][:200]) for n in range(s - 1, min(e, len(L)))), 5000)
    if "elf" in i:
        rows = [s for s in i["elf"]["symbols"] if s[0] == name or s[0].split("@")[0] == name]
        if rows:
            return "\n".join("%s %s %s @0x%x size %d  %s" % (s[0], s[1], s[2], s[3], s[4], meaning(s[0])) for s in rows[:5]) + \
                "\n(Machine code is not disassembled here. Use objdump/Ghidra for instructions.)"
    return "No function named '%s'. Try: prog symbols %s" % (name, name[:20])


def t_search(ws, a):
    q = a["query"]
    out = []
    i = load_info(ws)
    fs, cs = _all_funcs(i)
    hit = [f["name"] + " (line %d)" % f["line"] for f in fs + cs if q.lower() in f["name"].lower()][:12]
    if hit:
        out.append("FUNCTIONS/CLASSES:\n" + "\n".join("  " + h for h in hit))
    if "elf" in i:
        sy = [s[0] for s in i["elf"]["symbols"] if q.lower() in s[0].lower()][:12]
        if sy:
            out.append("SYMBOLS:\n" + "\n".join("  " + s for s in sy))
    if "pe" in i:
        im = [d + ": " + f for d, fl in i["pe"]["imports"].items() for f in fl if q.lower() in f.lower()][:12]
        if im:
            out.append("IMPORTS:\n" + "\n".join("  " + s for s in im))
    st = grep(os.path.join(ws, "strings.txt"), q, 12)
    if st:
        out.append("STRINGS:\n" + "\n".join("  " + s for s in st))
    return _clip("\n".join(out)) if out else "Nothing matches '%s'." % q


def t_lessons(ws, a):
    rows = search_lessons(os.path.dirname(ws), a.get("query", ""), 6)
    return "\n".join("  [%d] %s" % (r["id"], r["text"]) for r in rows) or "No lessons yet."


_TOOL_FN = {"summarize_program": t_summary, "list_symbols": t_symbols, "list_imports": t_imports,
            "search_strings": t_strings, "list_entries": t_entries, "read_source": t_source,
            "show_function": t_function, "search_code": t_search, "recall_lessons": t_lessons}
TOOLS = {"summarize_program": {}, "list_symbols": {"query": ("str", 80, False), "limit": ("int", 1, 100)},
         "list_imports": {"query": ("str", 80, False)}, "search_strings": {"query": ("str", 80, True), "limit": ("int", 1, 100)},
         "list_entries": {"query": ("str", 80, False)},
         "read_source": {"start": ("int", 1, 10000000), "end": ("int", 1, 10000000)},
         "show_function": {"name": ("str", 200, True)}, "search_code": {"query": ("str", 80, True)},
         "recall_lessons": {"query": ("str", 100, False)}}


def validate_call(name, args):
    if not isinstance(name, str) or name not in TOOLS:
        raise ToolError("Unknown tool. Allowed: " + ", ".join(sorted(TOOLS)))
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ToolError("Arguments must be a JSON object.")
    spec, clean = TOOLS[name], {}
    for k, v in args.items():
        if k not in spec:
            raise ToolError("Unexpected argument '%s' for %s." % (str(k)[:30], name))
        s = spec[k]
        if s[0] == "str":
            if not isinstance(v, str) or len(v.strip()) > s[1] or any(ord(c) < 32 for c in v):
                raise ToolError("'%s' must be short plain text." % k)
            clean[k] = v.strip()
        else:
            if isinstance(v, bool) or not isinstance(v, int):
                raise ToolError("'%s' must be a whole number." % k)
            clean[k] = max(s[1], min(s[2], v))
    for k, s in spec.items():
        if s[0] == "str" and s[2] and not clean.get(k):
            raise ToolError("'%s' is required for %s." % (k, name))
    return clean


def run_tool(ws, name, args):
    args = validate_call(name, args)
    if not ws or not os.path.isdir(ws):
        raise ToolError("No analyzed file. Use: prog pick")
    return _TOOL_FN[name](ws, args)


# ------------------------------------------------------------------ report

def build_report(i):
    ws = i["ws"]
    out = ["PROGRAM ANALYSIS REPORT", "=" * 23, "File: %s (%d KB)" % (i["file_name"], i["size"] // 1024),
           "SHA-256: " + i["sha256"], "", "1. OVERVIEW", "-" * 11, t_summary(ws, {}), "",
           "2. IMPORTS (what it asks the system to do)", "-" * 40, t_imports(ws, {}), "",
           "3. FUNCTIONS", "-" * 12, t_symbols(ws, {"limit": 80}), "", "4. STRINGS OF INTEREST", "-" * 22]
    for k, v in i.get("str_cats", {}).items():
        if v:
            out.append("%s (%d):" % (k, len(v)))
            out += ["  " + x for x in v[:12]]
    if i.get("secrets"):
        out.append("SECRET-LOOKING VALUES (hidden): " + ", ".join(i["secrets"][:5]))
    out += ["", "5. OBSERVATIONS", "-" * 15]
    obs = []
    for n in i.get("notes", []):
        obs.append("CONFIRMED: " + n)
    if "py" in i:
        for k, why in i["py"]["risks"].items():
            obs.append("CONFIRMED: uses %s (%s)." % (k, why))
    if "src" in i:
        for r in i["src"].get("risks", []):
            obs.append("CONFIRMED: pattern found: " + r)
    if "elf" in i:
        names = {s[0].split("@")[0] for s in i["elf"]["symbols"] if s[1] == "undef"}
        for n in sorted(names):
            if n in ("ptrace", "mprotect", "dlopen", "execve", "system", "popen", "strcpy", "gets", "sprintf"):
                obs.append("CONFIRMED: imports %s (%s)." % (n, meaning(n)))
        if names & {"socket", "connect"}:
            obs.append("HYPOTHESIS: makes network connections (socket/connect imported).")
    if "pe" in i:
        for d, fl in i["pe"]["imports"].items():
            for f in fl:
                if f in ("WriteProcessMemory", "CreateRemoteThread", "VirtualProtect", "URLDownloadToFileA", "IsDebuggerPresent"):
                    obs.append("CONFIRMED: imports %s (%s)." % (f, meaning(f)))
    out += obs or ["Nothing unusual in the data this tool can read. That does not prove the file is safe."]
    out += ["", "6. LIMITATIONS", "-" * 14] + ["- " + l for l in i.get("limits", [])]
    out += ["", "Everything above comes from reading the file only. Nothing was run."]
    return "\n".join(out)


# ------------------------------------------------------------------ lessons memory
# lessons.json lives in the workspace root. kinds: fact (user taught), example (answer marked good),
# pattern (auto-recorded from an analysis). Retrieval is by keyword overlap.

def _lpath(root):
    return os.path.join(root, "lessons.json")


def _lload(root):
    try:
        return json.load(open(_lpath(root), encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _lsave(root, rows):
    tmp = _lpath(root) + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows[-600:], f)
    os.replace(tmp, _lpath(root))


def _words(t):
    return {w for w in re.findall(r"[a-z0-9_]{3,}", t.lower())}


def add_lesson(root, text, kind="fact", topic=""):
    text = scrub(text.strip())[:700]
    if len(text) < 8:
        raise ToolError("Lesson is too short.")
    rows = _lload(root)
    for r in rows:
        if r["text"] == text:
            return r["id"]
    nid = max([r["id"] for r in rows] + [0]) + 1
    rows.append({"id": nid, "kind": kind, "topic": topic[:60], "text": text, "ts": int(time.time()), "uses": 0})
    _lsave(root, rows)
    return nid


def forget_lesson(root, lid):
    rows = _lload(root)
    keep = [r for r in rows if r["id"] != lid]
    _lsave(root, keep)
    return len(rows) - len(keep)


def search_lessons(root, query, k=5):
    q = _words(query)
    rows = _lload(root)
    scored = []
    for r in rows:
        if r.get("kind") == "pending":
            continue
        w = _words(r["text"] + " " + r.get("topic", ""))
        sc = len(q & w) * 2 + (3 if r["kind"] == "fact" else 1 if r["kind"] == "example" else 0) * (1 if q & w else 0)
        if q & w or not q:
            scored.append((sc, r["id"], r))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [r for _s, _i, r in scored[:k]]


def list_lessons(root):
    return _lload(root)


def record_pattern(root, info):
    """After an analysis, remember a compact fingerprint so similar files are recognized."""
    bits = [info["kind"]]
    if "elf" in info:
        bits.append("ELF " + info["elf"]["machine"])
        bits += info["elf"]["needed"][:6]
    if "pe" in info:
        bits += list(info["pe"]["imports"])[:6]
    if "py" in info:
        bits += [x.split(" ")[0] for x in info["py"]["imports"][:8]]
    txt = "Seen %s: %s (%d KB)." % (info["file_name"][:40], ", ".join(bits), info["size"] // 1024)
    add_lesson(root, txt, "pattern", info["kind"])


def delete_all(root, ws=None):
    root = os.path.realpath(root)
    if ws is None:
        for n in os.listdir(root):
            if n.startswith("p_"):
                shutil.rmtree(os.path.join(root, n), ignore_errors=True)
        return
    real = os.path.realpath(ws)
    if os.path.dirname(real) != root or not os.path.basename(real).startswith("p_"):
        raise ToolError("Refusing to delete outside the analysis workspace.")
    shutil.rmtree(real, ignore_errors=True)


# ================================================================== v46 additions
# Capability map, call graph, and an approval queue for learning.

CAPS = {
    "network": ["socket", "connect", "send", "recv", "bind", "listen", "accept", "getaddrinfo", "gethostbyname",
                "curl_easy", "ssl_", "wsastartup", "internetopen", "httpsendrequest", "winhttp", "wininet",
                "urldownloadtofile", "ws2_32", "requests", "urllib", "http.client", "aiohttp", "websocket",
                "ftplib", "smtplib", "paramiko", "xmlhttprequest", "fetch", "okhttp", "httpurlconnection"],
    "starts other programs": ["execve", "execl", "execv", "execvp", "system", "popen", "fork", "posix_spawn",
                              "createprocess", "shellexecute", "winexec", "subprocess", "os.system", "os.popen",
                              "child_process", "runtime.exec", "processbuilder"],
    "files": ["fopen", "open", "read", "write", "unlink", "rename", "remove", "createfile", "readfile",
              "writefile", "deletefile", "shutil", "pathlib", "os.remove", "os.rename"],
    "memory tricks": ["mprotect", "virtualprotect", "virtualalloc", "writeprocessmemory", "createremotethread",
                      "mmap", "ctypes", "ntallocatevirtualmemory"],
    "loads code at runtime": ["dlopen", "dlsym", "loadlibrary", "getprocaddress", "importlib", "__import__",
                              "dexclassloader", "classloader"],
    "anti-debugging": ["ptrace", "isdebuggerpresent", "checkremotedebuggerpresent", "ntqueryinformationprocess"],
    "cryptography": ["evp_", "crypto_", "aes", "bcrypt", "cryptencrypt", "crypt32", "hashlib", "cryptography",
                     "openssl", "rsa", "hmac", "cipher"],
    "registry or services": ["regopenkey", "regsetvalue", "regcreatekey", "createservice", "startservice", "advapi32"],
    "input capture": ["setwindowshookex", "getasynckeystate", "xgrabkey", "pynput", "accessibilityservice"],
    "runs generated code": ["eval", "exec", "compile", "pickle", "marshal", "fromcharcode", "unescape"],
    "unsafe copy functions": ["strcpy", "strcat", "sprintf", "gets", "scanf", "vsprintf"],
    "database": ["sqlite3", "mysql", "psycopg", "sqlalchemy"],
    "startup or scheduling": ["crontab", "systemd", "autorun", "launchagent", "bashrc", "schtasks", "alarmmanager"],
    "device or personal data": ["getdeviceid", "read_sms", "read_contacts", "locationmanager", "getlastknownlocation",
                                "telephonymanager", "camera", "mediarecorder", "audiorecord"],
}


def _ev_names(i):
    """Every import-like name the file declares, lower case."""
    names = set()
    if "elf" in i:
        for s in i["elf"]["symbols"]:
            if s[1] == "undef":
                names.add(s[0].split("@")[0].lstrip("_").lower())
        names.update(x.lower() for x in i["elf"]["needed"])
    if "pe" in i:
        for d, fl in i["pe"]["imports"].items():
            names.add(d.lower())
            names.update(f.lower() for f in fl)
    if "py" in i:
        for x in i["py"]["imports"]:
            names.add(str(x).split(" ")[0].lower())
        names.update(k.lower() for k in i["py"]["risks"])
    if "src" in i:
        names.update(str(x).lower() for x in i["src"].get("imports", []))
        names.update(str(k).lower() for k, _v in i["src"].get("commands", []))
        for r in i["src"].get("risks", []):
            names.add(str(r).lower())
    return names


def capabilities(i):
    """Returns {capability: [evidence names]}. Capability is not intent."""
    names = _ev_names(i)
    out = {}
    for cap, keys in CAPS.items():
        hit = []
        for n in names:
            for k in keys:
                if n == k or (len(k) >= 6 and n.startswith(k)) or (("." in k or k.endswith("_")) and k in n) \
                        or (len(k) >= 6 and k in n and len(n) <= len(k) + 12):
                    hit.append(n)
                    break
        if hit:
            out[cap] = sorted(set(hit))[:8]
    c = i.get("str_cats", {})
    if c.get("urls") and "network" not in out:
        out["network"] = ["URL strings present"]
    return out


def t_capabilities(ws, a):
    i = load_info(ws)
    caps = capabilities(i)
    if not caps:
        return "No known capability markers in the imports or names. This does not prove the file is harmless."
    lines = ["Capabilities seen in the file's own imports and names (what it CAN do, not why):"]
    for cap, ev in caps.items():
        lines.append("- %s: %s" % (cap, ", ".join(ev)))
    strong = set(caps) & {"memory tricks", "anti-debugging", "loads code at runtime", "input capture"}
    if len(strong) >= 3:
        lines.append("Several higher-risk markers appear together (%s). That is worth a closer look on a computer, "
                     "but it is still not proof of bad intent." % ", ".join(sorted(strong)))
    return _clip("\n".join(lines))


def t_callgraph(ws, a):
    i = load_info(ws)
    if "py" not in i:
        return "Call graph is only built for Python files. For other types use: search_code or show_function."
    path = os.path.join(ws, "target.bin")
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except (SyntaxError, ValueError, RecursionError):
        return "Could not parse the Python file for a call graph."
    defs = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            calls = []
            for c in ast.walk(n):
                if isinstance(c, ast.Call):
                    f = c.func
                    nm = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
                    if nm and nm not in calls:
                        calls.append(nm)
            defs[n.name] = calls
    q = a.get("query", "").lower()
    own = set(defs)
    lines = []
    for name in sorted(defs):
        if q and q not in name.lower() and not any(q in c.lower() for c in defs[name]):
            continue
        mine = [c for c in defs[name] if c in own and c != name]
        other = [c for c in defs[name] if c not in own][:6]
        lines.append("%s -> %s%s" % (name, ", ".join(mine[:8]) or "(no own functions)",
                                     ("  | also: " + ", ".join(other)) if other else ""))
        if len(lines) >= 45:
            break
    called = {c for v in defs.values() for c in v}
    roots = sorted(n for n in own if n not in called)[:12]
    head = "Functions never called inside this file (likely entry points or callbacks): " + (", ".join(roots) or "none")
    return _clip(head + "\n" + "\n".join(lines)) if lines else "No matching functions."


def t_explain(ws, a):
    n = a.get("name", "")
    m = meaning(n)
    return "%s: %s" % (n, m) if m else "No built-in note for %s. Look it up in the library documentation." % n


_old_summary = t_summary


def t_summary(ws, a):  # noqa: F811
    base = _old_summary(ws, a)
    try:
        caps = capabilities(load_info(ws))
    except Exception:
        caps = {}
    if caps:
        base += "\nCapabilities: " + "; ".join("%s (%s)" % (k, ", ".join(v[:3])) for k, v in list(caps.items())[:8])
    return _clip(base, MAX_OUT + 600)


_old_report = build_report


def build_report(i):  # noqa: F811
    body = _old_report(i)
    try:
        cap = t_capabilities(i["ws"], {})
        mark = "5. OBSERVATIONS"
        if mark in body:
            body = body.replace(mark, "4b. CAPABILITIES\n" + "-" * 16 + "\n" + cap + "\n\n" + mark, 1)
    except Exception:
        pass
    return body


_TOOL_FN.update({"summarize_program": t_summary, "list_capabilities": t_capabilities,
                 "call_graph": t_callgraph, "explain_api": t_explain})
TOOLS.update({"list_capabilities": {}, "call_graph": {"query": ("str", 80, False)},
              "explain_api": {"name": ("str", 80, True)}})


# ----- approval queue: nothing becomes a lesson until the user approves it -----

MAX_PENDING = 30


def add_pending(root, question, answer):
    text = scrub("Q: %s A: %s" % (question.strip()[:150], answer.strip()[:450]))
    rows = _lload(root)
    pend = [r for r in rows if r.get("kind") == "pending"]
    if any(r["text"] == text for r in pend):
        return None
    nid = max([r["id"] for r in rows] + [0]) + 1
    rows.append({"id": nid, "kind": "pending", "topic": "", "text": text, "ts": int(time.time()), "uses": 0})
    pend = [r for r in rows if r.get("kind") == "pending"]
    if len(pend) > MAX_PENDING:
        drop = {r["id"] for r in pend[:len(pend) - MAX_PENDING]}
        rows = [r for r in rows if r["id"] not in drop]
    _lsave(root, rows)
    return nid


def list_pending(root):
    return [r for r in _lload(root) if r.get("kind") == "pending"]


def approve_pending(root, which):
    """which is an id or 'all'. Returns how many became examples."""
    rows = _lload(root)
    n = 0
    for r in rows:
        if r.get("kind") == "pending" and (which == "all" or r["id"] == which):
            r["kind"] = "example"
            n += 1
    if n:
        _lsave(root, rows)
    return n


def reject_pending(root, which):
    rows = _lload(root)
    keep = [r for r in rows if not (r.get("kind") == "pending" and (which == "all" or r["id"] == which))]
    _lsave(root, keep)
    return len(rows) - len(keep)
