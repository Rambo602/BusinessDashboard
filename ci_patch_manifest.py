import glob, sys
svc = open("manifest_services_only.xml").read()
files = glob.glob("p4a-src/**/AndroidManifest.tmpl.xml", recursive=True)
n = 0
for f in files:
    t = open(f).read()
    if "RamboAccService" in t:
        n += 1
        continue
    if "</application>" not in t:
        continue
    open(f, "w").write(t.replace("</application>", svc + "\n</application>", 1))
    n += 1
print("patched", n, "of", len(files), "templates")
sys.exit(0 if n else 1)
