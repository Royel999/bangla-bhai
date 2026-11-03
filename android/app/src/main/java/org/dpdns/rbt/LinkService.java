package org.dpdns.rbt;
import android.app.*;import android.content.*;import android.os.*;import okhttp3.*;import org.json.*;import java.util.*;import java.util.concurrent.TimeUnit;import androidx.work.*;
public class LinkService extends Service{
 static final String CH="rbt_link";static String state="সংযোগ হচ্ছে…";WebSocket ws;Handler h;int delay=1;boolean stop;final Set<String> done=new HashSet<>();PowerManager.WakeLock wl;
 public IBinder onBind(Intent i){return null;}
 public void onCreate(){super.onCreate();h=new Handler(Looper.getMainLooper());NotificationManager nm=getSystemService(NotificationManager.class);
  nm.createNotificationChannel(new NotificationChannel(CH,"রয়েল লিংক",NotificationManager.IMPORTANCE_LOW));
  WorkManager.getInstance(this).enqueueUniquePeriodicWork("rbt_watch",ExistingPeriodicWorkPolicy.KEEP,new PeriodicWorkRequest.Builder(Watchdog.class,15,TimeUnit.MINUTES).build());}
 PendingIntent pi(Class<?> k,String a,int rq,boolean act){Intent i=new Intent(this,k).setAction(a);return act?PendingIntent.getActivity(this,rq,i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),PendingIntent.FLAG_IMMUTABLE):PendingIntent.getBroadcast(this,rq,i,PendingIntent.FLAG_IMMUTABLE);}
 Notification notif(){return new Notification.Builder(this,CH).setSmallIcon(R.drawable.seal).setContentTitle("🐯 রয়েল বেঙ্গল টাইগার").setContentText(state).setOngoing(true)
  .setContentIntent(pi(MainActivity.class,"open",1,true)).addAction(new Notification.Action.Builder(null,"📋 ক্লিপ রাখুন",pi(ClipActivity.class,"save",2,true)).build())
  .addAction(new Notification.Action.Builder(null,"📝 নোট",pi(QuickActivity.class,"note",3,true)).build())
  .addAction(new Notification.Action.Builder(null,Link.paused(this)?"▶ চালু":"⏸ বিরতি",pi(ActionReceiver.class,"pause",4,false)).build()).build();}
 void set(String s){state=s;try{getSystemService(NotificationManager.class).notify(7,notif());}catch(Exception e){}}
 public int onStartCommand(Intent i,int f,int id){
  if(Build.VERSION.SDK_INT>=29)startForeground(7,notif(),android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);else startForeground(7,notif());
  if(i!=null&&"refresh".equals(i.getAction())){set(state);return START_STICKY;}
  if(wl==null){wl=getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"rbt:link");}
  if(ws==null){stop=false;new Thread(this::connect).start();}return START_STICKY;}
 void connect(){try{String st=Link.status(this);
   if(st.equals("unpaired")||st.equals("unknown")){Link.pair(this);st="pending";}
   if(st.equals("denied")||st.equals("revoked")){set("❌ অনুমতি বাতিল — অ্যাপ খুলে আবার যুক্ত করুন");ws=null;return;}
   if(st.equals("pending")){set("⏳ অনুমোদনের অপেক্ষা — ডিভাইস ও অনুমতি পাতায় Approve দিন");retry(10);return;}
   if(st.equals("offline")){set("🔌 ইন্টারনেট নেই — আবার চেষ্টা হবে");retry(0);return;}
   Request r=new Request.Builder().url(Link.BASE.replace("https","wss")+"/bb/link/ws?token="+Link.tok(this)).header("User-Agent","RoyalLink-Android/1.0").build();
   ws=Link.HTTP.newWebSocket(r,new WebSocketListener(){
    public void onOpen(WebSocket w,Response x){delay=1;set("✅ যুক্ত আছে");}
    public void onMessage(WebSocket w,String m){onMsg(w,m);}
    public void onClosed(WebSocket w,int c,String s){down();}
    public void onFailure(WebSocket w,Throwable t,Response x){down();}});
  }catch(Exception e){set("🔌 সংযোগ হয়নি — আবার চেষ্টা হবে");retry(0);}}
 void down(){ws=null;if(stop)return;set("🔌 সংযোগ কেটেছে — আবার যুক্ত হচ্ছে");retry(0);}
 void retry(int fixed){int d=fixed>0?fixed:delay;delay=Math.min(delay*2,60);h.postDelayed(()->{if(ws==null&&!stop)new Thread(this::connect).start();},d*1000L);}
 void send(WebSocket w,JSONObject o){try{w.send(o.toString());}catch(Exception e){}}
 void onMsg(WebSocket w,String m){try{JSONObject j=new JSONObject(m);String t=j.optString("type");
  if(t.equals("ping")){send(w,new JSONObject().put("type","pong").put("t",j.opt("t")));return;}
  if(t.equals("hello")||t.equals("live")||t.equals("pong"))return;
  String cid=j.optString("cid","");if(cid.isEmpty()||done.contains(cid))return;done.add(cid);if(done.size()>500)done.clear();
  send(w,new JSONObject().put("type","ack").put("cid",cid));String a=j.optString("action");JSONObject g=j.optJSONObject("args");if(g==null)g=new JSONObject();
  set("⚙️ কাজ করছে: "+a);send(w,new JSONObject().put("type","step").put("cid",cid).put("phase","running").put("text",a));
  JSONObject res=act(a,g);send(w,new JSONObject().put("type","step").put("cid",cid).put("phase",res.has("error")?"error":"done").put("text",res.optString("error","")));
  send(w,new JSONObject().put("cid",cid).put("result",res));set("✅ যুক্ত আছে");}catch(Exception e){}}
 JSONObject act(String a,JSONObject g)throws Exception{JSONObject r=new JSONObject();
  switch(a){
   case "device_info":{BatteryManager b=getSystemService(BatteryManager.class);return r.put("text",Build.MANUFACTURER+" "+Build.MODEL+", Android "+Build.VERSION.RELEASE+", ব্যাটারি "+b.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)+"%");}
   case "notify":{getSystemService(NotificationManager.class).notify(100+new Random().nextInt(900),new Notification.Builder(this,CH).setSmallIcon(R.drawable.seal).setContentTitle(g.optString("title","🐯 রয়েল বার্তা")).setContentText(g.optString("text","")).setStyle(new Notification.BigTextStyle().bigText(g.optString("text",""))).build());return r.put("text","notified");}
   case "open_url":{startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse(g.getString("url"))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));return r.put("text","opened");}
   case "set_clipboard":{String s=g.optString("text");h.post(()->((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("rbt",s)));return r.put("text","copied");}
   case "vibrate":{getSystemService(Vibrator.class).vibrate(VibrationEffect.createOneShot(400,255));return r.put("text","vibrated");}
   default:return r.put("error","Android অ্যাপে এই কাজ এখনো নেই: "+a);}}
 public void onDestroy(){stop=true;if(ws!=null)ws.close(1000,"bye");super.onDestroy();}
}
