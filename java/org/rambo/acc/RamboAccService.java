package org.rambo.acc;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Path;
import android.graphics.Rect;
import android.os.Bundle;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;
import java.util.ArrayList;
import java.util.List;

public class RamboAccService extends AccessibilityService {
    public static volatile RamboAccService inst = null;

    @Override
    protected void onServiceConnected() {
        inst = this;
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
    }

    @Override
    public void onInterrupt() {
    }

    @Override
    public boolean onUnbind(Intent intent) {
        inst = null;
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        inst = null;
        super.onDestroy();
    }

    public static boolean isOn() {
        return inst != null;
    }

    private static List<AccessibilityNodeInfo> roots() {
        List<AccessibilityNodeInfo> out = new ArrayList<AccessibilityNodeInfo>();
        RamboAccService s = inst;
        if (s == null) {
            return out;
        }
        try {
            AccessibilityNodeInfo r = s.getRootInActiveWindow();
            if (r != null) {
                out.add(r);
                return out;
            }
            List<AccessibilityWindowInfo> ws = s.getWindows();
            if (ws != null) {
                for (AccessibilityWindowInfo w : ws) {
                    AccessibilityNodeInfo n = w.getRoot();
                    if (n != null) {
                        out.add(n);
                    }
                }
            }
        } catch (Exception e) {
        }
        return out;
    }

    public static String currentPackage() {
        for (AccessibilityNodeInfo r : roots()) {
            CharSequence p = r.getPackageName();
            if (p != null) {
                return p.toString();
            }
        }
        return "";
    }

    public static String screenText() {
        StringBuilder sb = new StringBuilder();
        for (AccessibilityNodeInfo r : roots()) {
            dump(r, sb, 0);
        }
        return sb.toString();
    }

    private static void dump(AccessibilityNodeInfo n, StringBuilder sb, int depth) {
        if (n == null || sb.length() > 8000 || depth > 40) {
            return;
        }
        if (!n.isVisibleToUser()) {
            return;
        }
        String line = "";
        if (!n.isPassword()) {
            CharSequence t = n.getText();
            CharSequence d = n.getContentDescription();
            if (t != null && t.length() > 0) {
                line = t.toString();
            } else if (d != null && d.length() > 0) {
                line = d.toString();
            }
        }
        if (line.length() > 300) {
            line = line.substring(0, 300);
        }
        if (line.length() > 0) {
            String tag = n.isEditable() ? "[input] " : (n.isClickable() ? "[tap] " : "");
            sb.append(tag).append(line.replace("\n", " ")).append("\n");
        } else if (n.isEditable()) {
            sb.append("[input] (empty)\n");
        }
        int cnt = n.getChildCount();
        for (int i = 0; i < cnt; i++) {
            dump(n.getChild(i), sb, depth + 1);
        }
    }

    private static AccessibilityNodeInfo find(AccessibilityNodeInfo n, String q, boolean exact, int depth) {
        if (n == null || depth > 40) {
            return null;
        }
        String t = n.getText() == null ? "" : n.getText().toString().toLowerCase();
        String d = n.getContentDescription() == null ? "" : n.getContentDescription().toString().toLowerCase();
        boolean hit = exact ? (t.equals(q) || d.equals(q)) : (t.contains(q) || d.contains(q));
        if (hit && n.isVisibleToUser()) {
            return n;
        }
        int cnt = n.getChildCount();
        for (int i = 0; i < cnt; i++) {
            AccessibilityNodeInfo r = find(n.getChild(i), q, exact, depth + 1);
            if (r != null) {
                return r;
            }
        }
        return null;
    }

    private static AccessibilityNodeInfo firstEditable(AccessibilityNodeInfo n, int depth) {
        if (n == null || depth > 40) {
            return null;
        }
        if (n.isEditable() && n.isVisibleToUser()) {
            return n;
        }
        int cnt = n.getChildCount();
        for (int i = 0; i < cnt; i++) {
            AccessibilityNodeInfo r = firstEditable(n.getChild(i), depth + 1);
            if (r != null) {
                return r;
            }
        }
        return null;
    }

    private static AccessibilityNodeInfo findScrollable(AccessibilityNodeInfo n, int depth) {
        if (n == null || depth > 40) {
            return null;
        }
        if (n.isScrollable() && n.isVisibleToUser()) {
            return n;
        }
        int cnt = n.getChildCount();
        for (int i = 0; i < cnt; i++) {
            AccessibilityNodeInfo r = findScrollable(n.getChild(i), depth + 1);
            if (r != null) {
                return r;
            }
        }
        return null;
    }

    private static boolean clickNode(AccessibilityNodeInfo n) {
        AccessibilityNodeInfo p = n;
        int guard = 0;
        while (p != null && guard < 8) {
            if (p.isClickable() && p.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                return true;
            }
            p = p.getParent();
            guard++;
        }
        Rect rc = new Rect();
        n.getBoundsInScreen(rc);
        return tap(rc.centerX(), rc.centerY());
    }

    private static void findLowest(AccessibilityNodeInfo n, String q, AccessibilityNodeInfo[] best, int[] top, int depth) {
        if (n == null || depth > 40) {
            return;
        }
        String t = n.getText() == null ? "" : n.getText().toString().toLowerCase();
        String d = n.getContentDescription() == null ? "" : n.getContentDescription().toString().toLowerCase();
        if ((t.equals(q) || d.equals(q)) && n.isVisibleToUser()) {
            Rect rc = new Rect();
            n.getBoundsInScreen(rc);
            if (rc.top > top[0]) {
                top[0] = rc.top;
                best[0] = n;
            }
        }
        int cnt = n.getChildCount();
        for (int i = 0; i < cnt; i++) {
            findLowest(n.getChild(i), q, best, top, depth + 1);
        }
    }

