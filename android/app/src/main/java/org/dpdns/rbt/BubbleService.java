package org.dpdns.rbt;
import android.app.*;import android.content.*;import android.graphics.PixelFormat;import android.os.*;import android.view.*;import android.widget.ImageView;
import android.net.ConnectivityManager;import android.net.Network;import android.net.NetworkCapabilities;
/* Realistic doyel (oriental magpie-robin) overlay. Flies → lands on the screen bottom or under the status bar → idle fidgets
   (tail-cock, look back, preen, sing, hop) → takes off. Flight speed follows internet bandwidth (ConnectivityManager); offline = stays perched.
   Tap = quick note, long-press = clips, drag & drop = pinned there (fidgets only), double-tap = fly again. Pref "roam" off = stays perched. */
public class BubbleService extends Service{WindowManager wm;ImageView v;WindowManager.LayoutParams lp;final Handler h=new Handler(Looper.getMainLooper());
 static final int[] FLY={R.drawable.doyel_fly0,R.drawable.doyel_fly1,R.drawable.doyel_fly2,R.drawable.doyel_fly3,R.drawable.doyel_fly4,R.drawable.doyel_fly5,R.drawable.doyel_fly6,R.drawable.doyel_fly7};
 static final int PERCH=R.drawable.doyel_perch0;
 static final int[] IDLE={R.drawable.doyel_perch0,R.drawable.doyel_perch0,R.drawable.doyel_perch0,R.drawable.doyel_cock0,R.drawable.doyel_cock1,R.drawable.doyel_cock0,R.drawable.doyel_look0,R.drawable.doyel_look0,R.drawable.doyel_preen0,R.drawable.doyel_sing0,R.drawable.doyel_down0};
 float x,y,tx,ty;int sz,foot,wing=0,glide=0,state=1,cur=0;/* 0 fly,1 perch,2 pinned */boolean tgtPerch=false,touching=false;float face=-1;long until=0,nextF=0,lastNet=0,lastFlap=0;Float net=1f;
 public IBinder onBind(Intent i){return null;}
 boolean roam(){return Link.p(this).getBoolean("roam",true);}
 public int onStartCommand(Intent i,int f,int id){
  if(i!=null&&"roam".equals(i.getAction())){Link.p(this).edit().putBoolean("roam",!roam()).apply();}
  if(i!=null&&"fly".equals(i.getAction())){pin(false);}
  getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("rbt_bubble","ভাসমান নোটবুক",NotificationManager.IMPORTANCE_MIN));
  PendingIntent pi=PendingIntent.getService(this,9,new Intent(this,BubbleService.class).setAction("roam"),PendingIntent.FLAG_IMMUTABLE);
  PendingIntent pf=PendingIntent.getService(this,10,new Intent(this,BubbleService.class).setAction("fly"),PendingIntent.FLAG_IMMUTABLE);
  Notification n=new Notification.Builder(this,"rbt_bubble").setSmallIcon(R.drawable.seal).setContentTitle("🐦 দোয়েল "+(roam()?"উড়ছে":"বসে আছে"))
   .addAction(new Notification.Action.Builder(null,roam()?"⏸ ঘোরা থামান":"▶ ঘোরান",pi).build()).addAction(new Notification.Action.Builder(null,"🕊 উড়ে যাও",pf).build()).build();
  if(Build.VERSION.SDK_INT>=34)startForeground(8,n,android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);else startForeground(8,n);
  if(v==null&&android.provider.Settings.canDrawOverlays(this))show();
  h.removeCallbacks(tick);h.post(tick);return START_STICKY;}
 /* bandwidth → speed factor; null = offline */
 Float probeNet(){try{ConnectivityManager cm=getSystemService(ConnectivityManager.class);Network nw=cm.getActiveNetwork();if(nw==null)return null;NetworkCapabilities c=cm.getNetworkCapabilities(nw);
   if(c==null||!c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET))return null;float mbps=c.getLinkDownstreamBandwidthKbps()/1000f;
   return (float)Math.max(.35,Math.min(2.6,.4+.5*Math.log(1+mbps)/Math.log(2)));}catch(Exception e){return 1f;}}
 int W(){return getResources().getDisplayMetrics().widthPixels-sz;}
 int Hs(){return getResources().getDisplayMetrics().heightPixels;}
 int statusBar(){int r=getResources().getIdentifier("status_bar_height","dimen","android");return r>0?getResources().getDimensionPixelSize(r):(int)(24*getResources().getDisplayMetrics().density);}
 void pick(boolean perch){tgtPerch=perch;tx=(float)(Math.random()*W());
  if(perch){ty=Math.random()<.7?Hs()-foot-statusBar():statusBar()-foot+sz/6f;}   /* screen bottom (above nav) or hanging under the status bar */
  else ty=(float)(statusBar()+Math.random()*(Hs()*.7));}
 void set(int res){if(res!=cur){cur=res;v.setImageResource(res);}v.setScaleX(face);}
 void pin(boolean on){if(v==null)return;SharedPreferences.Editor e=Link.p(this).edit().putBoolean("pinned",on);
  if(on){state=2;nextF=0;e.putInt("bx",lp.x).putInt("by",lp.y);}else{state=0;pick(false);until=SystemClock.uptimeMillis()+20000;}e.apply();}
 void fidget(long t){double r=Math.random();if(r<.1){face=-face;set(PERCH);nextF=t+900;return;}
  if(r<.2){set(R.drawable.doyel_hop0);h.postDelayed(()->{if(v==null)return;set(R.drawable.doyel_hop1);lp.y-=sz/10;upd();},150);
   h.postDelayed(()->{if(v==null)return;lp.y+=sz/10;lp.x=(int)Math.max(0,Math.min(W(),lp.x+face*sz/8));x=lp.x;upd();set(PERCH);},420);nextF=t+1600;return;}
  int res=IDLE[(int)(Math.random()*IDLE.length)];set(res);nextF=t+700+(long)(Math.random()*(res==R.drawable.doyel_preen0?3500:2000));}
 void upd(){try{wm.updateViewLayout(v,lp);}catch(Exception e){}}
 final Runnable tick=new Runnable(){public void run(){if(v==null)return;long t=SystemClock.uptimeMillis();int dt=33;
  if(t-lastNet>60000){lastNet=t;net=probeNet();}
  if(touching){dt=60;}
  else if(state!=0){if(t>nextF)fidget(t);
   if(state==1&&t>until&&roam()&&net!=null){pick(Math.random()<.3);state=0;until=t+14000+(long)(Math.random()*24000);}dt=100;}
  else{if((net==null||!roam()||t>until)&&!tgtPerch)pick(true);
   float sp=3.2f*getResources().getDisplayMetrics().density/2f*Link.p(BubbleService.this).getInt("roam_speed",2)/2f*(net==null?.6f:net)*(tgtPerch?1.25f:1f);
   float dx=tx-x,dy=ty-y;double d=Math.hypot(dx,dy);
   if(d<sp+1){x=tx;y=ty;lp.x=(int)x;lp.y=(int)y;upd();if(tgtPerch){state=1;until=t+5000+(long)(Math.random()*9000);nextF=0;set(PERCH);}else pick(false);}
   else{if(Math.abs(dx)>2)face=dx>0?1:-1;x+=dx/d*sp;y+=dy/d*sp;
    if(glide>0){glide--;set(R.drawable.doyel_glide0);}else if(t-lastFlap>Math.max(30,55/Math.sqrt(net==null?.6:net))){lastFlap=t;wing=(wing+1)%8;set(FLY[wing]);if(wing==2&&dy>-.3*Math.abs(dx)&&d>400&&Math.random()<.3)glide=20+(int)(Math.random()*30);}
    lp.x=(int)x;lp.y=(int)(y+(glide>0?0:4*Math.sin(t/60.0)));upd();}}
  h.postDelayed(this,dt);}};
 void show(){wm=getSystemService(WindowManager.class);ImageView iv=new ImageView(this);iv.setImageResource(PERCH);cur=PERCH;float dn=getResources().getDisplayMetrics().density;sz=(int)(96*dn);foot=(int)(93*dn);
  lp=new WindowManager.LayoutParams(sz,sz,WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE|WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,PixelFormat.TRANSLUCENT);
  lp.gravity=Gravity.TOP|Gravity.START;SharedPreferences p=Link.p(this);lp.x=p.getInt("bx",0);lp.y=p.getInt("by",400);x=lp.x;y=lp.y;
  state=p.getBoolean("pinned",false)?2:1;until=SystemClock.uptimeMillis()+3000;
  iv.setOnTouchListener(new View.OnTouchListener(){float sx,sy;int ox,oy;long t0,lastTap=0;boolean moved;final Runnable single[]={null};
   public boolean onTouch(View w,MotionEvent e){switch(e.getAction()){
    case MotionEvent.ACTION_DOWN:touching=true;moved=false;sx=e.getRawX();sy=e.getRawY();ox=lp.x;oy=lp.y;t0=System.currentTimeMillis();return true;
    case MotionEvent.ACTION_MOVE:if(Math.abs(e.getRawX()-sx)+Math.abs(e.getRawY()-sy)>15){moved=true;set(FLY[0]);}lp.x=ox+(int)(e.getRawX()-sx);lp.y=oy+(int)(e.getRawY()-sy);x=lp.x;y=lp.y;upd();return true;
    case MotionEvent.ACTION_UP:case MotionEvent.ACTION_CANCEL:touching=false;
     if(moved){pin(true);return true;}
     long now=System.currentTimeMillis();
     if(now-lastTap<320){if(single[0]!=null)h.removeCallbacks(single[0]);lastTap=0;if(state==2)pin(false);else{pick(true);state=0;}return true;}
     lastTap=now;final boolean lng=now-t0>600;
     single[0]=()->startActivity(new Intent(BubbleService.this,lng?ClipActivity.class:QuickActivity.class).setAction("save").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
     h.postDelayed(single[0],lng?0:330);return true;}return false;}});
  v=iv;wm.addView(iv,lp);}
 public void onDestroy(){h.removeCallbacks(tick);if(v!=null)wm.removeView(v);v=null;super.onDestroy();}}
