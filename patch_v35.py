#!/usr/bin/env python3
# patch_v35.py - hold button opens a see-through "Listening..." overlay with instant speech
# Run from ~/BusinessDashboard AFTER v34:  python patch_v35.py
# Backs up main.py, buildozer.spec, manifest_service.xml. Aborts if an anchor is missing.
import os, re, sys, shutil, py_compile

ROOT = os.getcwd()
MAIN = os.path.join(ROOT, "main.py")
SPEC = os.path.join(ROOT, "buildozer.spec")
MANI = os.path.join(ROOT, "manifest_service.xml")
IFIL = os.path.join(ROOT, "intent_filters.xml")


def die(msg):
    print("STOPPED: " + msg)
    sys.exit(1)


for p in (MAIN, SPEC, MANI):
    if not os.path.exists(p):
        die("run this from ~/BusinessDashboard (missing " + os.path.basename(p) + ")")

main = open(MAIN).read()
spec = open(SPEC).read()
mani = open(MANI).read()

if "AssistOverlayActivity" in mani or "_rambo_assist_hook" in main:
    die("patch v35 already applied")
if "def web_search" not in main:
    die("apply patch_v33.py and patch_v34.py first")

A_AUTO = ('        if self.cfg.get("auto"):\n'
          '            Clock.schedule_once(lambda dt: self.on_mic(None), 2.5)\n')
A_PAUSE = "    def on_pause(self):\n        return True\n"
for name, a in (("auto mic block", A_AUTO), ("on_pause", A_PAUSE)):
    if main.count(a) != 1:
        die("anchor missing or not unique in main.py: " + name)

PY_METHODS = r'''    # ---------- hold-button overlay hands us what you said ----------

    def _rambo_say_check(self, intent):
        try:
            if intent is None:
                return False
            txt = intent.getStringExtra("rambo_say")
            if not txt:
                return False
            txt = str(txt).strip()
            try:
                ts = int(intent.getLongExtra("rambo_ts", 0))
            except Exception:
                ts = 0
            try:
                intent.removeExtra("rambo_say")
            except Exception:
                pass
            if ts and abs(time.time() * 1000 - ts) > 60000:
                return False
            if txt == getattr(self, "_rs_last", None) and time.time() - getattr(self, "_rs_t", 0) < 5:
                return False
            self._rs_last, self._rs_t = txt, time.time()
            Clock.schedule_once(lambda dt: self.handle(txt, True), 0.6)
            return True
        except Exception as e:
            self.err("assist say", e)
            return False

    def _rambo_assist_hook(self):
        try:
            from jnius import autoclass
            from android import activity
            PA = autoclass("org.kivy.android.PythonActivity")
            activity.bind(on_new_intent=self._rambo_say_check)
            return self._rambo_say_check(PA.mActivity.getIntent())
        except Exception as e:
            self.err("assist hook", e)
            return False

'''

