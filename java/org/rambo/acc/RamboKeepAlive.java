package org.rambo.acc;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

public class RamboKeepAlive extends Service {
    private PowerManager.WakeLock wl = null;

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        try {
            Notification.Builder b;
            if (Build.VERSION.SDK_INT >= 26) {
                NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
                nm.createNotificationChannel(new NotificationChannel(
                        "rambo_keep", "RAMBO AI running", NotificationManager.IMPORTANCE_LOW));
                b = new Notification.Builder(this, "rambo_keep");
            } else {
                b = new Notification.Builder(this);
            }
            Intent li = getPackageManager().getLaunchIntentForPackage(getPackageName());
            if (li != null) {
                int fl = PendingIntent.FLAG_UPDATE_CURRENT;
                if (Build.VERSION.SDK_INT >= 23) {
                    fl |= PendingIntent.FLAG_IMMUTABLE;
                }
                b.setContentIntent(PendingIntent.getActivity(this, 0, li, fl));
            }
            b.setSmallIcon(getApplicationInfo().icon);
            b.setContentTitle("RAMBO AI is working");
            b.setContentText("Auto run is going in the background");
            b.setOngoing(true);
            Notification n = b.build();
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(2, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
            } else {
                startForeground(2, n);
            }
            if (wl == null) {
                PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
                wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "rambo:keep");
                wl.acquire(6 * 60 * 60 * 1000L);
            }
        } catch (Exception e) {
        }
        return START_NOT_STICKY;
    }

    @Override
    public void onDestroy() {
        try {
            if (wl != null && wl.isHeld()) {
                wl.release();
            }
        } catch (Exception e) {
        }
        wl = null;
        super.onDestroy();
    }
}
