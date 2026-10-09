"""apkscan: static APK analysis for RAMBO AI.

Pure Python, standard library only. It NEVER runs or installs the APK: it only reads
the ZIP, the binary AndroidManifest.xml and the DEX tables. It does not decompile
bytecode (that needs JADX/Apktool, which need Java).
"""
import hashlib
import json
import os
import re
import shutil
import struct
import time
import zipfile

SCHEMA = 1
MAX_APK = 600 * 1024 * 1024
MAX_DEX = 96 * 1024 * 1024
MAX_MANIFEST = 8 * 1024 * 1024
MAX_STRINGS = 1500000
MAX_METHODS = 500000
MAX_ENTRIES = 200000
MAX_OUT = 3500


class ApkError(Exception):
    pass


class Cancelled(Exception):
    pass


class ToolError(Exception):
    pass


# ---------------------------------------------------------------- file helpers

def sha256_file(path, cancel=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            if cancel and cancel():
                raise Cancelled()
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def copy_stream(src, dst_path, limit=MAX_APK, cancel=None, progress=None):
    """Copy a file-like object to dst_path in 1 MB pieces. Returns (bytes, sha256)."""
    h = hashlib.sha256()
    n = 0
    tmp = dst_path + ".part"
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
                    raise ApkError("The file is larger than the %d MB limit." % (limit >> 20))
                h.update(b)
                out.write(b)
                if progress:
                    progress(n)
        os.replace(tmp, dst_path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return n, h.hexdigest()


# ---------------------------------------------------------------- binary XML

class Node(object):
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag):
        self.tag = tag
        self.attrs = {}
        self.children = []

    def kids(self, tag):
        return [c for c in self.children if c.tag == tag]


# resource ids used only when the attribute name string is missing (obfuscated manifests)
_RES_NAMES = {0x01010003: "name", 0x0101021b: "versionCode", 0x0101021c: "versionName",
              0x0101020c: "minSdkVersion", 0x01010270: "targetSdkVersion",
              0x01010010: "exported", 0x0101000f: "debuggable", 0x0101000e: "enabled",
              0x01010006: "permission", 0x01010018: "authorities"}


def _len8(d, o):
    n = d[o]
    o += 1
    if n & 0x80:
        n = ((n & 0x7F) << 8) | d[o]
        o += 1
    return n, o


def _len16(d, o):
    n = struct.unpack_from("<H", d, o)[0]
    o += 2
    if n & 0x8000:
        n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", d, o)[0]
        o += 2
    return n, o


def _string_pool(d, o):
    chsize = struct.unpack_from("<H", d, o + 2)[0]
    count, _style, flags, sstart, _ystart = struct.unpack_from("<IIIII", d, o + 8)
    if count > 500000:
        raise ApkError("AndroidManifest.xml string table is too large.")
    utf8 = bool(flags & 0x100)
    offs = struct.unpack_from("<%dI" % count, d, o + chsize) if count else ()
    out = []
    base = o + sstart
    for off in offs:
        p = base + off
        try:
            if utf8:
                _c, p = _len8(d, p)
                bl, p = _len8(d, p)
                out.append(d[p:p + bl].decode("utf-8", "replace"))
            else:
                n, p = _len16(d, p)
                out.append(d[p:p + 2 * n].decode("utf-16le", "replace"))
        except (IndexError, struct.error):
            out.append("")
    return out


def _s(strings, i):
    return strings[i] if 0 <= i < len(strings) else ""


def _val(strings, raw, dtype, data):
    if raw != 0xFFFFFFFF:
        return _s(strings, raw)
    if dtype == 0x03:
        return _s(strings, data)
    if dtype == 0x12:
        return data != 0
    if dtype == 0x10:
        return struct.unpack("<i", struct.pack("<I", data))[0]
    if dtype == 0x11:
        return "0x%x" % data
    if dtype == 0x01:
        return "@0x%08x" % data
    if dtype == 0x02:
        return "?0x%08x" % data
    if dtype == 0x04:
        return struct.unpack("<f", struct.pack("<I", data))[0]
    return "0x%x" % data


def parse_axml(data):
    """Parse Android binary XML into a Node tree."""
    if len(data) < 8:
        raise ApkError("AndroidManifest.xml is empty or truncated.")
    typ, hsize, size = struct.unpack_from("<HHI", data, 0)
    if typ != 0x0003:
        raise ApkError("AndroidManifest.xml is not binary XML (unexpected format).")
    strings, resmap, root, stack = [], [], None, []
    o = hsize
    end = min(size, len(data))
    try:
        while o + 8 <= end:
            ctype, chsize, csize = struct.unpack_from("<HHI", data, o)
            if csize < 8 or o + csize > len(data):
                raise ApkError("AndroidManifest.xml is truncated or corrupted.")
            if ctype == 0x0001:
                strings = _string_pool(data, o)
            elif ctype == 0x0180:
                n = (csize - chsize) // 4
                resmap = list(struct.unpack_from("<%dI" % n, data, o + chsize)) if n else []
            elif ctype == 0x0102:
                _ns, name, astart, asize, acount = struct.unpack_from("<IIHHH", data, o + 16)
                node = Node(_s(strings, name))
                base = o + 16 + astart
                for k in range(acount):
                    a = base + k * asize
                    _ans, aname, raw, _ts, _r0, dtype, ddata = struct.unpack_from("<IIIHBBI", data, a)
                    nm = _s(strings, aname)
                    if not nm and aname < len(resmap):
                        nm = _RES_NAMES.get(resmap[aname], "")
                    if nm:
                        node.attrs[nm] = _val(strings, raw, dtype, ddata)
                if stack:
                    stack[-1].children.append(node)
                elif root is None:
                    root = node
                stack.append(node)
            elif ctype == 0x0103:
                if stack:
                    stack.pop()
            o += csize
    except (struct.error, IndexError):
        raise ApkError("AndroidManifest.xml is corrupted.")
    if root is None:
        raise ApkError("AndroidManifest.xml has no root element.")
    return root


DANGEROUS = {
    "READ_SMS", "SEND_SMS", "RECEIVE_SMS", "RECEIVE_MMS", "READ_CONTACTS", "WRITE_CONTACTS",
    "GET_ACCOUNTS", "READ_CALL_LOG", "WRITE_CALL_LOG", "CALL_PHONE", "RECORD_AUDIO", "CAMERA",
    "ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION", "ACCESS_BACKGROUND_LOCATION",
    "READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE", "MANAGE_EXTERNAL_STORAGE",
    "READ_PHONE_STATE", "READ_PHONE_NUMBERS", "SYSTEM_ALERT_WINDOW", "BIND_ACCESSIBILITY_SERVICE",
    "REQUEST_INSTALL_PACKAGES", "READ_MEDIA_IMAGES", "READ_MEDIA_VIDEO", "READ_MEDIA_AUDIO",
    "BODY_SENSORS", "READ_CALENDAR", "WRITE_CALENDAR", "QUERY_ALL_PACKAGES",
    "BIND_DEVICE_ADMIN", "WRITE_SETTINGS", "RECEIVE_BOOT_COMPLETED", "USE_FULL_SCREEN_INTENT",
    "BIND_NOTIFICATION_LISTENER_SERVICE", "READ_LOGS", "SCHEDULE_EXACT_ALARM"}

KINDS = ("activity", "activity-alias", "service", "receiver", "provider")
KIND_ALIASES = {"activity": "activity", "activities": "activity", "alias": "activity-alias",
                "activity-alias": "activity-alias", "service": "service", "services": "service",
                "receiver": "receiver", "receivers": "receiver", "provider": "provider",
                "providers": "provider", "all": "all"}


def _fq(pkg, n):
    if not n or not isinstance(n, str):
        return ""
    if n.startswith("."):
        return pkg + n
    if "." not in n:
        return pkg + "." + n
    return n


def _flag(v):
    return v if isinstance(v, bool) else None


def manifest_info(root):
    a = root.attrs
    pkg = str(a.get("package", "") or "")
    info = {"package": pkg, "version_name": a.get("versionName"),
            "version_code": a.get("versionCode"), "split": a.get("split"),
            "min_sdk": None, "target_sdk": None, "debuggable": None, "allow_backup": None,
            "cleartext": None, "network_security_config": None, "app_class": "",
            "permissions": [], "custom_permissions": [], "features": [],
            "components": {k: [] for k in KINDS}, "launcher": "", "meta": []}
    for u in root.kids("uses-sdk"):
        info["min_sdk"] = u.attrs.get("minSdkVersion")
        info["target_sdk"] = u.attrs.get("targetSdkVersion")
    for tag in ("uses-permission", "uses-permission-sdk-23", "uses-permission-sdk-m"):
        for u in root.kids(tag):
            n = u.attrs.get("name")
            if n and n not in info["permissions"]:
                info["permissions"].append(str(n))
    for u in root.kids("permission"):
        if u.attrs.get("name"):
            info["custom_permissions"].append(str(u.attrs["name"]))
    for u in root.kids("uses-feature"):
        if u.attrs.get("name"):
            info["features"].append(str(u.attrs["name"]))
    for app in root.kids("application"):
        aa = app.attrs
        info["debuggable"] = _flag(aa.get("debuggable"))
        info["allow_backup"] = _flag(aa.get("allowBackup"))
        info["cleartext"] = _flag(aa.get("usesCleartextTraffic"))
        info["network_security_config"] = aa.get("networkSecurityConfig")
        info["app_class"] = _fq(pkg, aa.get("name"))
        for m in app.kids("meta-data")[:60]:
            nm = str(m.attrs.get("name", ""))
            val = m.attrs.get("value", m.attrs.get("resource", ""))
            if re.search(r"key|secret|token|password", nm, re.I):
                val = "(hidden)"
            info["meta"].append("%s = %s" % (nm, str(val)[:80]))
        for c in app.children:
            if c.tag not in KINDS:
                continue
            filt = []
            for f in c.kids("intent-filter"):
                filt.append({
                    "actions": [str(x.attrs.get("name", "")) for x in f.kids("action")],
                    "categories": [str(x.attrs.get("name", "")) for x in f.kids("category")],
                    "data": [" ".join("%s=%s" % (k, v) for k, v in x.attrs.items()
                                      if k in ("scheme", "host", "path", "pathPrefix", "mimeType"))
                             for x in f.kids("data")]})
            exp = _flag(c.attrs.get("exported"))
            if c.tag == "provider":
                eff = exp is True
            else:
                eff = exp if exp is not None else bool(filt)
            comp = {"name": _fq(pkg, c.attrs.get("name") or c.attrs.get("targetActivity")),
                    "exported": exp, "effective_exported": bool(eff),
                    "enabled": c.attrs.get("enabled"), "permission": c.attrs.get("permission"),
                    "filters": filt, "authorities": c.attrs.get("authorities")}
            info["components"][c.tag].append(comp)
            for f in filt:
                if ("android.intent.action.MAIN" in f["actions"]
                        and any("LAUNCHER" in x for x in f["categories"])):
                    if not info["launcher"] and c.tag != "service":
                        info["launcher"] = comp["name"]
    return info


# ---------------------------------------------------------------- DEX

def _uleb(d, o):
    r = 0
    s = 0
    while True:
        b = d[o]
        o += 1
        r |= (b & 0x7F) << s
        if not b & 0x80:
            return r, o
        s += 7
        if s > 35:
            raise ApkError("Corrupted DEX number.")


_PRIM = {"V": "void", "Z": "boolean", "B": "byte", "S": "short", "C": "char",
         "I": "int", "J": "long", "F": "float", "D": "double"}


def pretty(desc):
    dims = 0
    while desc.startswith("["):
        dims += 1
        desc = desc[1:]
    if desc.startswith("L") and desc.endswith(";"):
        s = desc[1:-1].replace("/", ".")
    else:
        s = _PRIM.get(desc, desc)
    return s + "[]" * dims


def _flags(acc):
    names = ((1, "public"), (2, "private"), (4, "protected"), (8, "static"), (0x10, "final"),
             (0x100, "native"), (0x200, "interface"), (0x400, "abstract"), (0x1000, "synthetic"),
             (0x4000, "enum"))
    return " ".join(n for bit, n in names if acc & bit)


class Dex(object):
    def __init__(self, data, name="classes.dex"):
        if len(data) < 0x70 or data[:4] != b"dex\n":
            raise ApkError("%s is not a valid DEX file." % name)
        self.d = data
        self.name = name
        (self.n_str, self.o_str, self.n_type, self.o_type, self.n_proto, self.o_proto,
         self.n_field, self.o_field, self.n_meth, self.o_meth, self.n_cls,
         self.o_cls) = struct.unpack_from("<12I", data, 0x38)
        L = len(data)
        for n, o, sz in ((self.n_str, self.o_str, 4), (self.n_type, self.o_type, 4),
                         (self.n_proto, self.o_proto, 12), (self.n_field, self.o_field, 8),
                         (self.n_meth, self.o_meth, 8), (self.n_cls, self.o_cls, 32)):
            if n and (o + n * sz > L):
                raise ApkError("%s is corrupted (table outside file)." % name)
        self._types = None

    def string(self, i):
        d = self.d
        off = struct.unpack_from("<I", d, self.o_str + 4 * i)[0]
        _n, p = _uleb(d, off)
        e = d.find(b"\0", p)
        if e < 0:
            e = len(d)
        return d[p:e].decode("utf-8", "replace")

    def type_desc(self, i):
        return self.string(struct.unpack_from("<I", self.d, self.o_type + 4 * i)[0])

    def proto(self, i):
        _sh, ret, poff = struct.unpack_from("<III", self.d, self.o_proto + 12 * i)
        params = []
        if poff:
            n = struct.unpack_from("<I", self.d, poff)[0]
            params = list(struct.unpack_from("<%dH" % n, self.d, poff + 4)) if n else []
        return ret, params

    def method(self, i):
        return struct.unpack_from("<HHI", self.d, self.o_meth + 8 * i)

    def field(self, i):
        return struct.unpack_from("<HHI", self.d, self.o_field + 8 * i)

    def class_def(self, i):
        return struct.unpack_from("<8I", self.d, self.o_cls + 32 * i)

    def method_sig(self, i, with_class=False):
        cidx, pidx, nidx = self.method(i)
        ret, params = self.proto(pidx)
        s = "%s %s(%s)" % (pretty(self.type_desc(ret)), self.string(nidx),
                           ", ".join(pretty(self.type_desc(p)) for p in params))
        if with_class:
            s = pretty(self.type_desc(cidx)) + "." + s
        return s

    def members(self, ci):
        off = self.class_def(ci)[6]
        fields, methods = [], []
        if not off:
            return fields, methods
        d = self.d
        sf, p = _uleb(d, off)
        inf, p = _uleb(d, p)
        dm, p = _uleb(d, p)
        vm, p = _uleb(d, p)
        if max(sf, inf, dm, vm) > 65535:
            raise ApkError("Corrupted class data in %s." % self.name)
        for kind, cnt in (("static", sf), ("instance", inf)):
            idx = 0
            for _ in range(cnt):
                diff, p = _uleb(d, p)
                acc, p = _uleb(d, p)
                idx += diff
                fields.append((idx, acc, kind))
        for kind, cnt in (("direct", dm), ("virtual", vm)):
            idx = 0
            for _ in range(cnt):
                diff, p = _uleb(d, p)
                acc, p = _uleb(d, p)
                code, p = _uleb(d, p)
                idx += diff
                methods.append((idx, acc, code, kind))
        return fields, methods

    def interfaces(self, ci):
        off = self.class_def(ci)[3]
        if not off:
            return []
        n = struct.unpack_from("<I", self.d, off)[0]
        return [self.type_desc(t) for t in struct.unpack_from("<%dH" % n, self.d, off + 4)] if n else []


# ---------------------------------------------------------------- knowledge tables

LIBS = {
    "OkHttp": ("Lokhttp3/",), "Retrofit": ("Lretrofit2/",), "Volley": ("Lcom/android/volley/",),
    "Apache HttpClient": ("Lorg/apache/http/",), "Cronet": ("Lorg/chromium/net/",),
    "Ktor": ("Lio/ktor/",), "Glide": ("Lcom/bumptech/glide/",), "Picasso": ("Lcom/squareup/picasso/",),
    "Coil": ("Lcoil/",), "Room (database)": ("Landroidx/room/",),
    "SQLDelight": ("Lcom/squareup/sqldelight/", "Lapp/cash/sqldelight/"),
    "Realm": ("Lio/realm/",), "DataStore": ("Landroidx/datastore/",),
    "Firebase": ("Lcom/google/firebase/",), "Google Play services": ("Lcom/google/android/gms/",),
    "Gson": ("Lcom/google/gson/",), "Moshi": ("Lcom/squareup/moshi/",),
    "Jackson": ("Lcom/fasterxml/jackson/",), "Kotlin coroutines": ("Lkotlinx/coroutines/",),
    "RxJava": ("Lio/reactivex/",), "Dagger/Hilt": ("Ldagger/",),
    "Jetpack Compose": ("Landroidx/compose/",), "WorkManager": ("Landroidx/work/",),
    "ExoPlayer/Media3": ("Lcom/google/android/exoplayer2/", "Landroidx/media3/"),
    "TensorFlow Lite": ("Lorg/tensorflow/",), "ML Kit": ("Lcom/google/mlkit/",),
    "Facebook SDK": ("Lcom/facebook/",), "AppsFlyer": ("Lcom/appsflyer/",),
    "Adjust": ("Lcom/adjust/",), "Sentry": ("Lio/sentry/",), "Crashlytics": ("Lcom/google/firebase/crashlytics/",),
    "Ads (AdMob)": ("Lcom/google/android/gms/ads/",), "Unity": ("Lcom/unity3d/",),
    "React Native": ("Lcom/facebook/react/",), "Flutter": ("Lio/flutter/",),
    "Kivy / python-for-android": ("Lorg/kivy/", "Lorg/renpy/"), "pyjnius": ("Lorg/jnius/",),
    "Cordova": ("Lorg/apache/cordova/",), "Biometric": ("Landroidx/biometric/",),
}
NETWORK_LIBS = ("OkHttp", "Retrofit", "Volley", "Apache HttpClient", "Cronet", "Ktor")
STORAGE_LIBS = ("Room (database)", "SQLDelight", "Realm", "DataStore")

SIGNALS = {
    "WebView": ("Landroid/webkit/WebView;",),
    "JavaScript bridge": ("Landroid/webkit/JavascriptInterface;",),
    "Crypto (javax.crypto)": ("Ljavax/crypto/",),
    "Dynamic code loading": ("Ldalvik/system/DexClassLoader;", "Ldalvik/system/InMemoryDexClassLoader;"),
    "Reflection": ("Ljava/lang/reflect/Method;",),
    "Process execution": ("Ljava/lang/ProcessBuilder;",),
    "SMS": ("Landroid/telephony/SmsManager;",),
    "Location": ("Landroid/location/LocationManager;",),
    "Camera": ("Landroid/hardware/camera2/", "Landroidx/camera/"),
    "Accounts": ("Landroid/accounts/AccountManager;",),
    "Background jobs": ("Landroid/app/job/JobScheduler;", "Landroidx/work/", "Landroid/app/AlarmManager;"),
    "SQLite": ("Landroid/database/sqlite/",),
    "SharedPreferences": ("Landroid/content/SharedPreferences;",),
    "Accessibility service": ("Landroid/accessibilityservice/",),
    "Clipboard": ("Landroid/content/ClipboardManager;",),
    "Package installer": ("Landroid/content/pm/PackageInstaller;",),
    "Device admin": ("Landroid/app/admin/",),
}
_ALLPFX = tuple(sorted({p for v in list(LIBS.values()) + list(SIGNALS.values()) for p in v}))

FRAMEWORK_FILES = (
    ("Flutter", "libflutter.so"), ("Unity", "libunity.so"), ("React Native", "libreactnativejni.so"),
    ("React Native (JS bundle)", "assets/index.android.bundle"), ("Xamarin / .NET", "assemblies/"),
    ("Cordova / web app", "assets/www/"), ("Kivy / Python", "libpython"), ("Godot", "libgodot"),
    ("llama.cpp / GGML", "libggml"), ("TensorFlow Lite", "libtensorflowlite"))

URL_RE = re.compile(r"(?:https?|wss?)://[^\s\"'<>\\]{4,200}")
SECRET_RE = re.compile(
    r"AIza[0-9A-Za-z_\-]{35}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"xox[baprs]-[0-9A-Za-z\-]{10,}|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{24,}|"
    r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{1,200}\.[A-Za-z]{2,}")
AUTH_WORDS = ("login", "signin", "sign_in", "auth", "oauth", "token", "session", "credential",
              "password", "account")


def mask(s):
    s = str(s)
    return s[:6] + "..." + "(%d chars)" % len(s)


def scrub(text):
    """Remove secret-looking values and email addresses before text leaves the phone."""
    text = SECRET_RE.sub("[REDACTED]", text)
    text = EMAIL_RE.sub("[EMAIL]", text)
    return re.sub(r"(?i)(bearer|api[_-]?key|secret|password|token)(\W{0,3})[A-Za-z0-9_\-\.]{12,}",
                  r"\1\2[REDACTED]", text)


def _short_name(desc):
    n = desc[1:-1] if desc.startswith("L") and desc.endswith(";") else desc
    parts = n.split("/")
    return parts


# ---------------------------------------------------------------- analysis

def _pick_base(zf, apks):
    for n in apks:
        if os.path.basename(n).lower() == "base.apk":
            return n
    plain = [n for n in apks if not re.search(r"split_|config\.", os.path.basename(n).lower())]
    pool = plain or apks
    return max(pool, key=lambda n: zf.getinfo(n).file_size)


def _index_dex(dex, no, fs, fc, fm, st, cancel):
    """Write strings/classes/methods of one DEX to the index files and collect findings."""
    types = [dex.type_desc(i) for i in range(dex.n_type)]
    st["types"].update(types)
    # strings
    for i in range(dex.n_str):
        if i % 4000 == 0 and cancel and cancel():
            raise Cancelled()
        if st["n_str"] >= MAX_STRINGS:
            st["limits"].add("String index stopped at %d strings (limit)." % MAX_STRINGS)
            break
        s = dex.string(i)
        st["n_str"] += 1
        if not s:
            continue
        line = s.replace("\n", "\\n").replace("\r", "\\r")[:400]
        fs.write("%d\t%s\n" % (no, line))
        if "://" in s:
            for m in URL_RE.finditer(s):
                u = m.group(0).rstrip(".,;)")
                if len(st["urls"]) < 400:
                    st["urls"].add(u)
        if len(s) >= 16:
            for m in SECRET_RE.finditer(s):
                if len(st["secrets"]) < 30:
                    st["secrets"].add(mask(m.group(0)))
    # classes
    n_cls = 0
    for i in range(dex.n_cls):
        if i % 4000 == 0 and cancel and cancel():
            raise Cancelled()
        cidx = dex.class_def(i)[0]
        desc = types[cidx] if cidx < len(types) else ""
        fc.write("%d\t%s\n" % (no, desc))
        n_cls += 1
        parts = _short_name(desc)
        if parts:
            st["cls_total"] += 1
            if len(parts[-1]) <= 2 and all(len(p) <= 2 for p in parts[:-1]):
                st["cls_short"] += 1
            low = desc.lower()
            if len(st["auth_cls"]) < 30 and any(w in low for w in AUTH_WORDS):
                st["auth_cls"].append(pretty(desc))
    # methods
    proto_cache = {}
    n_m = 0
    for i in range(dex.n_meth):
        if i % 4000 == 0 and cancel and cancel():
            raise Cancelled()
        if st["n_meth"] >= MAX_METHODS:
            st["limits"].add("Method index stopped at %d methods (limit)." % MAX_METHODS)
            break
        cidx, pidx, nidx = dex.method(i)
        p = proto_cache.get(pidx)
        if p is None:
            ret, params = dex.proto(pidx)
            p = "(" + "".join(types[t] for t in params if t < len(types)) + ")" + (types[ret] if ret < len(types) else "")
            proto_cache[pidx] = p
        fm.write("%d\t%s->%s%s\n" % (no, types[cidx] if cidx < len(types) else "?", dex.string(nidx), p))
        st["n_meth"] += 1
        n_m += 1
    return n_cls, n_m


def analyze(src_path, root, orig_name="", progress=None, cancel=None, max_bytes=MAX_APK):
    """Analyze a local file (APK or split bundle). Returns the info dict (also saved in the
    workspace folder root/<sha16>/info.json). Never executes anything from the file."""
    def say(m):
        if progress:
            progress(m)

    def chk():
        if cancel and cancel():
            raise Cancelled()

    t0 = time.time()
    say("1/7 Checking the file and hashing it")
    if not os.path.isfile(src_path):
        raise ApkError("File not found.")
    size = os.path.getsize(src_path)
    if size == 0:
        raise ApkError("The file is empty.")
    if size > max_bytes:
        raise ApkError("The file is larger than the %d MB limit." % (max_bytes >> 20))
    sha = sha256_file(src_path, cancel)
    ws = os.path.join(root, sha[:16])
    cache = os.path.join(ws, "info.json")
    if os.path.exists(cache):
        try:
            old = json.load(open(cache, encoding="utf-8"))
            if old.get("schema") == SCHEMA and old.get("sha256") == sha:
                old["cached"] = True
                return old
        except (ValueError, OSError):
            pass
    if not zipfile.is_zipfile(src_path):
        raise ApkError("This is not a valid APK: it is not a ZIP archive. "
                       "The download may be incomplete or damaged.")
    os.makedirs(ws, exist_ok=True)
    base_apk = os.path.join(ws, "base.apk")
    info = {"schema": SCHEMA, "sha256": sha, "size": size, "file_name": orig_name or "app.apk",
            "archive": "apk", "splits": [], "limits": [], "cached": False}
    try:
        try:
            zf = zipfile.ZipFile(src_path)
        except zipfile.BadZipFile:
            raise ApkError("The ZIP structure is damaged (incomplete or corrupted file).")
        names = zf.namelist()
        if len(names) > MAX_ENTRIES:
            raise ApkError("The archive has too many entries (%d)." % len(names))
        if "AndroidManifest.xml" not in names:
            apks = [n for n in names if n.lower().endswith(".apk")]
            if not apks:
                raise ApkError("No AndroidManifest.xml found. This is not an APK or a split bundle.")
            base = _pick_base(zf, apks)
            say("1/7 Split bundle found. Extracting the base APK: " + os.path.basename(base))
            try:
                with zf.open(base) as src:
                    copy_stream(src, base_apk, max_bytes, cancel)
            except RuntimeError:
                raise ApkError("The bundle is encrypted.")
            info["archive"] = "bundle"
            info["base_name"] = os.path.basename(base)
            info["splits"] = sorted(os.path.basename(n) for n in apks if n != base)
            zf.close()
            zf = zipfile.ZipFile(base_apk)
            names = zf.namelist()
            if "AndroidManifest.xml" not in names:
                raise ApkError("The base APK inside the bundle has no AndroidManifest.xml.")
        else:
            os.replace(src_path, base_apk)
            zf.close()
            zf = zipfile.ZipFile(base_apk)
        chk()
        say("2/7 Reading AndroidManifest.xml")
        zi = zf.getinfo("AndroidManifest.xml")
        if zi.flag_bits & 1:
            raise ApkError("AndroidManifest.xml is encrypted.")
        if zi.file_size > MAX_MANIFEST:
            raise ApkError("AndroidManifest.xml is unusually large; refusing to parse it.")
        try:
            man = manifest_info(parse_axml(zf.read("AndroidManifest.xml")))
        except (zipfile.BadZipFile, RuntimeError, OSError, EOFError) as e:
            raise ApkError("Could not read the manifest (damaged or encrypted archive): " + str(e)[:80])
        info.update(man)
        say("3/7 Listing files, libraries and assets")
        ent = zf.infolist()
        native, assets, sigs, framework = {}, [], [], []
        with open(os.path.join(ws, "entries.txt"), "w", encoding="utf-8") as fe:
            for z in ent:
                fe.write("%d\t%s\n" % (z.file_size, z.filename))
                n = z.filename
                m = re.match(r"lib/([^/]+)/(.+\.so)$", n)
                if m:
                    native.setdefault(m.group(1), []).append(m.group(2))
                elif n.startswith("assets/") and not n.endswith("/"):
                    assets.append(n)
                elif n.startswith("META-INF/") and re.search(r"\.(RSA|DSA|EC|SF|MF)$", n):
                    sigs.append(n)
        for label, key in FRAMEWORK_FILES:
            if any((key in z.filename) for z in ent):
                framework.append(label)
        info["native"] = native
        info["assets"] = {"count": len(assets), "sample": assets[:25],
                          "config_like": [a for a in assets if re.search(
                              r"\.(json|xml|ya?ml|properties|cfg|ini|txt|conf|db|sqlite)$", a, re.I)][:30]}
        info["entries"] = len(ent)
        info["resources_arsc"] = "resources.arsc" in names
        info["signature_files"] = sigs[:10]
        info["frameworks"] = framework
        info["has_kotlin"] = any(n.startswith("kotlin/") or n.endswith(".kotlin_module") for n in names)
        chk()
        dex_names = sorted([n for n in names if re.match(r"classes\d*\.dex$", n)],
                           key=lambda n: (len(n), n))
        st = {"types": set(), "urls": set(), "secrets": set(), "auth_cls": [], "limits": set(),
              "n_str": 0, "n_meth": 0, "cls_total": 0, "cls_short": 0}
        info["dex"] = []
        if not dex_names:
            info["limits"].append("No classes.dex found: this archive has no app code of its own.")
        with open(os.path.join(ws, "strings.txt"), "w", encoding="utf-8") as fs, \
                open(os.path.join(ws, "classes.txt"), "w", encoding="utf-8") as fc, \
                open(os.path.join(ws, "methods.txt"), "w", encoding="utf-8") as fm:
            for no, dn in enumerate(dex_names):
                chk()
                say("4/7 Reading %s (%d of %d)" % (dn, no + 1, len(dex_names)))
                z = zf.getinfo(dn)
                if z.file_size > MAX_DEX:
                    info["limits"].append("%s is %d MB, over the %d MB limit, so it was skipped."
                                          % (dn, z.file_size >> 20, MAX_DEX >> 20))
                    info["dex"].append({"name": dn, "skipped": True})
                    continue
                if z.flag_bits & 1:
                    raise ApkError(dn + " is encrypted.")
                try:
                    data = zf.read(dn)
                    dex = Dex(data, dn)
                    say("5/7 Indexing %s: %d strings, %d classes" % (dn, dex.n_str, dex.n_cls))
                    nc, nm = _index_dex(dex, no, fs, fc, fm, st, cancel)
                except (zipfile.BadZipFile, RuntimeError, EOFError, struct.error, IndexError) as e:
                    raise ApkError("%s is damaged: %s" % (dn, str(e)[:80]))
                info["dex"].append({"name": dn, "strings": dex.n_str, "classes": nc,
                                    "methods": nm, "size": z.file_size})
                del data, dex
        say("6/7 Identifying libraries and behavior")
        types = st["types"]
        hits = {}
        for t in types:
            if t.startswith(_ALLPFX):
                for pfx in _ALLPFX:
                    if t.startswith(pfx):
                        hits[pfx] = hits.get(pfx, 0) + 1
        info["libs"] = [k for k, v in LIBS.items() if any(p in hits for p in v)]
        info["signals"] = [k for k, v in SIGNALS.items() if any(p in hits for p in v)]
        info["urls"] = sorted(st["urls"])[:300]
        hosts = {}
        for u in st["urls"]:
            m = re.match(r"\w+://([^/:?#]+)", u)
            if m:
                hosts[m.group(1).lower()] = hosts.get(m.group(1).lower(), 0) + 1
        info["hosts"] = dict(sorted(hosts.items(), key=lambda kv: -kv[1])[:60])
        info["secrets"] = sorted(st["secrets"])
        info["auth_classes"] = st["auth_cls"]
        info["n_classes"] = st["cls_total"]
        info["n_methods"] = st["n_meth"]
        info["n_strings"] = st["n_str"]
        info["obfuscation"] = round(st["cls_short"] / float(st["cls_total"]), 3) if st["cls_total"] else 0.0
        for l in st["limits"]:
            info["limits"].append(l)
        say("7/7 Writing the report data")
        if info.get("split"):
            info["limits"].append("This APK is a split ('%s'). Splits carry resources or libraries "
                                  "but usually not the app logic; analyze the base APK as well." % info["split"])
        if info["archive"] == "bundle" and info["splits"]:
            info["limits"].append("Bundle with %d split file(s). Only the base APK was analyzed; "
                                  "native libraries and resources in the splits were not." % len(info["splits"]))
        if info["obfuscation"] >= 0.5:
            info["limits"].append("Heavily obfuscated (%d%% of class names are 1-2 letters). Names "
                                  "will not describe what the code does." % int(info["obfuscation"] * 100))
        elif info["obfuscation"] >= 0.2:
            info["limits"].append("Partly obfuscated (%d%% short class names)." % int(info["obfuscation"] * 100))
        if native:
            info["limits"].append("Contains native libraries (%s). Their code is not analyzed here."
                                  % ", ".join(sorted(native)))
        if info["resources_arsc"]:
            info["limits"].append("resources.arsc is not decoded: app labels, layouts and string "
                                  "resources are not shown (Apktool does that).")
        info["limits"].append("Bytecode is not decompiled or disassembled. Class and method lists "
                              "and strings are real; what the code does is inferred from names, "
                              "strings and libraries. JADX or Apktool on a computer give full code.")
        info["limits"].append("Server-side behavior cannot be seen from the APK.")
        info["ws"] = ws
        info["seconds"] = round(time.time() - t0, 1)
        tmp = cache + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(info, f)
        os.replace(tmp, cache)
        zf.close()
        return info
    except BaseException:
        try:
            zf.close()
        except Exception:
            pass
        shutil.rmtree(ws, ignore_errors=True)
        raise


# ---------------------------------------------------------------- workspace + tools

def load_info(ws):
    p = os.path.join(ws, "info.json")
    if not os.path.isfile(p):
        raise ToolError("No analyzed APK. Use: apk pick")
    return json.load(open(p, encoding="utf-8"))


def grep_file(path, q, limit=40, maxlen=240):
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


def _clip(s, n=MAX_OUT):
    return s if len(s) <= n else s[:n - 40] + "\n... (cut, ask for a narrower search)"


def _yn(v):
    return "unknown" if v is None else ("yes" if v else "no")


def t_manifest(ws, a):
    i = load_info(ws)
    comp = i["components"]
    lines = ["Package: %s" % i["package"], "Version: %s (code %s)" % (i.get("version_name"), i.get("version_code")),
             "Min SDK %s, target SDK %s" % (i.get("min_sdk"), i.get("target_sdk")),
             "Launcher activity: %s" % (i.get("launcher") or "none found"),
             "Application class: %s" % (i.get("app_class") or "default"),
             "Debuggable: %s | Backup allowed: %s | Cleartext HTTP: %s" % (
                 _yn(i.get("debuggable")), _yn(i.get("allow_backup")), _yn(i.get("cleartext"))),
             "Components: " + ", ".join("%d %s" % (len(comp[k]), k) for k in KINDS),
             "Permissions: %d" % len(i["permissions"])]
    if i.get("network_security_config"):
        lines.append("Network security config: %s" % i["network_security_config"])
    if i.get("split"):
        lines.append("Split name: %s" % i["split"])
    if i.get("meta"):
        lines.append("Meta-data: " + "; ".join(i["meta"][:8]))
    return "\n".join(lines)


def t_permissions(ws, a):
    i = load_info(ws)
    sens, other = [], []
    for p in i["permissions"]:
        (sens if p.split(".")[-1] in DANGEROUS else other).append(p)
    out = ["%d permissions; %d sensitive." % (len(i["permissions"]), len(sens))]
    if sens:
        out.append("SENSITIVE:\n" + "\n".join("  " + p for p in sens))
    if other:
        out.append("OTHER:\n" + "\n".join("  " + p for p in other))
    if i["custom_permissions"]:
        out.append("DECLARED BY APP:\n" + "\n".join("  " + p for p in i["custom_permissions"]))
    return "\n".join(out)


def t_components(ws, a):
    i = load_info(ws)
    kind = a.get("kind", "all")
    only = bool(a.get("exported_only", False))
    out = []
    for k in KINDS:
        if kind != "all" and k != kind:
            continue
        rows = [c for c in i["components"][k] if (c["effective_exported"] or not only)]
        out.append("%s (%d)" % (k.upper(), len(rows)))
        for c in rows[:40]:
            tag = "EXPORTED" if c["effective_exported"] else "internal"
            extra = ""
            acts = [x for f in c["filters"] for x in f["actions"]]
            if acts:
                extra = "  actions: " + ", ".join(a_.split(".")[-1] for a_ in acts[:4])
            if c.get("authorities"):
                extra += "  authorities: %s" % c["authorities"]
            if c.get("permission"):
                extra += "  needs: %s" % str(c["permission"]).split(".")[-1]
            out.append("  [%s] %s%s" % (tag, c["name"], extra))
        if len(rows) > 40:
            out.append("  ... %d more" % (len(rows) - 40))
    return _clip("\n".join(out) or "No components.")


def t_strings(ws, a):
    q = a["query"]
    rows = grep_file(os.path.join(ws, "strings.txt"), q, a.get("limit", 40))
    if not rows:
        return "No strings contain '%s'." % q
    return _clip("%d string(s) containing '%s':\n" % (len(rows), q) +
                 "\n".join("  [dex%s] %s" % tuple(r.split("\t", 1)) if "\t" in r else r for r in rows))


def t_classes(ws, a):
    q = a.get("query", "")
    lim = a.get("limit", 60)
    rows = grep_file(os.path.join(ws, "classes.txt"), q, lim, 200) if q else grep_file(os.path.join(ws, "classes.txt"), "", lim, 200)
    if not rows:
        return "No classes match '%s'." % q
    return _clip("%d class(es):\n" % len(rows) + "\n".join(
        "  " + pretty(r.split("\t", 1)[1]) for r in rows if "\t" in r))


def _find_class(ws, name):
    name = name.strip()
    if name.startswith("L") and name.endswith(";") and "/" in name:
        want = name
        exact = grep_file(os.path.join(ws, "classes.txt"), want, 5, 300)
        exact = [r for r in exact if r.split("\t", 1)[1] == want]
    else:
        n = name.replace(".", "/")
        want = "L" + n + ";"
        rows = grep_file(os.path.join(ws, "classes.txt"), n, 400, 300)
        exact = [r for r in rows if r.split("\t", 1)[1] == want]
        if not exact:
            exact = [r for r in rows if r.split("\t", 1)[1].endswith("/" + n + ";")]
    out = []
    for r in exact[:10]:
        no, desc = r.split("\t", 1)
        out.append((int(no), desc))
    return out


def _open_dex(ws, info, no):
    d = info["dex"][no]
    if d.get("skipped"):
        raise ToolError("That DEX file was skipped (too large).")
    with zipfile.ZipFile(os.path.join(ws, "base.apk")) as zf:
        return Dex(zf.read(d["name"]), d["name"])


def _class_report(ws, info, no, desc, method_filter=None):
    dex = _open_dex(ws, info, no)
    ci = None
    for i in range(dex.n_cls):
        if dex.type_desc(dex.class_def(i)[0]) == desc:
            ci = i
            break
    if ci is None:
        raise ToolError("Class not found in " + dex.name)
    cd = dex.class_def(ci)
    fields, methods = dex.members(ci)
    out = ["class %s  (%s)" % (pretty(desc), dex.name), "  flags: %s" % (_flags(cd[1]) or "none")]
    if cd[2] != 0xFFFFFFFF:
        out.append("  extends %s" % pretty(dex.type_desc(cd[2])))
    ifs = dex.interfaces(ci)
    if ifs:
        out.append("  implements %s" % ", ".join(pretty(x) for x in ifs))
    if cd[4] != 0xFFFFFFFF:
        out.append("  source file: %s" % dex.string(cd[4]))
    if method_filter is None:
        out.append("  fields (%d):" % len(fields))
        for idx, acc, kind in fields[:40]:
            _c, t, n = dex.field(idx)
            out.append("    %s %s %s" % (_flags(acc) or "-", pretty(dex.type_desc(t)), dex.string(n)))
    shown = []
    for idx, acc, code, kind in methods:
        sig = dex.method_sig(idx)
        if method_filter is not None and method_filter.lower() not in sig.lower():
            continue
        shown.append("    %s %s%s" % (_flags(acc) or "-", sig, "" if code else "  [no code]"))
    out.append("  methods (%d%s):" % (len(shown), "" if method_filter is None else " matching '%s'" % method_filter))
    out.extend(shown[:70])
    if len(shown) > 70:
        out.append("    ... %d more" % (len(shown) - 70))
    out.append("  (Method bodies are not disassembled here. Use JADX on a computer for the code.)")
    return "\n".join(out)


def t_class(ws, a):
    info = load_info(ws)
    found = _find_class(ws, a["name"])
    if not found:
        return "No class named '%s'. Try: apk classes <part of the name>" % a["name"]
    if len(found) > 1:
        return "Several classes match; give the full name:\n" + "\n".join("  " + pretty(d) for _n, d in found)
    return _clip(_class_report(ws, info, found[0][0], found[0][1]))


def t_method(ws, a):
    info = load_info(ws)
    found = _find_class(ws, a["class"])
    if not found:
        return "No class named '%s'." % a["class"]
    if len(found) > 1:
        return "Several classes match; give the full name:\n" + "\n".join("  " + pretty(d) for _n, d in found)
    return _clip(_class_report(ws, info, found[0][0], found[0][1], a["method"]))


def t_search(ws, a):
    q = a["query"]
    out = []
    cls = grep_file(os.path.join(ws, "classes.txt"), q, 12, 200)
    if cls:
        out.append("CLASSES:\n" + "\n".join("  " + pretty(r.split("\t", 1)[1]) for r in cls if "\t" in r))
    mt = grep_file(os.path.join(ws, "methods.txt"), q, 12, 200)
    if mt:
        out.append("METHODS:\n" + "\n".join("  " + r.split("\t", 1)[1] for r in mt if "\t" in r))
    st = grep_file(os.path.join(ws, "strings.txt"), q, 12, 200)
    if st:
        out.append("STRINGS:\n" + "\n".join("  " + r.split("\t", 1)[1] for r in st if "\t" in r))
    ent = grep_file(os.path.join(ws, "entries.txt"), q, 8, 200)
    if ent:
        out.append("FILES:\n" + "\n".join("  " + r.split("\t", 1)[1] for r in ent if "\t" in r))
    return _clip("\n".join(out)) if out else "Nothing in the APK matches '%s'." % q


def t_deps(ws, a):
    i = load_info(ws)
    out = ["Libraries found by class names (%d):" % len(i.get("libs", []))]
    out += ["  " + x for x in i.get("libs", [])] or ["  none recognised"]
    if i.get("frameworks"):
        out.append("Frameworks: " + ", ".join(i["frameworks"]))
    if i.get("native"):
        out.append("Native libraries:")
        for abi, libs in sorted(i["native"].items()):
            out.append("  %s: %s" % (abi, ", ".join(sorted(libs)[:12])))
    if i.get("signals"):
        out.append("Behavior signals: " + ", ".join(i["signals"]))
    stor = [x for x in i.get("libs", []) if x in STORAGE_LIBS] + [
        x for x in i.get("signals", []) if x in ("SQLite", "SharedPreferences")]
    out.append("Local storage hints: " + (", ".join(stor) if stor else "none recognised"))
    return _clip("\n".join(out))


def t_network(ws, a):
    i = load_info(ws)
    out = []
    nl = [x for x in i.get("libs", []) if x in NETWORK_LIBS]
    out.append("Network libraries: " + (", ".join(nl) if nl else "none recognised (may use java.net directly)"))
    out.append("INTERNET permission: " + ("yes" if any(p.endswith("INTERNET") for p in i["permissions"]) else "no"))
    out.append("Cleartext HTTP allowed by manifest: %s" % _yn(i.get("cleartext")))
    if i.get("network_security_config"):
        out.append("Network security config: %s" % i["network_security_config"])
    if "WebView" in i.get("signals", []):
        out.append("WebView is used.")
    hosts = i.get("hosts", {})
    out.append("Hosts in strings (%d):" % len(hosts))
    out += ["  %s (%d)" % kv for kv in list(hosts.items())[:25]]
    urls = i.get("urls", [])
    out.append("URLs (%d, first 15):" % len(urls))
    out += ["  " + u for u in urls[:15]]
    http = [u for u in urls if u.startswith("http://")]
    if http:
        out.append("Plain http:// URLs: %d" % len(http))
    for w in ("Authorization", "Bearer"):
        n = len(grep_file(os.path.join(ws, "strings.txt"), w, 5))
        if n:
            out.append("String '%s' present (%s)" % (w, "auth header use is likely"))
    return _clip("\n".join(out))


def t_summary(ws, a):
    i = load_info(ws)
    out = ["%s v%s" % (i["package"], i.get("version_name")),
           "%d KB, %d classes, %d methods, %d strings, %d dex file(s)" % (
               i["size"] // 1024, i.get("n_classes", 0), i.get("n_methods", 0), i.get("n_strings", 0),
               len([d for d in i.get("dex", []) if not d.get("skipped")])),
           "Launcher: %s" % (i.get("launcher") or "none"),
           "Libraries: " + (", ".join(i.get("libs", [])[:12]) or "none recognised"),
           "Frameworks: " + (", ".join(i.get("frameworks", [])) or "none"),
           "Signals: " + (", ".join(i.get("signals", [])) or "none"),
           "Sensitive permissions: " + (", ".join(p.split(".")[-1] for p in i["permissions"]
                                                 if p.split(".")[-1] in DANGEROUS) or "none"),
           "Exported components: %d" % sum(1 for k in KINDS for c in i["components"][k] if c["effective_exported"]),
           "Hosts: " + (", ".join(list(i.get("hosts", {}))[:6]) or "none found"),
           "Obfuscation: %d%% short class names" % int(i.get("obfuscation", 0) * 100)]
    return "\n".join(out)


def t_files(ws, a):
    q = a.get("query", "")
    rows = grep_file(os.path.join(ws, "entries.txt"), q, 60, 200)
    return _clip("\n".join("  %s bytes  %s" % tuple(r.split("\t", 1)) for r in rows if "\t" in r) or "No files match.")


def read_file(ws, path, limit=6000):
    """Show a small text file from inside the APK. Path must be an exact entry name."""
    if not path or len(path) > 300 or any(ord(c) < 32 for c in path):
        raise ToolError("Bad path.")
    with zipfile.ZipFile(os.path.join(ws, "base.apk")) as zf:
        names = set(zf.namelist())
        if path not in names:
            raise ToolError("No such file in the APK. Use: apk files <part of the name>")
        zi = zf.getinfo(path)
        if zi.flag_bits & 1:
            raise ToolError("That file is encrypted.")
        if zi.file_size > 2 * 1024 * 1024:
            raise ToolError("That file is over 2 MB; not shown.")
        raw = zf.read(path)
    if b"\x00" in raw[:2000]:
        return "(binary file, %d bytes)" % len(raw)
    return _clip(raw.decode("utf-8", "replace"), limit)


_TOOL_FN = {"inspect_apk_manifest": t_manifest, "list_permissions": t_permissions,
            "list_components": t_components, "search_apk_strings": t_strings,
            "list_classes": t_classes, "inspect_class": t_class, "inspect_method": t_method,
            "search_code": t_search, "inspect_dependencies": t_deps,
            "inspect_network_references": t_network, "summarize_apk": t_summary}

TOOLS = {
    "inspect_apk_manifest": {}, "list_permissions": {},
    "list_components": {"kind": ("enum", KIND_ALIASES), "exported_only": ("bool",)},
    "search_apk_strings": {"query": ("str", 80, True), "limit": ("int", 1, 100)},
    "list_classes": {"query": ("str", 80, False), "limit": ("int", 1, 100)},
    "inspect_class": {"name": ("str", 200, True)},
    "inspect_method": {"class": ("str", 200, True), "method": ("str", 100, True)},
    "search_code": {"query": ("str", 80, True)},
    "inspect_dependencies": {}, "inspect_network_references": {}, "summarize_apk": {},
    "answer_apk_question": {"question": ("str", 500, True)},
}


def validate_call(name, args):
    """Check a tool request (for example from Gemma). Raises ToolError on anything unexpected."""
    if not isinstance(name, str) or name not in TOOLS:
        raise ToolError("Unknown tool. Allowed: " + ", ".join(sorted(TOOLS)))
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ToolError("Arguments must be a JSON object.")
    spec = TOOLS[name]
    clean = {}
    for k, v in args.items():
        if k not in spec:
            raise ToolError("Unexpected argument '%s' for %s." % (str(k)[:30], name))
        s = spec[k]
        if s[0] == "str":
            if not isinstance(v, str):
                raise ToolError("'%s' must be text." % k)
            v = v.strip()
            if len(v) > s[1]:
                raise ToolError("'%s' is too long (max %d)." % (k, s[1]))
            if any(ord(c) < 32 for c in v):
                raise ToolError("'%s' has control characters." % k)
            clean[k] = v
        elif s[0] == "int":
            if isinstance(v, bool) or not isinstance(v, int):
                raise ToolError("'%s' must be a whole number." % k)
            clean[k] = max(s[1], min(s[2], v))
        elif s[0] == "bool":
            if not isinstance(v, bool):
                raise ToolError("'%s' must be true or false." % k)
            clean[k] = v
        elif s[0] == "enum":
            key = str(v).lower().strip()
            if key not in s[1]:
                raise ToolError("'%s' must be one of: %s" % (k, ", ".join(sorted(set(s[1].values())))))
            clean[k] = s[1][key]
    for k, s in spec.items():
        if s[0] == "str" and s[2] and not clean.get(k):
            raise ToolError("'%s' is required for %s." % (k, name))
    return clean


def run_tool(ws, name, args):
    args = validate_call(name, args)
    if name == "answer_apk_question":
        raise ToolError("answer_apk_question is handled by RAMBO AI itself (it asks the model).")
    if not ws or not os.path.isdir(ws):
        raise ToolError("No analyzed APK. Use: apk pick")
    return _TOOL_FN[name](ws, args)


def build_report(info):
    """Full text report with evidence and limits. Plain text, safe to show or save."""
    i = info
    out = ["APK ANALYSIS REPORT", "=" * 20,
           "File: %s  (%d KB)" % (i.get("file_name"), i["size"] // 1024),
           "SHA-256: %s" % i["sha256"], "Type: %s" % ("split bundle" if i["archive"] == "bundle" else "APK"),
           "", "1. BASIC INFORMATION", "-" * 20]
    ws = i.get("ws", "")
    out.append(t_manifest(ws, {}))
    out += ["", "2. PERMISSIONS", "-" * 20, t_permissions(ws, {})]
    sens = [p for p in i["permissions"] if p.split(".")[-1] in DANGEROUS]
    if sens:
        out.append("PRIVACY NOTE: sensitive access requested: " + ", ".join(p.split(".")[-1] for p in sens[:12]))
    out += ["", "3. COMPONENTS", "-" * 20, t_components(ws, {"kind": "all"})]
    out += ["", "4. CODE", "-" * 20, "%d dex file(s), %d classes, %d methods, %d strings." % (
        len([d for d in i.get("dex", []) if not d.get("skipped")]), i.get("n_classes", 0),
        i.get("n_methods", 0), i.get("n_strings", 0))]
    if i.get("auth_classes"):
        out.append("Classes with auth-related names (name match only):")
        out += ["  " + c for c in i["auth_classes"][:15]]
    out += ["", "5. LIBRARIES AND FRAMEWORKS", "-" * 20, t_deps(ws, {})]
    out += ["", "6. NETWORK", "-" * 20, t_network(ws, {})]
    out += ["", "7. SECURITY OBSERVATIONS", "-" * 20]
    obs = []
    if i.get("debuggable"):
        obs.append("CONFIRMED: android:debuggable is true.")
    if i.get("allow_backup") is not False:
        obs.append("CONFIRMED: app data backup is not disabled (allowBackup is %s)." % _yn(i.get("allow_backup")))
    if i.get("cleartext"):
        obs.append("CONFIRMED: manifest allows cleartext HTTP traffic.")
    expo = [c["name"] for k in KINDS for c in i["components"][k] if c["effective_exported"] and not c.get("permission")]
    if expo:
        obs.append("CONFIRMED: %d exported component(s) with no permission requirement "
                   "(the launcher activity is normal): %s" % (len(expo), ", ".join(expo[:6])))
    if i.get("secrets"):
        obs.append("CONFIRMED: %d string(s) look like secrets/keys (values hidden): %s" % (
            len(i["secrets"]), ", ".join(i["secrets"][:5])))
    http = [u for u in i.get("urls", []) if u.startswith("http://")]
    if http:
        obs.append("CONFIRMED: %d plain http:// URL(s) in strings." % len(http))
    if "Dynamic code loading" in i.get("signals", []):
        obs.append("HYPOTHESIS: loads code at runtime (DexClassLoader referenced); check what it loads.")
    if "Package installer" in i.get("signals", []) or any(p.endswith("REQUEST_INSTALL_PACKAGES") for p in i["permissions"]):
        obs.append("HYPOTHESIS: can install other apps.")
    if i.get("obfuscation", 0) >= 0.2:
        obs.append("CONFIRMED: class names are partly or heavily obfuscated.")
    out += obs or ["No obvious issues found in the data this tool can read. That does not prove the app is safe."]
    out += ["", "8. LIMITATIONS", "-" * 20] + ["- " + l for l in i.get("limits", [])]
    out += ["", "Everything above comes from reading the APK file only. Nothing was run."]
    return "\n".join(out)


def delete_workspace(root, ws=None):
    """Delete one analysis folder, or all of them. Only touches folders inside root."""
    root = os.path.realpath(root)
    if ws is None:
        shutil.rmtree(root, ignore_errors=True)
        return
    real = os.path.realpath(ws)
    if os.path.dirname(real) != root:
        raise ToolError("Refusing to delete outside the APK workspace.")
    shutil.rmtree(real, ignore_errors=True)
