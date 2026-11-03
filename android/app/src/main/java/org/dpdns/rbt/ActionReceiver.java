package org.dpdns.rbt;
import android.content.*;import android.widget.Toast;
public class ActionReceiver extends BroadcastReceiver{public void onReceive(Context c,Intent i){if("pause".equals(i.getAction())){boolean p=!Link.paused(c);Link.p(c).edit().putBoolean("paused",p).apply();
 Toast.makeText(c,p?"⏸ কপি-ধরা বিরতিতে":"▶ কপি-ধরা চালু",0).show();try{c.startForegroundService(new Intent(c,LinkService.class).setAction("refresh"));}catch(Exception e){}}}}
