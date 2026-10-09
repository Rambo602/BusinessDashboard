# patch_v44: fixes the + button (now bottom right, left of MIC), adds the APK Analyzer
# (static analysis, nothing is installed or run), and lets AUTO RUN read and tap the screen
# through Accessibility. Bundles apkscan.py. Backup: main.py.bak44. Run inside ~/BusinessDashboard.
import os, sys, shutil, py_compile, base64, zlib, hashlib

F = "main.py"
if not os.path.exists(F):
    sys.exit("STOPPED: main.py not found (run this inside ~/BusinessDashboard)")
src = open(F, encoding="utf-8").read()
if "_pick_file" in src and "apk_route" in src:
    sys.exit("Already patched (v44). Nothing to do.")

# if the first + button patch (v43) is in, go back to the file as it was before it
if "on_attach_result" in src:
    if not os.path.exists(F + ".bak43"):
        sys.exit("STOPPED: v43 is applied but main.py.bak43 is missing, so I cannot undo it safely.")
    src = open(F + ".bak43", encoding="utf-8").read()
    print("Replaced the old + button patch (v43).")
if not os.path.exists(F + ".bak44"):
    shutil.copy(F, F + ".bak44")

APKSCAN_B64 = "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"
APKSCAN_SHA = "3789da847e7bdd9d4326253fbf5c988cded5fa7b0a664552ca5b1b44401838b1"
mod = zlib.decompress(base64.b64decode(APKSCAN_B64))
if hashlib.sha256(mod).hexdigest() != APKSCAN_SHA:
    sys.exit("STOPPED: bundled apkscan.py is damaged. Download patch_v44.py again.")


def swap(s, old, new, label):
    if s.count(old) != 1:
        raise Exception("anchor not unique or missing: " + label + " (%d)" % s.count(old))
    return s.replace(old, new, 1)


