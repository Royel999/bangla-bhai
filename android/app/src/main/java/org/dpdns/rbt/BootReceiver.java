package org.dpdns.rbt;
import android.content.*;
public class BootReceiver extends BroadcastReceiver{public void onReceive(Context c,Intent i){if(Link.p(c).getBoolean("enabled",true))Link.start(c);}}
