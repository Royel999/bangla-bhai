package org.dpdns.rbt;
import android.app.*;import android.app.usage.*;import android.content.*;import android.content.pm.*;import android.os.*;import org.json.*;import java.io.*;import java.util.*;import java.util.regex.Pattern;
/* Phone work-buddy. Uses ONLY the foreground app name, and only if the user granted Usage Access (optional). Never reads screen contents or typing.
   Banking / bKash / Nagad / password / authenticator apps are skipped entirely. Everything learned stays in the app's private storage (files/learn). */
public class Coach{
 final GirlService g;final Handler h=new Handler(Looper.getMainLooper());final File L;boolean on=true;String app,label;long tApp,tScreen=SystemClock.elapsedRealtime(),tTip,tIns;int n;
 static final Pattern PRIV=Pattern.compile("bank|bkash|nagad|upay|rocket|dbbl|pay|wallet|password|passwd|authenticator|vault|keepass|bitwarden|lastpass|1password|otp|ব্যাংক|বিকাশ|নগদ",2);
 Coach(GirlService g){this.g=g;L=new File(g.getFilesDir(),"learn");L.mkdirs();tTip=SystemClock.elapsedRealtime()-5*60000;h.postDelayed(loop,20000);}
 void stop(){on=false;h.removeCallbacksAndMessages(null);}
 void screen(boolean s){if(s){tScreen=SystemClock.elapsedRealtime();h.removeCallbacks(loop);h.postDelayed(loop,20000);}else h.removeCallbacks(loop);}
 static JSONObject cfg(Context c){try{return new JSONObject(read(new File(new File(c.getFilesDir(),"learn"),"settings.json")));}catch(Exception e){return new JSONObject();}}
 static String read(File f)throws IOException{return new String(java.nio.file.Files.readAllBytes(f.toPath()),"UTF-8");}
 void log(String f,JSONObject o){if(cfg(g).optBoolean("pause"))return;try(FileWriter w=new FileWriter(new File(L,f),true)){w.write(o.toString()+"\n");}catch(Exception e){}}
 static boolean usageOk(Context c){try{AppOpsManager a=c.getSystemService(AppOpsManager.class);return a.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS,android.os.Process.myUid(),c.getPackageName())==AppOpsManager.MODE_ALLOWED;}catch(Exception e){return false;}}
 boolean canTip(){JSONObject c=cfg(g);long gap=(long)(Math.max(3,Math.min(60,c.optDouble("gap",10)))*60000);return !c.optBoolean("quiet")&&SystemClock.elapsedRealtime()-tTip>gap&&g.state!=GirlService.SLEEP;}
 void tip(String t,String kind){tTip=SystemClock.elapsedRealtime();try{log("tips.jsonl",new JSONObject().put("t",System.currentTimeMillis()/1000.0).put("kind",kind).put("app",label).put("text",t));}catch(Exception e){}h.post(()->g.cmd("tip",t));}
 String fg(){UsageStatsManager u=g.getSystemService(UsageStatsManager.class);long now=System.currentTimeMillis();UsageEvents ev=u.queryEvents(now-120000,now);UsageEvents.Event e=new UsageEvents.Event();String last=null;
  while(ev.hasNextEvent()){ev.getNextEvent(e);if(e.getEventType()==UsageEvents.Event.ACTIVITY_RESUMED)last=e.getPackageName();}return last;}
 String lbl(String p){try{PackageManager pm=g.getPackageManager();return String.valueOf(pm.getApplicationLabel(pm.getApplicationInfo(p,0)));}catch(Exception e){return p;}}
 final Runnable loop=new Runnable(){public void run(){if(!on)return;try{step();}catch(Exception e){android.util.Log.w("coach","step",e);}h.postDelayed(this,20000);}};
 void step()throws Exception{long now=SystemClock.elapsedRealtime();
  if(now-tScreen>45*60000&&canTip()){tScreen=now;tip(new String[]{"আব্বু, অনেকক্ষণ ফোন দেখছো — একটু চোখ বিশ্রাম দাও 👀","উঠে একটু হাঁটো, পানি খাও 💧"}[(int)(Math.random()*2)],"break");return;}
  if(!usageOk(g))return;String p=fg();if(p==null||p.equals(g.getPackageName()))return;
  boolean priv=PRIV.matcher(p).find();String lb=priv?"[private]":lbl(p);if(!priv&&PRIV.matcher(lb).find()){priv=true;lb="[private]";}
  if(!p.equals(app)){if(app!=null)log("apps.jsonl",new JSONObject().put("t0",tApp/1000.0).put("t1",System.currentTimeMillis()/1000.0).put("app",label));app=p;label=lb;tApp=System.currentTimeMillis();return;}
  if(now-tIns>3600000){tIns=now;insights();}
  if(priv||System.currentTimeMillis()-tApp<180000||!canTip())return;
  String loc=local(p);n++;
  if(loc!=null&&n%2==1){tip(loc,"tip");return;}
  final String L2=lb,lc=loc;new Thread(()->{try{JSONObject r=Link.post("/bb/link/assist",new JSONObject().put("token",Link.tok(g)).put("kind","tip").put("app",L2).put("title","(Android ফোন)").put("mins",(System.currentTimeMillis()-tApp)/60000));
    String t=r.optString("tip","");if(!t.isEmpty())tip(t,"tip");else if(lc!=null)tip(lc,"tip");}catch(Exception e){if(lc!=null)tip(lc,"tip");}}).start();}
 String local(String p){p=p.toLowerCase(Locale.US);String[] a=null;
  if(p.contains("gm")||p.contains("mail")||p.contains("outlook"))a=new String[]{"ভদ্র উত্তর: \"আপনার মেইলের জন্য ধন্যবাদ। বিষয়টি দেখে আজকের মধ্যেই জানাচ্ছি।\"","লম্বা মেইল? প্যানেলের AI-কে বলো ছোট করে উত্তর লিখে দিতে"};
  else if(p.contains("sheets")||p.contains("excel"))a=new String[]{"খোঁজার সূত্র: =XLOOKUP(A2, B:B, C:C, \"নেই\")","শর্ত দিয়ে যোগ: =SUMIFS(C:C, A:A, \"ঢাকা\")","ভুল লুকাতে: =IFERROR(সূত্র, \"\")"};
  else if(p.contains("docs")||p.contains("word"))a=new String[]{"কীবোর্ডের 🎤 চাপলে বাংলায় বলে লেখা যায়","লেখা কপি করলে আমি নোটবুকে রেখে দেবো"};
  else if(p.contains("chrome")||p.contains("browser"))a=new String[]{"পেজের ⋮ → 'Translate' দিয়ে বাংলায় পড়া যায়","দরকারি লিংক কপি করলে নোটবুকে রেখে দিই"};
  else if(p.contains("facebook")||p.contains("youtube")||p.contains("tiktok")||p.contains("instagram"))a=new String[]{"অনেকক্ষণ স্ক্রল হচ্ছে — একটু বিরতি নেবে? 🙂","কাজের ভিডিও হলে লিংক কপি করো, নোটে রেখে দেবো"};
  else if(p.contains("whatsapp")||p.contains("messenger")||p.contains("telegram"))a=new String[]{"ভদ্র উত্তর: \"ধন্যবাদ, একটু পরে জানাচ্ছি।\"","লম্বা মেসেজ? 🎤 দিয়ে বলে লিখে ফেলো"};
  return a==null?null:a[(int)(Math.random()*a.length)];}
 void copied(String s){new Thread(()->{try{if(cfg(g).optBoolean("pause")||"[private]".equals(label))return;String k=Integer.toHexString(s.trim().hashCode());File f=new File(L,"copies.json");
   JSONObject d;try{d=new JSONObject(read(f));}catch(Exception e){d=new JSONObject();}JSONObject e=d.optJSONObject(k);if(e==null)e=new JSONObject().put("n",0).put("p",s.trim().replace('\n',' ').substring(0,Math.min(60,s.trim().length())));
   e.put("n",e.optInt("n")+1).put("t",System.currentTimeMillis()/1000.0);d.put(k,e);try(FileWriter w=new FileWriter(f)){w.write(d.toString());}
   if(e.optInt("n")==3&&canTip())tip("এটা ৩ বার কপি করলে — স্নিপেট হিসেবে নোটে রাখি? প্যানেল → সঙ্গী → শেখা","auto");}catch(Exception x){}}).start();}
 void insights(){try{JSONArray out=new JSONArray();Map<String,Set<Integer>> hr=new HashMap<>();
   try(BufferedReader b=new BufferedReader(new FileReader(new File(L,"apps.jsonl")))){String ln;while((ln=b.readLine())!=null){JSONObject o=new JSONObject(ln);if("[private]".equals(o.optString("app")))continue;
     Calendar c=Calendar.getInstance(TimeZone.getTimeZone("Asia/Dhaka"));c.setTimeInMillis((long)(o.getDouble("t0")*1000));String key=o.optString("app")+"|"+c.get(Calendar.HOUR_OF_DAY);
     hr.computeIfAbsent(key,z->new HashSet<>()).add(c.get(Calendar.DAY_OF_YEAR));}}catch(Exception e){}
   for(Map.Entry<String,Set<Integer>> en:hr.entrySet())if(en.getValue().size()>=3){String[] a=en.getKey().split("\\|");out.put(new JSONObject().put("id","open:"+en.getKey()).put("kind","open").put("text","প্রতিদিন প্রায় "+a[1]+"টায় "+a[0]+" খোলো — তখন মনে করিয়ে দেবো?"));}
   try{JSONObject d=new JSONObject(read(new File(L,"copies.json")));for(Iterator<String> it=d.keys();it.hasNext();){String k=it.next();JSONObject e=d.getJSONObject(k);if(e.optInt("n")>=3)out.put(new JSONObject().put("id","snip:"+k).put("kind","snippet").put("text","বারবার কপি: \""+e.optString("p")+"\" — স্নিপেট বানাও").put("p",e.optString("p")));}}catch(Exception e){}
   try(FileWriter w=new FileWriter(new File(L,"insights.json"))){w.write(out.toString());}}catch(Exception e){}}
 /* panel bridge helpers */
 static String state(Context c){File L=new File(c.getFilesDir(),"learn");JSONObject o=new JSONObject();try{o.put("settings",cfg(c));o.put("usage",usageOk(c));
   JSONArray tips=new JSONArray();try{List<String> ls=java.nio.file.Files.readAllLines(new File(L,"tips.jsonl").toPath());for(int i=ls.size()-1;i>=0&&i>=ls.size()-6;i--)tips.put(new JSONObject(ls.get(i)));}catch(Exception e){}o.put("tips",tips);
   try{o.put("insights",new JSONArray(read(new File(L,"insights.json"))));}catch(Exception e){o.put("insights",new JSONArray());}
   Map<String,Double> m=new LinkedHashMap<>();int n=0;try{Calendar now=Calendar.getInstance();for(String ln:java.nio.file.Files.readAllLines(new File(L,"apps.jsonl").toPath())){n++;JSONObject a=new JSONObject(ln);
     Calendar c2=Calendar.getInstance();c2.setTimeInMillis((long)(a.getDouble("t0")*1000));if(c2.get(Calendar.DAY_OF_YEAR)==now.get(Calendar.DAY_OF_YEAR))m.merge(a.optString("app"),(a.getDouble("t1")-a.getDouble("t0"))/60,Double::sum);}}catch(Exception e){}
   JSONArray apps=new JSONArray();m.entrySet().stream().sorted((p,q)->Double.compare(q.getValue(),p.getValue())).limit(6).forEach(en->{if(en.getValue()>=1)apps.put(new JSONArray().put(en.getKey()).put(en.getValue().intValue()));});
   o.put("apps",apps).put("n",n);}catch(Exception e){}return o.toString();}
 static boolean set(Context c,String k,String v){if(!k.matches("pause|quiet|gap"))return false;try{File L=new File(c.getFilesDir(),"learn");L.mkdirs();JSONObject o=cfg(c);
   if(k.equals("gap"))o.put(k,Double.parseDouble(v));else o.put(k,Boolean.parseBoolean(v));try(FileWriter w=new FileWriter(new File(L,"settings.json"))){w.write(o.toString());}return true;}catch(Exception e){return false;}}
 static boolean delete(Context c){File L=new File(c.getFilesDir(),"learn");for(String f:new String[]{"apps.jsonl","tips.jsonl","copies.json","insights.json"})new File(L,f).delete();return true;}
}
