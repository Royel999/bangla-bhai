package org.dpdns.rbt;
import android.app.*;import android.content.*;import android.graphics.PixelFormat;import android.os.*;import android.view.*;import android.widget.ImageView;
public class BubbleService extends Service{WindowManager wm;View v;
 public IBinder onBind(Intent i){return null;}
 public int onStartCommand(Intent i,int f,int id){getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("rbt_bubble","ভাসমান নোটবুক",NotificationManager.IMPORTANCE_MIN));
  Notification n=new Notification.Builder(this,"rbt_bubble").setSmallIcon(R.drawable.seal).setContentTitle("🐯 ভাসমান নোটবুক চালু").build();
  if(Build.VERSION.SDK_INT>=34)startForeground(8,n,android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);else startForeground(8,n);
  if(v==null&&android.provider.Settings.canDrawOverlays(this))show();return START_STICKY;}
 void show(){wm=getSystemService(WindowManager.class);ImageView iv=new ImageView(this);iv.setImageResource(R.drawable.seal);int s=(int)(56*getResources().getDisplayMetrics().density);
  WindowManager.LayoutParams lp=new WindowManager.LayoutParams(s,s,WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,PixelFormat.TRANSLUCENT);
  lp.gravity=Gravity.TOP|Gravity.START;SharedPreferences p=Link.p(this);lp.x=p.getInt("bx",0);lp.y=p.getInt("by",400);
  iv.setOnTouchListener(new View.OnTouchListener(){float sx,sy;int ox,oy;long t0;
   public boolean onTouch(View w,MotionEvent e){switch(e.getAction()){
    case MotionEvent.ACTION_DOWN:sx=e.getRawX();sy=e.getRawY();ox=lp.x;oy=lp.y;t0=System.currentTimeMillis();return true;
    case MotionEvent.ACTION_MOVE:lp.x=ox+(int)(e.getRawX()-sx);lp.y=oy+(int)(e.getRawY()-sy);wm.updateViewLayout(iv,lp);return true;
    case MotionEvent.ACTION_UP:p.edit().putInt("bx",lp.x).putInt("by",lp.y).apply();
     if(Math.abs(e.getRawX()-sx)<15&&Math.abs(e.getRawY()-sy)<15){boolean lng=System.currentTimeMillis()-t0>600;
      startActivity(new Intent(BubbleService.this,lng?ClipActivity.class:QuickActivity.class).setAction("save").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}return true;}return false;}});
  v=iv;wm.addView(iv,lp);}
 public void onDestroy(){if(v!=null)wm.removeView(v);v=null;super.onDestroy();}}
