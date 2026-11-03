package org.dpdns.rbt;
import android.app.*;import android.content.*;import android.graphics.PixelFormat;import android.os.*;import android.view.*;import android.widget.ImageView;
/* Floating notebook bubble that roams the whole screen (bounces off edges). Touch = stops; tap = quick note; long-press = clips.
   Roaming toggle: pref "roam" (app button or notification action). Low CPU: ~30 fps only while roaming, nothing while paused. */
public class BubbleService extends Service{WindowManager wm;ImageView v;WindowManager.LayoutParams lp;final Handler h=new Handler(Looper.getMainLooper());
 float x,y,vx,vy;long holdUntil=0;boolean touching=false;int sz;
 public IBinder onBind(Intent i){return null;}
 boolean roam(){return Link.p(this).getBoolean("roam",true);}
 public int onStartCommand(Intent i,int f,int id){
  if(i!=null&&"roam".equals(i.getAction())){Link.p(this).edit().putBoolean("roam",!roam()).apply();}
  getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("rbt_bubble","ভাসমান নোটবুক",NotificationManager.IMPORTANCE_MIN));
  PendingIntent pi=PendingIntent.getService(this,9,new Intent(this,BubbleService.class).setAction("roam"),PendingIntent.FLAG_IMMUTABLE);
  Notification n=new Notification.Builder(this,"rbt_bubble").setSmallIcon(R.drawable.seal).setContentTitle("🐯 ভাসমান নোটবুক "+(roam()?"ঘুরছে":"থেমে আছে"))
   .addAction(new Notification.Action.Builder(null,roam()?"⏸ ঘোরা থামান":"▶ ঘোরান",pi).build()).build();
  if(Build.VERSION.SDK_INT>=34)startForeground(8,n,android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);else startForeground(8,n);
  if(v==null&&android.provider.Settings.canDrawOverlays(this))show();
  h.removeCallbacks(tick);if(roam())h.post(tick);return START_STICKY;}
 final Runnable tick=new Runnable(){public void run(){if(v==null||!roam())return;
  if(!touching&&SystemClock.uptimeMillis()>holdUntil){android.util.DisplayMetrics m=getResources().getDisplayMetrics();int W=m.widthPixels-sz,H=m.heightPixels-sz;
   float sp=Link.p(BubbleService.this).getInt("roam_speed",2);x+=vx*sp;y+=vy*sp;
   if(x<0){x=0;vx=Math.abs(vx);}if(x>W){x=W;vx=-Math.abs(vx);}if(y<0){y=0;vy=Math.abs(vy);}if(y>H){y=H;vy=-Math.abs(vy);}
   if(Math.random()<0.01){vx+=(float)(Math.random()-.5);vy+=(float)(Math.random()-.5);float s=(float)Math.hypot(vx,vy);if(s>0){vx=vx/s*1.5f;vy=vy/s*1.5f;}}
   lp.x=(int)x;lp.y=(int)y;try{wm.updateViewLayout(v,lp);}catch(Exception e){}
   v.setScaleX(1f+0.06f*(float)Math.sin(SystemClock.uptimeMillis()/300.0));v.setScaleY(v.getScaleX());}
  h.postDelayed(this,33);}};
 void show(){wm=getSystemService(WindowManager.class);ImageView iv=new ImageView(this);iv.setImageResource(R.drawable.seal);sz=(int)(56*getResources().getDisplayMetrics().density);
  lp=new WindowManager.LayoutParams(sz,sz,WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE|WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,PixelFormat.TRANSLUCENT);
  lp.gravity=Gravity.TOP|Gravity.START;SharedPreferences p=Link.p(this);lp.x=p.getInt("bx",0);lp.y=p.getInt("by",400);x=lp.x;y=lp.y;double a=Math.random()*6.28;vx=(float)Math.cos(a)*1.5f;vy=(float)Math.sin(a)*1.5f;
  iv.setOnTouchListener(new View.OnTouchListener(){float sx,sy;int ox,oy;long t0;
   public boolean onTouch(View w,MotionEvent e){switch(e.getAction()){
    case MotionEvent.ACTION_DOWN:touching=true;sx=e.getRawX();sy=e.getRawY();ox=lp.x;oy=lp.y;t0=System.currentTimeMillis();return true;
    case MotionEvent.ACTION_MOVE:lp.x=ox+(int)(e.getRawX()-sx);lp.y=oy+(int)(e.getRawY()-sy);x=lp.x;y=lp.y;wm.updateViewLayout(iv,lp);return true;
    case MotionEvent.ACTION_UP:case MotionEvent.ACTION_CANCEL:touching=false;holdUntil=SystemClock.uptimeMillis()+5000;p.edit().putInt("bx",lp.x).putInt("by",lp.y).apply();
     if(Math.abs(e.getRawX()-sx)<15&&Math.abs(e.getRawY()-sy)<15){boolean lng=System.currentTimeMillis()-t0>600;
      startActivity(new Intent(BubbleService.this,lng?ClipActivity.class:QuickActivity.class).setAction("save").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}return true;}return false;}});
  v=iv;wm.addView(iv,lp);}
 public void onDestroy(){h.removeCallbacks(tick);if(v!=null)wm.removeView(v);v=null;super.onDestroy();}}
