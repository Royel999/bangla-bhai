package org.dpdns.rbt;
import android.content.Intent;import android.service.quicksettings.TileService;import android.app.PendingIntent;import android.os.Build;
public class ClipTile extends TileService{public void onClick(){Intent i=new Intent(this,ClipActivity.class).setAction("save").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
 if(Build.VERSION.SDK_INT>=34)startActivityAndCollapse(PendingIntent.getActivity(this,9,i,PendingIntent.FLAG_IMMUTABLE));else startActivityAndCollapse(i);}}