METHODS = r'''    # ---------- + button: attach a file (APK files go to the APK Analyzer) ----------

    ATTACH_MAX = 15 * 1024 * 1024
    APK_EXT = (".apk", ".apks", ".xapk", ".apkm")
    APK_HELP = ("APK Analyzer. It only reads APK files. It never installs or runs them.\n"
                "apk pick (or tap + and choose an APK)\n"
                "apk summary | manifest | permissions | components [exported]\n"
                "apk strings TEXT | classes TEXT | class NAME | method CLASS METHOD\n"
                "apk search TEXT | deps | network | files TEXT | file PATH\n"
                "apk report | apk report save\n"
                "apk ask YOUR QUESTION (Gemma answers from the extracted evidence)\n"
                "apk cloud on / off (lets Gemini help, and shows what would be sent)\n"
                "apk limit MB | apk cancel | apk delete | apk delete all | apk jadx")
    APK_SYS = ("You are RAMBO AI's APK analysis assistant. You get EVIDENCE from static analysis of an "
               "Android APK: manifest data, class and method names, strings, URLs, libraries. Rules: "
               "use only the evidence. Name the class, string, permission or file behind every technical "
               "claim. Label claims CONFIRMED (directly in the evidence) or HYPOTHESIS (inferred). If the "
               "evidence is not enough, say: Cannot be determined from the evidence, and say what to look "
               "at next. Method bodies are NOT decompiled, so never claim to know what a method does "
               "internally. If you need more data, reply with ONLY a JSON object such as "
               "{\"tool\":\"search_code\",\"args\":{\"query\":\"login\"}}. Allowed tools: "
               "inspect_apk_manifest, list_permissions, list_components, search_apk_strings, list_classes, "
               "inspect_class, inspect_method, search_code, inspect_dependencies, "
               "inspect_network_references, summarize_apk. Otherwise answer in plain text, short, for a "
               "phone screen. If asked to write code, write your own original implementation of the "
               "behavior and say it is not the app's source code.")

    def on_attach(self, instance):
        self.flash("Pick a file to attach")
        self._pick_file("attach")

    def on_apk_pick(self):
        self._pick_file("apk")

    def _pick_file(self, mode):
        try:
            from jnius import autoclass
            from android import activity
            PA = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            i = Intent(Intent.ACTION_OPEN_DOCUMENT)
            i.addCategory(Intent.CATEGORY_OPENABLE)
            i.setType("*/*")
            self._pick_mode = mode
            activity.unbind(on_activity_result=self.on_attach_result)
            activity.bind(on_activity_result=self.on_attach_result)
            PA.mActivity.startActivityForResult(i, 4343)
            return True
        except Exception as e:
            self.err("file picker", e)
            self.add_msg("Could not open the file picker: " + str(e)[:160], False)
            return False

    def on_attach_result(self, request, result, data):
        if request != 4343:
            return
        if result != -1 or data is None:
            return
        try:
            uri = data.getData()
        except Exception as e:
            Clock.schedule_once(lambda dt: self.err("attach result", e), 0)
            return
        if uri is None:
            return
        mode = getattr(self, "_pick_mode", "attach")
        threading.Thread(target=self._attach_read, args=(uri, mode), daemon=True).start()

    def _say(self, text):
        Clock.schedule_once(lambda dt: self.add_msg(text, False), 0)

    def _prog(self, text):
        Clock.schedule_once(lambda dt: self.flash(text), 0)

    def _attach_read(self, uri, mode):
        name, mime, err, fd = "file", "", "", None
        try:
            from jnius import autoclass
            PA = autoclass("org.kivy.android.PythonActivity")
            res = PA.mActivity.getContentResolver()
            try:
                mime = str(res.getType(uri) or "")
            except Exception:
                pass
            try:
                cur = res.query(uri, None, None, None, None)
                if cur is not None:
                    try:
                        if cur.moveToFirst():
                            ix = cur.getColumnIndex("_display_name")
                            if ix >= 0:
                                name = str(cur.getString(ix))
                    finally:
                        cur.close()
            except Exception:
                pass
            pfd = res.openFileDescriptor(uri, "r")
            fd = pfd.detachFd()
        except Exception as e:
            err = str(e)[:150]
        if fd is None:
            self._say("Could not open that file. " + err)
            return
        low = name.lower()
        if mode == "apk" or low.endswith(self.APK_EXT) or mime == "application/vnd.android.package-archive":
            self._apk_import(fd, name)
            return
        raw = b""
        try:
            with os.fdopen(fd, "rb") as f:
                raw = f.read(self.ATTACH_MAX + 1)
        except Exception as e:
            err = str(e)[:150]
        Clock.schedule_once(lambda dt: self._attach_done(name, mime, raw, err), 0)

    def _attach_done(self, name, mime, raw, err):
        import base64
        import mimetypes
        if err or not raw:
            self.add_msg("Could not read that file. " + err, False)
            return
        if len(raw) > self.ATTACH_MAX:
            self.add_msg("That file is over 15 MB. Pick a smaller one.", False)
            return
        if mime in ("", "application/octet-stream"):
            mime = mimetypes.guess_type(name)[0] or mime
        parts = None
        if mime.startswith(("image/", "audio/")) or mime == "application/pdf":
            parts = [{"inline_data": {"mime_type": mime,
                                      "data": base64.b64encode(raw).decode()}}]
        else:
            try:
                t = raw.decode("utf-8")
                if "\x00" in t[:2000]:
                    raise ValueError("binary")
                parts = [{"text": "File " + name + ":\n" + t[:120000]}]
            except Exception:
                parts = None
        if parts is None:
            self.add_msg("I can read text, PDF, image and audio files. That one looks like "
                         + (mime or "an unknown type") + ".", False)
            return
        self.attach = {"name": name, "parts": parts}
        kb = max(1, len(raw) // 1024)
        self.add_msg("Attached: " + name + " (" + str(kb) + " KB). Type your question and "
                     "press SEND, or just press SEND to get a summary. Tap + to pick a different file.", False)

    def _send_attach(self, text):
        att = self.attach
        self.attach = None
        if not text:
            text = "Summarize this file."
        shown = text + "\n(file: " + att["name"] + ")"
        self.add_msg(shown, True)
        self.hide_chips()
        try:
            self.db.add_chat("user", shown)
        except Exception as e:
            self.err("chat save", e)
        self.hist.append(("user", text))
        self.hist = self.hist[-12:]
        self._att_once = att["parts"]
        try:
            self._ask_cloud(text)
        finally:
            self._att_once = None

    # ---------- APK Analyzer (static: reads the file, never runs or installs it) ----------

    def _apk_root(self):
        p = os.path.join(self.user_data_dir, "apk_ws")
        os.makedirs(p, exist_ok=True)
        return p

    def _apk_ws(self):
        root = os.path.realpath(self._apk_root())
        ws = getattr(self, "apk_cur", None)
        if not ws:
            try:
                ws = open(os.path.join(root, "current.txt")).read().strip()
            except Exception:
                ws = None
        if ws and os.path.dirname(os.path.realpath(ws)) == root and os.path.isfile(os.path.join(ws, "info.json")):
            self.apk_cur = ws
            return ws
        return None

    def _apk_import(self, fd, name):
        import shutil
        import apkscan
        if getattr(self, "apk_busy", False):
            try:
                os.close(fd)
            except Exception:
                pass
            self._say("An APK is already being analyzed. Say: apk cancel")
            return
        self.apk_cancel = False
        self.apk_busy = True
        root = self._apk_root()
        inc = os.path.join(root, "incoming.part")
        try:
            limit = int(self.cfg.get("apk_max_mb", 600)) << 20
            free = shutil.disk_usage(root).free
            if free < 200 * 1024 * 1024:
                raise apkscan.ApkError("Less than 200 MB of free storage. Free some space first.")
            self._say("Importing " + name + ". It is only read, never installed or run.")
            with os.fdopen(fd, "rb") as f:
                apkscan.copy_stream(f, inc, limit, lambda: self.apk_cancel,
                                    lambda n: self._prog("Copied %d MB" % (n >> 20)))
            if free < 2 * os.path.getsize(inc) + 100 * 1024 * 1024:
                raise apkscan.ApkError("Not enough free storage to analyze this file.")
            info = apkscan.analyze(inc, root, name, self._prog, lambda: self.apk_cancel, limit)
            ws = info["ws"]
            self.apk_cur = ws
            try:
                open(os.path.join(root, "current.txt"), "w").write(ws)
            except Exception:
                pass
            head = ("APK analyzed" + (" (from cache)" if info.get("cached") else "") + "\n"
                    + "File: " + str(info.get("file_name")) + "\n"
                    + "Size: %d KB\n" % (info["size"] // 1024)
                    + "SHA-256: " + info["sha256"] + "\n"
                    + "Type: " + ("split bundle, base APK analyzed" if info["archive"] == "bundle" else "APK") + "\n\n")
            self._say(head + apkscan.run_tool(ws, "summarize_apk", {})
                      + "\n\nNext: apk report | apk permissions | apk ask <question> | apk help")
        except apkscan.Cancelled:
            self._say("Analysis cancelled. Partial files were removed.")
        except apkscan.ApkError as e:
            self._say("Could not analyze this file: " + str(e))
        except MemoryError:
            self._say("Ran out of memory. Try: apk limit 200, or analyze on a computer.")
        except Exception as e:
            self.err("apk import", e)
            self._say("APK analysis failed: " + str(e)[:200])
        finally:
            self.apk_busy = False
            try:
                if os.path.exists(inc):
                    os.remove(inc)
            except Exception:
                pass

    def _apk_async(self, fn, label):
        def work():
            try:
                out = fn()
            except Exception as e:
                if e.__class__.__name__ not in ("ToolError", "ApkError"):
                    self.err("apk tool", e)
                out = "APK tool: " + str(e)[:300]
            self._say(out)
        threading.Thread(target=work, daemon=True).start()
        return label

    def _save_download(self, fname, data, mime):
        from jnius import autoclass
        PA = autoclass("org.kivy.android.PythonActivity")
        ContentValues = autoclass("android.content.ContentValues")
        Downloads = autoclass("android.provider.MediaStore$Downloads")
        cr = PA.mActivity.getContentResolver()
        cv = ContentValues()
        cv.put("_display_name", fname)
        cv.put("mime_type", mime)
        cv.put("relative_path", "Download")
        uri = cr.insert(Downloads.EXTERNAL_CONTENT_URI, cv)
        out = cr.openOutputStream(uri)
        out.write(data, 0, len(data))
        out.close()

    def apk_route(self, text, low):
        if not (low == "apk" or low.startswith("apk ")
                or low.startswith(("analyze apk", "analyse apk", "inspect apk"))):
            return None
        try:
            import apkscan
        except Exception as e:
            self.err("apk import", e)
            return "The APK Analyzer file (apkscan.py) is not in this build."
        if not low.startswith("apk"):
            self.on_apk_pick()
            return "Choose the APK in the file picker. It is only read, never installed or run."
        rest = text[3:].strip()
        sub = rest.split(" ", 1)[0].lower() if rest else ""
        arg = rest.split(" ", 1)[1].strip() if " " in rest else ""
        ws = self._apk_ws()
        if sub in ("", "help"):
            self.add_msg(self.APK_HELP, False)
            return "APK Analyzer help is above."
        if sub in ("pick", "import", "open", "load"):
            self.on_apk_pick()
            return "Choose the APK in the file picker. It is only read, never installed or run."
        if sub == "cancel":
            self.apk_cancel = True
            return "Cancelling. Partial files will be removed."
        if sub == "limit":
            if arg.isdigit() and 20 <= int(arg) <= 2000:
                self.cfg["apk_max_mb"] = int(arg)
                return "APK size limit set to %s MB until the app restarts." % arg
            return "Use: apk limit 300 (between 20 and 2000 MB). Now: %s MB." % self.cfg.get("apk_max_mb", 600)
        if sub == "jadx":
            self.add_msg("JADX and Apktool need Java, so they cannot run inside this app. "
                         "In Termux you can try: pkg install openjdk-17, download JADX from "
                         "github.com/skylot/jadx/releases, then: jadx -d out file.apk. I have not "
                         "tested that on your phone. The built-in analysis (apk summary, apk class ...) "
                         "needs no Java.", False)
            return "JADX notes are above."
        if sub == "cloud":
            if arg.lower() in ("on", "yes", "enable"):
                self.cfg["apk_cloud"] = True
                return ("Cloud help is ON for this session. When local Gemma cannot answer, Gemini gets your "
                        "question plus up to ~7000 characters of APK findings (class and method names, strings, "
                        "URLs, permissions). Not sent: the APK file, certificates, other files. Secret-looking "
                        "values and emails are removed. You will see what is sent each time.")
            if arg.lower() in ("off", "no", "disable"):
                self.cfg["apk_cloud"] = False
                return "Cloud help is OFF. Everything stays on the phone."
            return "Cloud help is %s. Use: apk cloud on / off" % ("ON" if self.cfg.get("apk_cloud") else "OFF")
        if sub == "delete":
            root = self._apk_root()
            try:
                if arg.lower() == "all":
                    apkscan.delete_workspace(root)
                    self.apk_cur = None
                    return "All APK analysis data deleted."
                if not ws:
                    return "No APK is loaded."
                apkscan.delete_workspace(root, ws)
                self.apk_cur = None
                return "Deleted the analysis of the current APK."
            except Exception as e:
                self.err("apk delete", e)
                return "Could not delete: " + str(e)[:120]
        if sub == "status":
            if not ws:
                return "No APK loaded. Use: apk pick"
            i = apkscan.load_info(ws)
            return "Loaded: %s v%s (%d KB)" % (i["package"], i.get("version_name"), i["size"] // 1024)
        if not ws:
            return "No APK loaded yet. Use: apk pick, or tap + and choose an APK."
        if sub == "report":
            save = arg.lower() == "save"

            def rep():
                i = apkscan.load_info(ws)
                i["ws"] = ws
                body = apkscan.build_report(i)
                if save:
                    fname = "RAMBO_apk_report_" + i["package"] + ".txt"
                    self._save_download(fname, body.encode("utf-8"), "text/plain")
                    return "Report saved to Downloads as " + fname
                return body
            return self._apk_async(rep, "Building the report...")
        if sub == "ask":
            if not arg:
                return "Use: apk ask <your question>"
            return self._apk_ask(arg)
        if sub == "tool":
            def tool():
                try:
                    req = json.loads(arg)
                except Exception:
                    raise apkscan.ToolError("Tool request must be JSON, like {\"tool\":\"list_permissions\",\"args\":{}}")
                if not isinstance(req, dict):
                    raise apkscan.ToolError("Tool request must be a JSON object.")
                return apkscan.run_tool(ws, req.get("tool"), req.get("args"))
            return self._apk_async(tool, "Running tool...")
        table = {"summary": ("summarize_apk", {}), "manifest": ("inspect_apk_manifest", {}),
                 "permissions": ("list_permissions", {}), "perms": ("list_permissions", {}),
                 "deps": ("inspect_dependencies", {}), "libs": ("inspect_dependencies", {}),
                 "network": ("inspect_network_references", {}), "net": ("inspect_network_references", {}),
                 "urls": ("inspect_network_references", {})}
        call = None
        if sub in table:
            call = table[sub]
        elif sub in ("components", "comps"):
            call = ("list_components", {"exported_only": True} if arg.lower().startswith("export") else {})
        elif sub == "strings" and arg:
            call = ("search_apk_strings", {"query": arg})
        elif sub == "classes":
            call = ("list_classes", {"query": arg})
        elif sub == "class" and arg:
            call = ("inspect_class", {"name": arg})
        elif sub == "method" and " " in arg:
            c, m = arg.split(" ", 1)
            call = ("inspect_method", {"class": c, "method": m.strip()})
        elif sub == "search" and arg:
            call = ("search_code", {"query": arg})
        if call is not None:
            return self._apk_async(lambda: apkscan.run_tool(ws, call[0], call[1]), "Looking...")
        if sub == "files":
            return self._apk_async(lambda: apkscan.t_files(ws, {"query": arg}), "Listing files...")
        if sub == "file" and arg:
            return self._apk_async(lambda: apkscan.read_file(ws, arg), "Reading the file...")
        return "Unknown APK command. Say: apk help"

    def _apk_evidence(self, ws, q):
        import apkscan
        ql = q.lower()
        parts = []
        done = set()

        def add(name, args=None):
            key = name + json.dumps(args or {}, sort_keys=True)
            if key in done:
                return
            done.add(key)
            try:
                parts.append("## " + name + (" " + json.dumps(args) if args else "") + "\n"
                             + apkscan.run_tool(ws, name, args or {}))
            except Exception:
                pass
        add("summarize_apk")
        if any(w in ql for w in ("permission", "privacy", "access", "risk", "security")):
            add("list_permissions")
        if any(w in ql for w in ("component", "activity", "service", "receiver", "provider", "export",
                                 "architecture", "how does", "how it works", "explain", "risk", "security")):
            add("list_components", {"exported_only": True} if "export" in ql or "risk" in ql or "security" in ql else {})
        if any(w in ql for w in ("network", "server", "api", "url", "http", "communicat", "endpoint",
                                 "login", "auth", "internet", "risk", "security")):
            add("inspect_network_references")
        if any(w in ql for w in ("librar", "depend", "framework", "built", "sdk", "explain", "store", "setting")):
            add("inspect_dependencies")
        if any(w in ql for w in ("login", "auth", "sign in", "signin", "account", "password")):
            add("search_code", {"query": "login"})
            add("search_code", {"query": "token"})
        if any(w in ql for w in ("setting", "stor", "save", "database", "prefs", "preference", "cache")):
            add("search_code", {"query": "prefs"})
            add("search_code", {"query": "database"})
        stop = ("this", "that", "with", "from", "what", "where", "which", "does", "explain", "find",
                "show", "code", "about", "have", "into", "their", "there", "responsible", "feature",
                "application", "work", "works", "help", "recreate", "generate", "implementation",
                "identify", "relevant", "available", "found", "please")
        for w in [w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_\.]{3,}", q) if w.lower() not in stop][:4]:
            if "." in w and w.count(".") >= 2:
                add("inspect_class", {"name": w})
            else:
                add("search_code", {"query": w})
        return "\n\n".join(parts)[:7000]

    def _apk_llm_local(self, sysm, user, ws):
        import apkscan
        for _round in range(3):
            txt = gemma_chat(sysm, user, max_tokens=600)
            t = txt.strip()
            if t.startswith("```"):
                t = t.strip("`").replace("json", "", 1).strip()
            if t.startswith("{") and t.endswith("}"):
                try:
                    req = json.loads(t)
                except Exception:
                    return txt
                if isinstance(req, dict) and "tool" in req:
                    try:
                        out = apkscan.run_tool(ws, req.get("tool"), req.get("args"))
                    except Exception as e:
                        out = "Tool refused: " + str(e)[:200]
                    user += "\n\n## TOOL RESULT " + json.dumps(req)[:200] + "\n" + out[:3000]
                    continue
            return txt
        return gemma_chat(sysm, user + "\n\nAnswer now with the evidence you have. Do not request more tools.", max_tokens=600)

    def _apk_ask(self, q):
        ws = self._apk_ws()
        if not ws:
            return "No APK loaded yet. Use: apk pick"

        def work():
            import apkscan
            ev = self._apk_evidence(ws, q)
            user = "QUESTION: " + q + "\n\nEVIDENCE FROM THE APK:\n" + ev
            ans = ""
            try:
                ans = self._apk_llm_local(self.APK_SYS, user, ws)
            except Exception as e:
                self.err("apk gemma", str(e)[:100])
                ans = ""
            if ans:
                self._say(ans)
                return
            if self.cfg.get("apk_cloud") and self.gem_ok():
                safe = apkscan.scrub(user)
                self._say("Local Gemma did not answer. Sending to Gemini: your question and %d characters "
                          "of APK findings (names, strings, URLs, permissions). Not sent: the APK file, "
                          "certificates or other files. Secret-looking values and emails were removed." % len(safe))
                body = json.dumps({"systemInstruction": {"parts": [{"text": self.APK_SYS}]},
                                   "contents": [{"role": "user", "parts": [{"text": safe}]}]}).encode()
                code, raw = gemini_try(self.gem_key(), body)
                if code == 200:
                    try:
                        self._say(json.loads(raw)["candidates"][0]["content"]["parts"][0]["text"].strip())
                        return
                    except Exception as e:
                        self.err("apk gemini parse", e)
                self._say("Gemini could not answer (code %s). Here is the evidence I found:\n\n%s" % (code, ev[:3000]))
                return
            self._say("Local Gemma did not answer (start it in Termux). To let Gemini help, say: apk cloud on. "
                      "It shows what is sent. Here is what I found in the APK:\n\n" + ev[:3000])
        threading.Thread(target=work, daemon=True).start()
        return "Looking through the APK..."

    # ---------- auto run: screen control through Accessibility ----------

    def _auto_acc_help(self):
        on = False
        try:
            from jnius import autoclass
            on = bool(autoclass("org.rambo.acc.RamboAccService").isOn())
        except Exception:
            on = False
        if not on:
            return " You cannot tap inside other apps (Accessibility is off, so do not use acc commands)."
        return (" You CAN control the phone screen with these commands: acc screen (reads the text on "
                "screen; the result shows in the log as WEB SCREEN on your next turn), acc tap TEXT "
                "(taps a visible button or label), acc type TEXT, acc scroll down, acc scroll up, "
                "acc back, acc home. After you open an app, use acc screen in your NEXT step, because "
                "the app needs time to load. Read the screen before you tap. Never tap or type anything "
                "about payments, purchases, deleting, uninstalling or passwords: use the question field "
                "and ask the user instead.")

    def _auto_acc(self, pid, cm):
        body = cm.strip()[4:].strip().lower()
        ok = body in ("screen", "back", "home", "paste", "scroll down", "scroll up") or \
            body.startswith(("tap ", "type ", "clip "))
        if not ok:
            self.db.add_plog(pid, "run", cm + " -> not allowed in auto run")
            return
        risky = ("pay", "buy", "purchase", "checkout", "place order", "order now", "delete",
                 "uninstall", "transfer", "send money", "factory reset", "erase", "subscribe",
                 "password", "passcode", "pin")
        if body.startswith(("tap ", "type ")) and any(w in body for w in risky):
            self.db.add_plog(pid, "ask", "I did not run '" + cm + "' because it could spend money, delete "
                             "something or touch a password. Tell me if you want me to do it.")
            self._auto_end(pid, "waiting", None)
            return
        short, full = self.acc_run(cm)
        if short.startswith(("Accessibility is OFF", "Accessibility code is not")):
            self.db.add_plog(pid, "ask", short + " Type: acc settings, turn it on, then tap AUTO RUN.")
            self._auto_end(pid, "waiting", None)
            return
        self.db.add_plog(pid, "run", cm + " -> " + short)
        if full:
            self.db.add_plog(pid, "run", "WEB SCREEN " + " | ".join(full.splitlines())[:1600])

'''

