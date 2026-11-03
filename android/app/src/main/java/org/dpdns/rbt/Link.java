package org.dpdns.rbt;
import android.content.*;import android.os.*;import android.widget.Toast;import java.util.regex.*;import okhttp3.*;import org.json.*;import java.util.concurrent.TimeUnit;
public class Link{
 public static final String BASE="https://banglabhai.dpdns.org";
 public static final OkHttpClient HTTP=new OkHttpClient.Builder().connectTimeout(15,TimeUnit.SECONDS).readTimeout(30,TimeUnit.SECONDS).pingInterval(20,TimeUnit.SECONDS).build();
 static final MediaType J=MediaType.get("application/json");
 public static SharedPreferences p(Context c){return c.getSharedPreferences("rbt",0);}
 public static String tok(Context c){return p(c).getString("token","");}
 public static boolean paused(Context c){return p(c).getBoolean("paused",false);}
 static Request.Builder rb(String path){return new Request.Builder().url(BASE+path).header("User-Agent","RoyalLink-Android/1.0");}
 public static JSONObject get(String path)throws Exception{try(Response r=HTTP.newCall(rb(path).build()).execute()){return new JSONObject(r.body().string());}}
 public static JSONObject post(String path,JSONObject b)throws Exception{try(Response r=HTTP.newCall(rb(path).post(RequestBody.create(b.toString(),J)).build()).execute()){return new JSONObject(r.body().string());}}
 public static String status(Context c){try{if(tok(c).isEmpty())return "unpaired";return get("/bb/link/status?token="+tok(c)).optString("status","unknown");}catch(Exception e){return "offline";}}
 public static void pair(Context c)throws Exception{JSONObject info=new JSONObject().put("os","android "+Build.VERSION.RELEASE).put("model",Build.MANUFACTURER+" "+Build.MODEL).put("ws",true).put("app","rbt-android");
  JSONObject r=post("/bb/link/pair",new JSONObject().put("name",Build.MODEL).put("kind","phone").put("info",info));p(c).edit().putString("device",r.getString("device")).putString("token",r.getString("token")).apply();}
 static final Pattern[] SENS={Pattern.compile("\\b\\d{4,8}\\b.{0,40}\\b(otp|code|কোড|পিন|pin|verification)\\b",2),Pattern.compile("\\b(otp|code|কোড|pin|verification)\\b.{0,40}\\b\\d{4,8}\\b",2),
  Pattern.compile("^\\s*\\d{4,8}\\s*$"),Pattern.compile("(?:\\d[ -]?){13,19}"),Pattern.compile("(password|passwd|pwd|পাসওয়ার্ড)\\s*[:=]",2),Pattern.compile("-----BEGIN [A-Z ]*PRIVATE KEY"),Pattern.compile("\\b(sk|pk|ghp|gho|xox[bpa]|AKIA)[-_A-Za-z0-9]{16,}")};
 public static boolean sensitive(String s){for(Pattern x:SENS)if(x.matcher(s).find())return true;return false;}
 static String last="";
 public static void saveClip(Context c,String s,boolean loud){if(s==null)return;s=s.trim();Handler h=new Handler(Looper.getMainLooper());Context a=c.getApplicationContext();
  if(s.isEmpty()){if(loud)h.post(()->Toast.makeText(a,"ক্লিপবোর্ড খালি",0).show());return;}
  if(paused(c)){if(loud)h.post(()->Toast.makeText(a,"কপি-ধরা বিরতিতে আছে",0).show());return;}
  if(sensitive(s)){if(loud)h.post(()->Toast.makeText(a,"🔒 গোপন তথ্য মনে হলো — রাখা হলো না",0).show());return;}
  if(s.equals(last)&&!loud)return;last=s;String t=s;
  new Thread(()->{String m;try{JSONObject r=post("/bb/link/clip",new JSONObject().put("token",tok(a)).put("kind",t.matches("^https?://\\S+$")?"url":"text").put("content",t));
   m=r.has("error")?"রাখা যায়নি: "+r.optString("error"):r.has("skipped")?"🔒 রাখা হলো না":r.optBoolean("dup")?"আগেই রাখা আছে ✓":"🐯 রয়েল নোটবুকে রাখা হলো";if(!r.has("error")&&!r.has("skipped")){GirlService.copied(t);h.post(()->mascotCmd("happy",""));}}catch(Exception e){m="সংযোগ নেই — রাখা যায়নি";}
   String mm=m;h.post(()->Toast.makeText(a,mm,0).show());}).start();}
 public static void note(Context c,String body){Context a=c.getApplicationContext();Handler h=new Handler(Looper.getMainLooper());new Thread(()->{String m;try{JSONObject r=post("/bb/link/note",new JSONObject().put("token",tok(a)).put("body",body));m=r.has("error")?"নোট রাখা যায়নি":"📒 নোট রাখা হলো";}catch(Exception e){m="সংযোগ নেই";}String mm=m;h.post(()->Toast.makeText(a,mm,0).show());}).start();}
 public static void start(Context c){Intent i=new Intent(c,LinkService.class);try{c.startForegroundService(i);}catch(Exception e){}
  if(p(c).getBoolean("bubble",false)&&android.provider.Settings.canDrawOverlays(c))startMascot(c);}
 public static boolean girl(Context c){return !"doyel".equals(p(c).getString("mascot","girl"));}
 public static void startMascot(Context c){try{if(girl(c)){c.stopService(new Intent(c,BubbleService.class));c.startForegroundService(new Intent(c,GirlService.class));}else{c.stopService(new Intent(c,GirlService.class));c.startForegroundService(new Intent(c,BubbleService.class));}}catch(Exception e){}}
 public static void stopMascots(Context c){c.stopService(new Intent(c,BubbleService.class));c.stopService(new Intent(c,GirlService.class));}
 public static void mascotCmd(String c,String a){if(GirlService.I!=null)GirlService.I.cmd(c,a);else if(BubbleService.I!=null)BubbleService.I.cmd(c,a);}
}
