import io, json, os, re, zipfile
import urllib.request, urllib.error
REPO = "Rambo602/BusinessDashboard"


def cur_ver():
    try:
        from jnius import autoclass
        a = autoclass("org.kivy.android.PythonActivity").mActivity
        return str(a.getPackageManager().getPackageInfo(
            a.getPackageName(), 0).versionName)
    except Exception:
        return "unknown"


def install(apk, fname):
    from jnius import autoclass
    Intent = autoclass("android.content.Intent")
    CV = autoclass("android.content.ContentValues")
    DL = autoclass("android.provider.MediaStore$Downloads")
    a = autoclass("org.kivy.android.PythonActivity").mActivity
    mime = "application/vnd.android.package-archive"
    cr = a.getContentResolver()
    cv = CV()
    cv.put("_display_name", fname)
    cv.put("mime_type", mime)
    cv.put("relative_path", "Download")
    uri = cr.insert(DL.EXTERNAL_CONTENT_URI, cv)
    out = cr.openOutputStream(uri)
    for i in range(0, len(apk), 1 << 20):
        c = apk[i:i + (1 << 20)]
        out.write(c, 0, len(c))
    out.close()
    it = Intent(Intent.ACTION_VIEW)
    it.setDataAndType(uri, mime)
    it.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK)
    a.startActivity(it)


def run(tokfile, say):
    try:
        tok = open(tokfile).read().strip()
        h = {"Authorization": "Bearer " + tok, "User-Agent": "rambo-ai",
             "Accept": "application/vnd.github+json"}

        def get(u, hh, t):
            return urllib.request.urlopen(
                urllib.request.Request(u, headers=hh), timeout=t)

        say("Checking GitHub...")
        u = "https://api.github.com/repos/%s/actions/artifacts?per_page=30" % REPO
        arts = json.loads(get(u, h, 30).read().decode())["artifacts"]
        arts = [x for x in arts if not x.get("expired") and "apk" in x["name"].lower()]
        if not arts:
            return say("No APK build found.")
        say("Downloading newest build...")

        class NR(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None

        data = loc = None
        try:
            data = urllib.request.build_opener(NR).open(urllib.request.Request(
                arts[0]["archive_download_url"], headers=h), timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code not in (301, 302, 303, 307, 308):
                raise
            loc = e.headers["Location"]
        if loc:
            data = get(loc, {"User-Agent": "rambo-ai"}, 300).read()
        z = zipfile.ZipFile(io.BytesIO(data))
        n = [x for x in z.namelist() if x.endswith(".apk")][0]
        m = re.search(r"-(\d+(?:\.\d+)+)-", os.path.basename(n))
        new = tuple(int(x) for x in m.group(1).split("."))
        cs = cur_ver()
        try:
            cur = tuple(int(x) for x in cs.split("."))
        except Exception:
            cur = (0,)
        if new <= cur:
            return say("Up to date. Installed %s, latest %s." % (cs, m.group(1)))
        say("Opening installer for %s..." % m.group(1))
        install(z.read(n), os.path.basename(n))
        say("Installer opened. Tap Update.")
    except Exception as e:
        say("Update failed: %s" % e)
