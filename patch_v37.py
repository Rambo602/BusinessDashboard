#!/usr/bin/env python3
# patch_v37.py - Gemini-style overlay when you hold the button. ADDS ONLY; hold button entry untouched.
# Run from ~/BusinessDashboard AFTER v36:  python patch_v37.py
# Undo: cp main.py.bak37p main.py && cp manifest_service.xml.bak37p manifest_service.xml && rm java/org/rambo/acc/AssistOverlayActivity.java
import os, re, sys, shutil, py_compile

ROOT = os.getcwd()
MAIN = os.path.join(ROOT, "main.py")
MANI = os.path.join(ROOT, "manifest_service.xml")
SPEC = os.path.join(ROOT, "buildozer.spec")
JPATH = os.path.join(ROOT, "java/org/rambo/acc/AssistOverlayActivity.java")


def die(msg):
    print("STOPPED: " + msg)
    sys.exit(1)


for p in (MAIN, MANI, SPEC):
    if not os.path.exists(p):
        die("run this from ~/BusinessDashboard (missing " + os.path.basename(p) + ")")
main, mani, spec = open(MAIN).read(), open(MANI).read(), open(SPEC).read()

if "def _rambo_overlay" in main or "AssistOverlayActivity" in mani:
    die("patch v37 already applied")
if "def _rambo_intent" not in main:
    die("apply patch_v36.py first")
if "AssistOverlayActivity" in mani or os.path.exists(JPATH):
    die("old overlay files still present; run patch_v36.py first")
if not re.search(r"^android\.manifest\.intent_filters", spec, re.M):
    die("assist entry missing from buildozer.spec; run patch_v36.py first")

A_MIC = "            Clock.schedule_once(lambda dt: self.on_mic(None), 0.5)\n            return True\n"
A_DEF = "    def _rambo_intent(self, intent):\n"
if main.count(A_MIC) != 1:
    die("anchor missing or not unique in main.py: assist mic line")
if main.count(A_DEF) != 1:
    die("anchor missing or not unique in main.py: _rambo_intent")

PY_NEW = r"""    def _rambo_overlay(self):
        # show the listening card over whatever app you were in; plain mic if anything fails
        try:
            from jnius import autoclass
            PA = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            act = PA.mActivity
            i = Intent()
            i.setClassName(act.getPackageName(), "org.rambo.acc.AssistOverlayActivity")
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | 0x00010000)
            act.startActivity(i)
            Clock.schedule_once(lambda dt: act.moveTaskToBack(True), 0.35)
        except Exception as e:
            self.err("overlay", e)
            try:
                self.on_mic(None)
            except Exception:
                pass

"""

JAVA = r"""package org.rambo.acc;

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
"""

ACTIVITY_XML = ('<activity android:name="org.rambo.acc.AssistOverlayActivity"\n'
                '    android:theme="@android:style/Theme.Translucent.NoTitleBar"\n'
                '    android:exported="false"\n'
                '    android:excludeFromRecents="true"\n'
                '    android:taskAffinity=""\n'
                '    android:launchMode="singleTask" />\n')

for p in (MAIN, MANI):
    shutil.copy(p, p + ".bak37p")

new = main.replace(A_MIC, "            Clock.schedule_once(lambda dt: self._rambo_overlay(), 0.2)\n            return True\n", 1)
new = new.replace(A_DEF, PY_NEW + A_DEF, 1)
open(MAIN, "w").write(new)
try:
    py_compile.compile(MAIN, doraise=True, cfile="_main_check.pyc")
except Exception as e:
    shutil.copy(MAIN + ".bak37p", MAIN)
    die("main.py failed to compile, restored backup: " + str(e)[:300])
try:
    os.remove("_main_check.pyc")
except Exception:
    pass

os.makedirs(os.path.dirname(JPATH), exist_ok=True)
open(JPATH, "w").write(JAVA)
open(MANI, "w").write(mani.rstrip("\n") + "\n" + ACTIVITY_XML)

print("OK_PATCHED_V37")
print("Hold-button entry untouched. Backups: main.py.bak37p, manifest_service.xml.bak37p")
