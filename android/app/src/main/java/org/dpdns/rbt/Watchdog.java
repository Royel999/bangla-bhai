package org.dpdns.rbt;
import android.content.Context;import androidx.annotation.NonNull;import androidx.work.*;
public class Watchdog extends Worker{public Watchdog(@NonNull Context c,@NonNull WorkerParameters p){super(c,p);}
 @NonNull public Result doWork(){if(Link.p(getApplicationContext()).getBoolean("enabled",true))Link.start(getApplicationContext());return Result.success();}}