    public static boolean clickTextLast(String q) {
        String low = q.toLowerCase().trim();
        AccessibilityNodeInfo[] best = new AccessibilityNodeInfo[1];
        int[] top = new int[]{-1};
        for (AccessibilityNodeInfo r : roots()) {
            findLowest(r, low, best, top, 0);
        }
        if (best[0] != null) {
            return clickNode(best[0]);
        }
        return false;
    }

    public static boolean clickText(String q) {
        String low = q.toLowerCase().trim();
        for (AccessibilityNodeInfo r : roots()) {
            AccessibilityNodeInfo hit = find(r, low, true, 0);
            if (hit == null) {
                hit = find(r, low, false, 0);
            }
            if (hit != null) {
                return clickNode(hit);
            }
        }
        return false;
    }

    private static AccessibilityNodeInfo inputNode() {
        for (AccessibilityNodeInfo r : roots()) {
            AccessibilityNodeInfo f = r.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
            if (f == null || !f.isEditable()) {
                f = firstEditable(r, 0);
            }
            if (f != null) {
                return f;
            }
        }
        return null;
    }

    public static boolean typeText(String s) {
        AccessibilityNodeInfo f = inputNode();
        if (f == null) {
            return false;
        }
        f.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        Bundle b = new Bundle();
        b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, s);
        return f.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, b);
    }

    public static boolean pasteText() {
        AccessibilityNodeInfo f = inputNode();
        if (f == null) {
            return false;
        }
        f.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
        return f.performAction(AccessibilityNodeInfo.ACTION_PASTE);
    }

    public static boolean setClip(String s) {
        RamboAccService x = inst;
        if (x == null) {
            return false;
        }
        try {
            ClipboardManager cm = (ClipboardManager) x.getSystemService(Context.CLIPBOARD_SERVICE);
            cm.setPrimaryClip(ClipData.newPlainText("rambo", s));
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private static final java.util.concurrent.Executor SHOT_EXEC = java.util.concurrent.Executors.newSingleThreadExecutor();

    // V78_SHOT: real screenshot as base64 JPEG (Android 11+). Call from a background thread.
    public static String shotB64(final int maxPx) {
        final RamboAccService s = inst;
        if (s == null) {
            return "ERR:accessibility service is off";
        }
        if (android.os.Build.VERSION.SDK_INT < 30) {
            return "ERR:needs Android 11 or newer";
        }
        final java.util.concurrent.CountDownLatch latch = new java.util.concurrent.CountDownLatch(1);
        final String[] out = new String[]{"ERR:timeout"};
        try {
            s.takeScreenshot(android.view.Display.DEFAULT_DISPLAY, SHOT_EXEC,
                new AccessibilityService.TakeScreenshotCallback() {
                    @Override
                    public void onSuccess(AccessibilityService.ScreenshotResult r) {
                        try {
                            android.hardware.HardwareBuffer hb = r.getHardwareBuffer();
                            android.graphics.Bitmap hw = android.graphics.Bitmap.wrapHardwareBuffer(hb, r.getColorSpace());
                            android.graphics.Bitmap sw = hw.copy(android.graphics.Bitmap.Config.ARGB_8888, false);
                            hb.close();
                            int w = sw.getWidth();
                            int h = sw.getHeight();
                            float k = Math.min(1.0f, (float) maxPx / (float) Math.max(w, h));
                            android.graphics.Bitmap sm = sw;
                            if (k < 1.0f) {
                                sm = android.graphics.Bitmap.createScaledBitmap(sw, Math.max(1, Math.round(w * k)), Math.max(1, Math.round(h * k)), true);
                            }
                            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
                            sm.compress(android.graphics.Bitmap.CompressFormat.JPEG, 70, bo);
                            out[0] = android.util.Base64.encodeToString(bo.toByteArray(), android.util.Base64.NO_WRAP);
                        } catch (Throwable t) {
                            out[0] = "ERR:" + t;
                        }
                        latch.countDown();
                    }

                    @Override
                    public void onFailure(int code) {
                        out[0] = "ERR:screenshot code " + code;
                        latch.countDown();
                    }
                });
            latch.await(8, java.util.concurrent.TimeUnit.SECONDS);
        } catch (Throwable t) {
            return "ERR:" + t;
        }
        return out[0];
    }

    public static boolean tap(int x, int y) {
        RamboAccService s = inst;
        if (s == null) {
            return false;
        }
        Path p = new Path();
        p.moveTo(x, y);
        GestureDescription.Builder b = new GestureDescription.Builder();
        b.addStroke(new GestureDescription.StrokeDescription(p, 0, 80));
        return s.dispatchGesture(b.build(), null, null);
    }

    public static boolean back() {
        RamboAccService s = inst;
        return s != null && s.performGlobalAction(GLOBAL_ACTION_BACK);
    }

    public static boolean home() {
        RamboAccService s = inst;
        return s != null && s.performGlobalAction(GLOBAL_ACTION_HOME);
    }

    public static boolean scroll(boolean forward) {
        for (AccessibilityNodeInfo r : roots()) {
            AccessibilityNodeInfo sc = findScrollable(r, 0);
            if (sc != null) {
                return sc.performAction(forward
                        ? AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
                        : AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD);
            }
        }
        return false;
    }
}