JAVA = r'''package org.rambo.acc;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.ArrayList;

public class AssistOverlayActivity extends Activity {
    private static final int REQ_MIC = 77;
    private SpeechRecognizer sr = null;
    private TextView status;
    private TextView heard;
    private boolean sent = false;

    private int dp(int v) {
        return (int) (v * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.argb(90, 0, 0, 0));
        root.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                finish();
            }
        });

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(20), dp(20), dp(20), dp(20));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.parseColor("#F2101820"));
        bg.setCornerRadius(dp(28));
        bg.setStroke(dp(1), Color.parseColor("#FF2BD9FF"));
        card.setBackground(bg);
        card.setClickable(true);

        TextView title = new TextView(this);
        title.setText("RAMBO AI");
        title.setTextColor(Color.parseColor("#FF2BD9FF"));
        title.setTextSize(14);
        card.addView(title);

        status = new TextView(this);
        status.setText("Listening...");
        status.setTextColor(Color.WHITE);
        status.setTextSize(22);
        status.setPadding(0, dp(8), 0, dp(4));
        card.addView(status);

        heard = new TextView(this);
        heard.setText("");
        heard.setTextColor(Color.parseColor("#FFBBBBBB"));
        heard.setTextSize(16);
        card.addView(heard);

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setPadding(0, dp(14), 0, 0);

        Button talk = new Button(this);
        talk.setText("Tap to talk");
        talk.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                sent = false;
                startListening();
            }
        });
        row.addView(talk, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        Button open = new Button(this);
        open.setText("Open app");
        open.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                openMain("");
            }
        });
        row.addView(open, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        card.addView(row);

        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.gravity = Gravity.BOTTOM;
        lp.setMargins(dp(12), dp(12), dp(12), dp(24));
        root.addView(card, lp);
        setContentView(root);
        startListening();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        sent = false;
        startListening();
    }

    @Override
    protected void onUserLeaveHint() {
        super.onUserLeaveHint();
        finish();
    }

    private void startListening() {
        try {
            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                status.setText("Allow the microphone");
                requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_MIC);
                return;
            }
            if (!SpeechRecognizer.isRecognitionAvailable(this)) {
                status.setText("No speech service on this phone");
                return;
            }
            if (sr == null) {
                sr = SpeechRecognizer.createSpeechRecognizer(this);
                sr.setRecognitionListener(new RecognitionListener() {
                    @Override
                    public void onReadyForSpeech(Bundle p) {
                        status.setText("Listening...");
                    }

                    @Override
                    public void onBeginningOfSpeech() {
                    }

                    @Override
                    public void onRmsChanged(float rms) {
                    }

                    @Override
                    public void onBufferReceived(byte[] buf) {
                    }

                    @Override
                    public void onEndOfSpeech() {
                    }

                    @Override
                    public void onError(int error) {
                        if (sent) {
                            return;
                        }
                        if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) {
                            status.setText("Allow the microphone");
                            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_MIC);
                        } else {
                            status.setText("Didn't catch that. Tap to talk.");
                        }
                    }

                    @Override
                    public void onResults(Bundle r) {
                        ArrayList<String> list = r.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                        if (list != null && list.size() > 0 && list.get(0) != null) {
                            send(list.get(0));
                        } else {
                            status.setText("Didn't catch that. Tap to talk.");
                        }
                    }

                    @Override
                    public void onPartialResults(Bundle p) {
                        ArrayList<String> list = p.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                        if (list != null && list.size() > 0 && list.get(0) != null) {
                            heard.setText(list.get(0));
                        }
                    }

                    @Override
                    public void onEvent(int type, Bundle p) {
                    }
                });
            }
            Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            i.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
            i.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
            status.setText("Listening...");
            heard.setText("");
            sr.startListening(i);
        } catch (Exception e) {
            status.setText("Mic error. Tap to talk.");
        }
    }

    private void send(String text) {
        if (sent) {
            return;
        }
        sent = true;
        heard.setText(text);
        status.setText("On it...");
        openMain(text);
    }

    private void openMain(String text) {
        try {
            Intent li = getPackageManager().getLaunchIntentForPackage(getPackageName());
            if (li != null) {
                if (text != null && text.length() > 0) {
                    li.putExtra("rambo_say", text);
                    li.putExtra("rambo_ts", System.currentTimeMillis());
                }
                li.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
                startActivity(li);
            }
        } catch (Exception e) {
        }
        finish();
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] results) {
        super.onRequestPermissionsResult(code, perms, results);
        if (code == REQ_MIC) {
            if (results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) {
                startListening();
            } else {
                status.setText("Microphone is off. Allow it in app settings.");
            }
        }
    }

    @Override
    protected void onDestroy() {
        try {
            if (sr != null) {
                sr.destroy();
            }
        } catch (Exception e) {
        }
        sr = null;
        super.onDestroy();
    }
}
'''

ACTIVITY_XML = ('<activity android:name="org.rambo.acc.AssistOverlayActivity"\n'
                '    android:theme="@android:style/Theme.Translucent.NoTitleBar"\n'
                '    android:exported="true"\n'
                '    android:excludeFromRecents="true"\n'
                '    android:taskAffinity=""\n'
                '    android:launchMode="singleTask">\n'
                '    <intent-filter>\n'
                '        <action android:name="android.intent.action.ASSIST" />\n'
                '        <category android:name="android.intent.category.DEFAULT" />\n'
                '    </intent-filter>\n'
                '</activity>\n')

# ---------------- apply ----------------
for p in (MAIN, SPEC, MANI):
    shutil.copy(p, p + ".bak35p")
if os.path.exists(IFIL):
    shutil.copy(IFIL, IFIL + ".bak35p")

new = main.replace(
    A_AUTO,
    '        said_now = self._rambo_assist_hook()\n'
    '        if self.cfg.get("auto") and not said_now:\n'
    '            Clock.schedule_once(lambda dt: self.on_mic(None), 2.5)\n', 1)
new = new.replace(A_PAUSE, PY_METHODS + A_PAUSE, 1)
with open(MAIN, "w") as f:
    f.write(new)
try:
    py_compile.compile(MAIN, doraise=True, cfile="_main_check.pyc")
except Exception as e:
    shutil.copy(MAIN + ".bak35p", MAIN)
    die("main.py failed to compile, restored backup: " + str(e)[:300])
try:
    os.remove("_main_check.pyc")
except Exception:
    pass

os.makedirs(os.path.join(ROOT, "java/org/rambo/acc"), exist_ok=True)
with open(os.path.join(ROOT, "java/org/rambo/acc/AssistOverlayActivity.java"), "w") as f:
    f.write(JAVA)

with open(MANI, "w") as f:
    f.write(mani.rstrip("\n") + "\n" + ACTIVITY_XML)

# the old ASSIST filter on the main screen must go, or Android may pick it instead
new_spec = re.sub(r"^android\.manifest\.intent_filters\s*=.*\n?", "", spec, flags=re.M)
if new_spec != spec:
    with open(SPEC, "w") as f:
        f.write(new_spec)

print("OK_PATCHED_V35")
print("Backups: main.py.bak35p, buildozer.spec.bak35p, manifest_service.xml.bak35p")
print("New file: java/org/rambo/acc/AssistOverlayActivity.java")
print("Removed old assist filter line from buildozer.spec")
