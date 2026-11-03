package org.dpdns.rbt;
import android.app.*;import android.content.*;import android.graphics.*;import android.os.*;import android.view.*;import android.widget.*;import android.util.LruCache;
import org.json.*;import java.io.*;import java.util.*;import java.util.concurrent.*;import java.util.regex.Pattern;
/* মামণি overlay (v3): 600px video-derived frames downloaded from the server and cached on the phone (cartoon sprites only, no photos).
   Long 1–5 min story routines (read, draw, ball+blocks, snack, water plant, nap, stroll), rare quick bits, eased walk along the bottom edge,
   drag = stays there 30–120 s then hops down and walks off, tap = agent panel, double-tap = stroll, long-press = save clipboard. Sleeps 22:00–05:00 Dhaka.
   Battery: animation stops while the screen is off; optional low-fps; optional hide in fullscreen apps. Work buddy tips are rate-limited and learn locally only. */
public class GirlService extends Service{
 static GirlService I;final Handler h=new Handler(Looper.getMainLooper());WindowManager wm;ImageView v;WindowManager.LayoutParams lp;TextView bub;WindowManager.LayoutParams blp;
 File dir;JSONObject man;final Set<String> ready=ConcurrentHashMap.newKeySet();LruCache<String,Bitmap> cache;int S;float face=1;boolean screenOn=true,touching,moved;
 static final String G3="/bb/static/notes/girl3/";
 static final Map<String,int[]> LOOP=new HashMap<>();static{LOOP.put("walk",new int[]{36,64});LOOP.put("read",new int[]{40,60});LOOP.put("draw",new int[]{30,64});LOOP.put("sleep",new int[]{46,60});
  LOOP.put("watch",new int[]{14,27});LOOP.put("blocks",new int[]{60,80});LOOP.put("wave",new int[]{10,27});}
 static class Seg{String c;int[] fr;int i;int fps;String say;boolean fm;String prop;}
 final ArrayDeque<Seg> cq=new ArrayDeque<>();final ArrayList<Object[]> rt=new ArrayList<>();
 static final int PERCH=0,WALK=1,PIN=2,SLEEP=3,DROP=4;int state=PERCH;float x,y,tx,vel,wph,vy;long until,lastT,sleepUntil;String pose="";
 final Random R=new Random();
 static final Map<String,String[]> SAY=new HashMap<>();static{SAY.put("hi",new String[]{"আব্বু!","হাই আব্বু!","দেখো দেখো!"});SAY.put("read",new String[]{"গল্প পড়ছি…","এটা কী লেখা?"});
  SAY.put("draw",new String[]{"ছবি আঁকছি…","রং কোনটা দেবো?"});SAY.put("show",new String[]{"দেখো আব্বু, ছবি আঁকলাম!","সুন্দর হয়েছে না?"});SAY.put("play",new String[]{"খেলবে?","চলো খেলি!","বল খেলবো!"});
  SAY.put("blocks",new String[]{"উঁচু টাওয়ার বানাবো!","দেখো কত উঁচু!"});SAY.put("snack",new String[]{"মজার নাস্তা!","ইয়াম ইয়াম!"});SAY.put("water",new String[]{"গাছে পানি দিই","গাছটা বড় হবে!"});
  SAY.put("sleep",new String[]{"ঘুম পাচ্ছে…","শুভ রাত্রি আব্বু"});SAY.put("wake",new String[]{"শুভ সকাল!","উঠে গেছি!"});SAY.put("walk",new String[]{"হাঁটতে যাই…","ওদিকে কী আছে?"});
  SAY.put("giggle",new String[]{"হি হি!","হা হা হা!"});SAY.put("happy",new String[]{"রেখে দিলাম!","পেয়েছি!","হি হি!"});SAY.put("peek",new String[]{"টুকি!","খুঁজে পাও তো!"});}
 SharedPreferences P(){return Link.p(this);}
 int dp(float d){return (int)(d*getResources().getDisplayMetrics().density);}
 int Wd(){return getResources().getDisplayMetrics().widthPixels;}
 int Hd(){return getResources().getDisplayMetrics().heightPixels;}
 int navH(){int r=getResources().getIdentifier("navigation_bar_height","dimen","android");return r>0?getResources().getDimensionPixelSize(r):dp(48);}
 float groundY(){return Hd()-navH()-S*296f/300f+dp(2);}
 boolean night(){int hr=Calendar.getInstance(TimeZone.getTimeZone("Asia/Dhaka")).get(Calendar.HOUR_OF_DAY);return hr>=22||hr<5;}
 boolean low(){return P().getBoolean("lowfps",false);}
 public IBinder onBind(Intent i){return null;}
 final BroadcastReceiver scr=new BroadcastReceiver(){public void onReceive(Context c,Intent i){screenOn=Intent.ACTION_SCREEN_ON.equals(i.getAction())||Intent.ACTION_USER_PRESENT.equals(i.getAction());
  h.removeCallbacks(tick);if(screenOn){lastT=SystemClock.uptimeMillis();h.post(tick);}if(coach!=null)coach.screen(screenOn);}};
 Coach coach;
 public void onCreate(){super.onCreate();I=this;dir=new File(getFilesDir(),"girl3");dir.mkdirs();
  int mem=(int)Math.min(48L<<20,Runtime.getRuntime().maxMemory()/4);cache=new LruCache<String,Bitmap>(mem){protected int sizeOf(String k,Bitmap b){return b.getByteCount();}};
  IntentFilter f=new IntentFilter(Intent.ACTION_SCREEN_OFF);f.addAction(Intent.ACTION_SCREEN_ON);f.addAction(Intent.ACTION_USER_PRESENT);registerReceiver(scr,f);
  new Thread(this::download).start();coach=new Coach(this);}
 public void onDestroy(){I=null;h.removeCallbacksAndMessages(null);try{unregisterReceiver(scr);}catch(Exception e){}try{if(v!=null)wm.removeView(v);if(bub!=null)wm.removeView(bub);}catch(Exception e){}v=null;if(coach!=null)coach.stop();super.onDestroy();}
 public int onStartCommand(Intent i,int fl,int id){
  getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("rbt_girl","মামণি সঙ্গী",NotificationManager.IMPORTANCE_MIN));
  PendingIntent pp=PendingIntent.getActivity(this,21,new Intent(this,PanelActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),PendingIntent.FLAG_IMMUTABLE);
  PendingIntent ph=PendingIntent.getService(this,22,new Intent(this,GirlService.class).setAction("hide"),PendingIntent.FLAG_IMMUTABLE);
  Notification n=new Notification.Builder(this,"rbt_girl").setSmallIcon(org.dpdns.rbt.R.drawable.seal).setContentTitle("👧 মামণি পাশে আছে").setContentText("ট্যাপ করলে এজেন্ট প্যানেল").setContentIntent(pp)
   .addAction(new Notification.Action.Builder(null,"🙈 লুকাও",ph).build()).build();
  if(Build.VERSION.SDK_INT>=34)startForeground(9,n,android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);else startForeground(9,n);
  if(i!=null&&"hide".equals(i.getAction())){P().edit().putBoolean("bubble",false).apply();stopSelf();return START_NOT_STICKY;}
  if(v==null&&android.provider.Settings.canDrawOverlays(this))show();return START_STICKY;}
 /* ---------- frames ---------- */
 void download(){try{File mf=new File(dir,"manifest.json");
   try{man=Link.get(G3+"manifest.json");try(FileWriter w=new FileWriter(mf)){w.write(man.toString());}}catch(Exception e){man=new JSONObject(new String(java.nio.file.Files.readAllBytes(mf.toPath())));}
   String[] order={"watch","walk","wave","read","draw","ball","blocks","snack","water","sleep"};
   for(String c:order){if(!man.has(c))continue;File d=new File(dir,c);d.mkdirs();int n=man.getJSONObject(c).getInt("n");boolean ok=true;
    for(int k=0;k<n&&ok;k++){File f=new File(d,String.format(Locale.US,"%03d.webp",k));if(f.length()>200)continue;
     for(int a=0;a<3;a++){try(okhttp3.Response r=Link.HTTP.newCall(new okhttp3.Request.Builder().url(Link.BASE+G3+c+"/"+f.getName()).build()).execute()){
       if(!r.isSuccessful())throw new IOException("http "+r.code());File tf=new File(d,f.getName()+".t");try(FileOutputStream o=new FileOutputStream(tf)){o.write(r.body().bytes());}tf.renameTo(f);break;}
      catch(Exception e){if(a==2)ok=false;try{Thread.sleep(2000);}catch(Exception x){}}}}
    if(ok)ready.add(c);}}
  catch(Exception e){android.util.Log.w("girl","download",e);}}
 boolean all3(){return man!=null&&ready.size()>=man.length();}
 int fps(String c){try{return man.getJSONObject(c).getInt("fps");}catch(Exception e){return 10;}}
 int nfr(String c){try{return man.getJSONObject(c).getInt("n");}catch(Exception e){return 1;}}
 Bitmap frame(String c,int i){String k=c+i;Bitmap b=cache.get(k);if(b!=null)return b;
  BitmapFactory.Options o=new BitmapFactory.Options();o.inSampleSize=S<=300?2:1;Bitmap raw=BitmapFactory.decodeFile(new File(new File(dir,c),String.format(Locale.US,"%03d.webp",i)).getPath(),o);
  if(raw==null)return null;b=raw.getWidth()==S?raw:Bitmap.createScaledBitmap(raw,S,S,true);if(b!=raw)raw.recycle();cache.put(k,b);return b;}
 void show3(String c,int i){if(!ready.contains(c))return;String k=c+":"+i;if(!k.equals(pose)){Bitmap b=frame(c,i);if(b!=null){v.setImageBitmap(b);pose=k;}}v.setScaleX(face);}
 /* ---------- window ---------- */
 void show(){wm=getSystemService(WindowManager.class);String z=P().getString("gsize","medium");S=dp(z.equals("small")?96:z.equals("large")?180:132);
  v=new ImageView(this);v.setImageResource(org.dpdns.rbt.R.drawable.seal);v.setScaleType(ImageView.ScaleType.FIT_CENTER);
  lp=new WindowManager.LayoutParams(S,S,WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE|WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,PixelFormat.TRANSLUCENT);
  lp.gravity=Gravity.TOP|Gravity.START;x=P().getInt("gx",Wd()-S-dp(8));y=groundY();lp.x=(int)x;lp.y=(int)y;wm.addView(v,lp);
  bub=new TextView(this);bub.setTextColor(0xFF5A2400);bub.setTextSize(14);bub.setPadding(dp(10),dp(6),dp(10),dp(6));bub.setMaxWidth((int)(Wd()*.7));
  android.graphics.drawable.GradientDrawable g=new android.graphics.drawable.GradientDrawable();g.setColor(0xFFFFF6D8);g.setCornerRadius(dp(12));g.setStroke(dp(1),0xFFB07A3A);bub.setBackground(g);bub.setVisibility(View.GONE);
  blp=new WindowManager.LayoutParams(-2,-2,WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE|WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE|WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,PixelFormat.TRANSLUCENT);
  blp.gravity=Gravity.TOP|Gravity.START;wm.addView(bub,blp);
  if(Build.VERSION.SDK_INT>=30)v.setOnApplyWindowInsetsListener((vv,ins)->{if(P().getBoolean("fshide",false)){boolean full=!ins.isVisible(WindowInsets.Type.statusBars())&&!ins.isVisible(WindowInsets.Type.navigationBars());vv.setAlpha(full?0f:1f);}else vv.setAlpha(1f);return ins;});
  final GestureDetector gd=new GestureDetector(this,new GestureDetector.SimpleOnGestureListener(){
   public boolean onSingleTapConfirmed(MotionEvent e){startActivity(new Intent(GirlService.this,PanelActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));return true;}
   public boolean onDoubleTap(MotionEvent e){wake();cq.clear();routine("stroll");return true;}
   public void onLongPress(MotionEvent e){if(!moved)startActivity(new Intent(GirlService.this,ClipActivity.class).setAction("save").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}});
  final float[] d=new float[4];
  v.setOnTouchListener((vv,e)->{gd.onTouchEvent(e);switch(e.getActionMasked()){
   case MotionEvent.ACTION_DOWN:d[0]=e.getRawX();d[1]=e.getRawY();d[2]=lp.x;d[3]=lp.y;moved=false;touching=true;break;
   case MotionEvent.ACTION_MOVE:float dx=e.getRawX()-d[0],dy=e.getRawY()-d[1];if(Math.abs(dx)+Math.abs(dy)>dp(8))moved=true;if(moved){x=d[2]+dx;y=d[3]+dy;place();}break;
   case MotionEvent.ACTION_UP:case MotionEvent.ACTION_CANCEL:touching=false;if(moved){wake();cq.clear();rt.clear();state=PIN;until=SystemClock.uptimeMillis()+30000+R.nextInt(90000);
     P().edit().putInt("gx",(int)x).apply();say("giggle");}break;}return true;});
  lastT=SystemClock.uptimeMillis();until=lastT+3000;h.post(tick);}
 void place(){lp.x=(int)x;lp.y=(int)y;try{wm.updateViewLayout(v,lp);}catch(Exception e){}posBub();}
 void posBub(){if(bub==null||bub.getVisibility()!=View.VISIBLE)return;bub.measure(0,0);blp.x=(int)Math.max(0,Math.min(Wd()-bub.getMeasuredWidth(),x+S/2f-bub.getMeasuredWidth()/2f));blp.y=(int)Math.max(0,y+S*.05f-bub.getMeasuredHeight());try{wm.updateViewLayout(bub,blp);}catch(Exception e){}}
 final Runnable hideB=()->{if(bub!=null)bub.setVisibility(View.GONE);};
 void sayText(String t,int ms){if(bub==null)return;bub.setText(t);bub.setVisibility(View.VISIBLE);posBub();h.removeCallbacks(hideB);h.postDelayed(hideB,ms);}
 long tSay;void say(String k){long t=SystemClock.uptimeMillis();if(t-tSay<5000)return;tSay=t;String[] a=SAY.get(k);sayText(a==null?k:a[R.nextInt(a.length)],2800);}
 /* ---------- segments & routines ---------- */
 Seg seg(String c,String mode,double secs){Seg s=new Seg();s.c=c;s.fps=fps(c);int n=nfr(c);int[] L=LOOP.containsKey(c)?LOOP.get(c):new int[]{0,n};ArrayList<Integer> a=new ArrayList<>();
  if(mode.equals("once"))for(int i=0;i<n;i++)a.add(i);else if(mode.equals("in"))for(int i=0;i<L[0];i++)a.add(i);else if(mode.equals("out"))for(int i=L[0]-1;i>=0;i--)a.add(i);
  else while(a.size()<secs*s.fps)for(int i=L[0];i<L[1];i++)a.add(i);
  s.fr=new int[a.size()];for(int i=0;i<s.fr.length;i++)s.fr[i]=a.get(i);return s;}
 Seg sy(Seg s,String k){s.say=k;return s;}Seg fm(Seg s){s.fm=true;return s;}Seg pr(Seg s,String p){s.prop=p;return s;}
 double U(double a,double b){return a+R.nextDouble()*(b-a);}
 Object[] D(Seg... s){return new Object[]{"do",s};}Object[] GO(String w){return new Object[]{"go",w};}
 void routine(String k){rt.clear();switch(k){
  case "read":rt.add(GO("far"));rt.add(D(sy(seg("read","in",0),"read"),seg("read","loop",U(35,70)),seg("read","loop",U(30,60)),seg("read","out",0),sy(fm(seg("wave","once",0)),"hi")));break;
  case "draw":rt.add(GO("far"));rt.add(D(sy(seg("draw","in",0),"draw"),seg("draw","loop",U(40,100)),sy(seg("draw","out",0),"show"),fm(seg("wave","once",0))));break;
  case "play":{rt.add(GO("far"));int n=3+R.nextInt(3);Seg[] b=new Seg[n];for(int i=0;i<n;i++)b[i]=i==0?sy(seg("ball","once",0),"play"):seg("ball","once",0);rt.add(D(b));
   rt.add(GO("near"));rt.add(D(sy(seg("blocks","once",0),"blocks"),seg("blocks","loop",U(10,25)),seg("blocks","out",0)));break;}
  case "snack":rt.add(GO("far"));rt.add(D(sy(seg("snack","once",0),"snack"),seg("snack","once",0),seg("watch","loop",U(15,30))));break;
  case "garden":rt.add(GO("far"));rt.add(D(sy(seg("water","once",0),"water"),seg("water","once",0),seg("watch","loop",U(10,20)),seg("water","once",0)));rt.add(GO("near"));rt.add(D(seg("ball","once",0)));break;
  case "nap":rt.add(GO("near"));rt.add(new Object[]{"sleep",U(120,240)});break;
  case "stroll":rt.add(GO("far"));rt.add(D(seg("watch","loop",U(6,12))));rt.add(GO("far"));rt.add(D(fm(seg("wave","once",0))));rt.add(GO("far"));rt.add(D(seg("watch","loop",U(8,15))));break;}}
 void nextStep(){Object[] st=rt.remove(0);String k=(String)st[0];
  if(k.equals("do")){cq.addAll(Arrays.asList((Seg[])st[1]));return;}
  if(k.equals("sleep")){goSleep((Double)st[1]);return;}
  if(state==PIN)return;String w=(String)st[1];float W=Wd()-S;
  if(w.equals("far")){float best=x;for(int i=0;i<4;i++){float c=(float)(R.nextDouble()*W);if(Math.abs(c-x)>Math.abs(best-x))best=c;}tx=best;}
  else tx=Math.max(0,Math.min(W,x+(R.nextBoolean()?1:-1)*S*(.8f+R.nextFloat())));
  if(Math.abs(y-groundY())>4){state=DROP;vy=0;}else state=WALK;vel=0;}
 void goSleep(double secs){state=SLEEP;sleepUntil=SystemClock.uptimeMillis()+(long)(secs*1000);say("sleep");cq.clear();cq.add(seg("sleep","in",0));cq.add(pr(seg("sleep","loop",Math.min(secs,600)),"zzz"));}
 void wake(){if(state==SLEEP){state=PERCH;cq.clear();rt.clear();cq.add(sy(seg("sleep","out",0),"wake"));cq.add(fm(seg("wave","once",0)));}}
 void choose(){if(night()){routine("nap");if(!rt.isEmpty())rt.set(rt.size()-1,new Object[]{"sleep",3600.0});return;}
  String[] K={"read","draw","play","snack","garden","stroll","nap","quick"};double[] w={3,3,2.5,2,2,2.5,.6,1.6};double s=0;for(double q:w)s+=q;double r=R.nextDouble()*s;int i=0;while(i<w.length-1&&(r-=w[i])>0)i++;
  if(K[i].equals("quick")){quick();return;}routine(K[i]);}
 void quick(){int q=R.nextInt(3);if(q==0){face=R.nextBoolean()?1:-1;cq.add(sy(seg("wave","once",0),"hi"));}
  else if(q==1){rt.add(new Object[]{"edge",null});tx=R.nextBoolean()?-S*.35f:Wd()-S*.65f;state=WALK;vel=0;rt.add(D(sy(seg("watch","loop",U(3,6)),"peek")));}
  else{cq.add(sy(seg("ball","once",0),"giggle"));}}
 /* ---------- main loop ---------- */
 final Runnable tick=new Runnable(){public void run(){if(v==null||!screenOn)return;long t=SystemClock.uptimeMillis();float dt=Math.min(.12f,(t-lastT)/1000f);lastT=t;long next=500;
  try{if(touching){next=100;}
   else if(!ready.contains("watch")){next=1000;if(t>until){until=t+60000;sayText("মামণি আসছে… (ছবি নামছে)",3000);}}
   else if(state==WALK){next=walk(dt);}
   else if(state==DROP){vy+=S*6*dt;y=Math.min(groundY(),y+vy*dt);show3("watch",14);place();if(y>=groundY()){y=groundY();place();state=WALK;}next=33;}
   else if(!cq.isEmpty()){Seg s=cq.peek();if(s.say!=null){say(s.say);s.say=null;}if(s.fm){s.fm=false;face=x<(Wd()-S)/2f?1:-1;}
    if(s.i>=s.fr.length){cq.poll();next=1;}else{show3(s.c,s.fr[s.i]);s.i+=low()&&s.i+1<s.fr.length?2:1;if("zzz".equals(s.prop)&&s.i%40==0)sayText("z z Z",1500);next=1000/s.fps*(low()?2:1);}}
   else if(state==SLEEP){if(t>sleepUntil&&!night())wake();else cq.add(pr(seg("sleep","loop",60),"zzz"));next=1;}
   else if(!rt.isEmpty()&&state!=PIN){Object[] st=rt.get(0);if("edge".equals(st[0])){rt.remove(0);}else nextStep();next=1;}
   else if(state==PIN){if(t>until){state=DROP;vy=0;routine("stroll");rt.remove(0);tx=(float)(R.nextDouble()*(Wd()-S));}else cq.add(R.nextInt(3)==0?fm(seg("wave","once",0)):seg("watch","loop",U(6,12)));next=1;}
   else if(t>until&&all3()){choose();until=t+2000;next=1;}
   else{cq.add(seg("watch","loop",6));next=1;}}
  catch(Exception e){android.util.Log.w("girl","tick",e);next=1000;}
  h.postDelayed(this,Math.max(1,next));}};
 long walk(float dt){float W=Wd()-S;float H=S*.8f,vm=H*.42f;float dx=tx-x;
  if(Math.abs(dx)<3){x=tx;vel=0;place();state=PERCH;until=SystemClock.uptimeMillis()+4000;return 1;}
  face=dx>0?1:-1;vel=Math.min(vm,Math.min(vel+vm*dt/.6f,(float)Math.sqrt(2*(vm/.8f)*Math.abs(dx))+4));x+=face*Math.min(Math.abs(dx),vel*dt);
  wph=(wph+dt*12*vel/(H*.42f))%28;show3("walk",36+(int)wph);place();return low()?125:83;}
 /* ---------- commands from the panel ---------- */
 public void cmd(String c,String a){switch(c){
  case "fly":case "walk":wake();cq.clear();routine("stroll");break;case "sit":wake();cq.clear();routine("read");break;case "forage":case "play":wake();cq.clear();routine("play");break;
  case "sing":wake();cq.clear();cq.add(sy(seg("wave","once",0),"hi"));break;case "sleep":if(state==SLEEP)wake();else{cq.clear();rt.clear();goSleep(180);}break;
  case "happy":if(state!=SLEEP&&state!=WALK&&cq.size()<2){Seg s=seg("wave","once",0);s.say="happy";cq.addFirst(s);}break;
  case "think":case "sad":break;
  case "size":if(a.matches("small|medium|large")){P().edit().putString("gsize",a).apply();restart();}break;
  case "lowfps":P().edit().putBoolean("lowfps",!low()).apply();break;case "fshide":P().edit().putBoolean("fshide",!P().getBoolean("fshide",false)).apply();break;
  case "mascot":P().edit().putString("mascot",a.equals("doyel")?"doyel":"girl").apply();Link.startMascot(this);if(a.equals("doyel"))stopSelf();break;
  case "hide":P().edit().putBoolean("bubble",false).apply();stopSelf();break;
  case "tip":if(a!=null&&!a.isEmpty())sayText("💡 "+a,10000);break;
  default:break;}}
 void restart(){try{wm.removeView(v);wm.removeView(bub);}catch(Exception e){}v=null;cache.evictAll();h.removeCallbacks(tick);show();}
 public String status(){try{return new JSONObject().put("state",state==SLEEP?"sleep":state==PIN?"pinned":state==WALK?"walk":"perch").put("net",1).put("mbps",0).put("speed",2).put("sound",false)
  .put("roam",true).put("paused",Link.paused(this)).put("frames",ready.size()).toString();}catch(Exception e){return "{}";}}
 public static void copied(String s){GirlService g=I;if(g!=null&&g.coach!=null)g.coach.copied(s);}
}