results = []
try:
    s = src
    # plus button: bottom right, left of MIC
    s = swap(s, '        mic = NeonButton(glow=GREEN, text="MIC", size_hint=(None, 1),\n',
             '        plus = NeonButton(glow=CYAN, text="+", size_hint=(None, 1),\n'
             '                          width=46, font_size="26sp")\n'
             '        plus.bind(on_press=self.on_attach)\n'
             '        pill.add_widget(plus)\n'
             '        mic = NeonButton(glow=GREEN, text="MIC", size_hint=(None, 1),\n', "pill")
    results.append("+ button (bottom right, left of MIC)")
    s = swap(s, '("My tasks", "show my tasks")):', '("My tasks", "show my tasks"),\n                           ("APK", "apk pick")):', "chips")
    results.append("APK chip")
    s = swap(s, "    # ---------- actions from buttons ----------\n",
             METHODS + "    # ---------- actions from buttons ----------\n", "methods")
    s = swap(s, "        self.convo_active = False\n        if text:\n            self.handle(text, False)\n\n    def on_mic(self, instance):",
             "        self.convo_active = False\n"
             "        if getattr(self, \"attach\", None):\n"
             "            self._send_attach(text)\n"
             "            return\n"
             "        if text:\n            self.handle(text, False)\n\n    def on_mic(self, instance):", "on_send")
    s = swap(s, "        payload = {\n            \"systemInstruction\": {\"parts\": [{\"text\": build_system(self.db.memories())}]},\n            \"contents\": contents,",
             "        ap = getattr(self, \"_att_once\", None)\n"
             "        if ap:\n"
             "            contents[-1] = {\"role\": \"user\", \"parts\": list(ap) + [{\"text\": text}]}\n"
             "        payload = {\n            \"systemInstruction\": {\"parts\": [{\"text\": build_system(self.db.memories())}]},\n            \"contents\": contents,", "cloud payload")
    results.append("file attach (text, PDF, image, audio -> Gemini)")
    s = swap(s, "        r_acc = self.acc_route(text, low)\n        if r_acc is not None:\n            return r_acc\n",
             "        try:\n            r_apk = self.apk_route(text, low)\n        except Exception as e:\n"
             "            self.err(\"apk route\", e)\n            r_apk = \"APK Analyzer error: \" + str(e)[:150]\n"
             "        if r_apk is not None:\n            return r_apk\n"
             "        r_acc = self.acc_route(text, low)\n        if r_acc is not None:\n            return r_acc\n", "route")
    results.append("APK Analyzer commands")
    # auto run screen control (optional: skipped if this main.py already has it or looks different)
    a1 = '"itself. Max 3 commands. You cannot tap inside other apps.")'
    a2 = "    def _auto_cmd(self, pid, cm):\n        try:\n            if cm.lower().startswith(\"play \"):"
    if s.count(a1) == 1 and s.count(a2) == 1:
        s = s.replace(a1, '"itself. Max 3 commands." + self._auto_acc_help())', 1)
        s = s.replace(a2, "    def _auto_cmd(self, pid, cm):\n        try:\n"
                      "            if cm.lower().startswith(\"acc \"):\n                self._auto_acc(pid, cm)\n                return\n"
                      "            if cm.lower().startswith(\"play \"):", 1)
        results.append("AUTO RUN screen control (acc screen / tap / type / scroll)")
    else:
        results.append("AUTO RUN screen control SKIPPED (this main.py already differs there)")
    open(F, "w", encoding="utf-8").write(s)
    py_compile.compile(F, doraise=True)
    open("apkscan.py", "wb").write(mod)
    py_compile.compile("apkscan.py", doraise=True)
except Exception as e:
    shutil.copy(F + ".bak44", F)
    sys.exit("STOPPED and rolled back: " + str(e))

spec = open("buildozer.spec", encoding="utf-8").read() if os.path.exists("buildozer.spec") else ""
import re as _re
m = _re.search(r"^source\.include_exts\s*=\s*(.*)$", spec, _re.M)
if m and "py" not in [x.strip() for x in m.group(1).split(",")]:
    print("WARNING: buildozer.spec source.include_exts has no 'py'. Add it, or apkscan.py will not be in the APK.")
print("PATCHED v44 OK:")
for r in results:
    print("  - " + r)
print("Created apkscan.py")
print("UNDO: cd ~/BusinessDashboard && cp main.py.bak44 main.py && rm apkscan.py")
