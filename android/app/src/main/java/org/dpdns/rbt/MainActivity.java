package org.dpdns.rbt;
import android.app.*;import android.content.*;import android.net.Uri;import android.os.*;import android.provider.Settings;import android.widget.*;import android.graphics.Color;
public class MainActivity extends Activity{TextView st;
 protected void onCreate(Bundle b){super.onCreate(b);Link.p(this).edit().putBoolean("enabled",true).apply();if(Build.VERSION.SDK_INT>=33)requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},1);Link.start(this);
  LinearLayout r=new LinearLayout(this);r.setOrientation(1);r.setPadding(40,60,40,40);r.setBackgroundColor(Color.parseColor("#FFF8EE"));
  ImageView iv=new ImageView(this);iv.setImageResource(R.drawable.seal);r.addView(iv,new LinearLayout.LayoutParams(-1,300));
  TextView t=new TextView(this);t.setText("রয়েল বেঙ্গল টাইগার — অ্যান্ড্রয়েড লিংক");t.setTextSize(20);t.setGravity(1);r.addView(t);
  st=new TextView(this);st.setPadding(0,20,0,20);st.setGravity(1);r.addView(st);
  btn(r,"🔋 ব্যাটারি সীমা তুলে দিন (পেছনে চালু রাখতে)",()->{PowerManager pm=getSystemService(PowerManager.class);if(pm.isIgnoringBatteryOptimizations(getPackageName()))toast("আগেই করা আছে ✓");else startActivity(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,Uri.parse("package:"+getPackageName())));});
  btn(r,"👧 ভাসমান সঙ্গী (মামণি) চালু/বন্ধ",()->{if(!Settings.canDrawOverlays(this)){toast("“অন্য অ্যাপের উপরে দেখান” অনুমতি দিন");startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,Uri.parse("package:"+getPackageName())));return;}
   boolean on=!Link.p(this).getBoolean("bubble",false);Link.p(this).edit().putBoolean("bubble",on).apply();if(on)Link.startMascot(this);else Link.stopMascots(this);toast(on?"সঙ্গী চালু":"সঙ্গী বন্ধ");});
  btn(r,"🎭 মামণি ⇄ দোয়েল বদলান",()->{boolean g=Link.girl(this);Link.p(this).edit().putString("mascot",g?"doyel":"girl").putBoolean("bubble",true).apply();Link.startMascot(this);toast(g?"🐦 দোয়েল":"👧 মামণি");});
  btn(r,"📏 মামণির আকার (ছোট/মাঝারি/বড়)",()->{String[] z={"small","medium","large"};String c=Link.p(this).getString("gsize","medium");String n=z[(java.util.Arrays.asList(z).indexOf(c)+1)%3];Link.p(this).edit().putString("gsize",n).apply();Link.mascotCmd("size",n);toast("আকার: "+(n.equals("small")?"ছোট":n.equals("large")?"বড়":"মাঝারি"));});
  btn(r,"🔋 কম FPS (ব্যাটারি বাঁচাও) চালু/বন্ধ",()->{boolean b2=!Link.p(this).getBoolean("lowfps",false);Link.p(this).edit().putBoolean("lowfps",b2).apply();toast(b2?"কম FPS চালু":"স্বাভাবিক FPS");});
  btn(r,"🎬 ফুলস্ক্রিন অ্যাপে লুকাও চালু/বন্ধ",()->{boolean b2=!Link.p(this).getBoolean("fshide",false);Link.p(this).edit().putBoolean("fshide",b2).apply();toast(b2?"ভিডিও/গেমে লুকাবে":"সবসময় দেখাবে");});
  btn(r,"💡 কাজের পরামর্শ: Usage Access (ঐচ্ছিক)",()->new AlertDialog.Builder(this).setTitle("ঐচ্ছিক অনুমতি").setMessage("মামণি শুধু কোন অ্যাপ সামনে খোলা আছে তার নাম দেখবে — স্ক্রিনের লেখা বা টাইপ করা কিছুই না। ব্যাংক, বিকাশ, নগদ, পাসওয়ার্ড অ্যাপ পুরো বাদ। যা শেখে তা শুধু এই ফোনে থাকে; প্যানেল → সঙ্গী থেকে থামানো/মুছে ফেলা যায়। পরামর্শ সর্বোচ্চ ১০ মিনিটে একটি।\n\nরাজি থাকলে পরের পাতায় «রয়েল বেঙ্গল টাইগার» চালু করুন।")
   .setPositiveButton("রাজি",(d,w)->startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))).setNegativeButton("না",null).show());
  btn(r,"🧠 শেখা ডেটা মুছুন",()->{Coach.delete(this);toast("মুছে ফেলা হলো");});
  btn(r,"🌀 বাবল ঘোরা থামান / ঘোরান",()->{startForegroundService(new Intent(this,BubbleService.class).setAction("roam"));toast(Link.p(this).getBoolean("roam",true)?"থামছে":"ঘুরবে");});
  btn(r,"⚡ ঘোরার গতি (ধীর/মাঝারি/দ্রুত)",()->{int s=Link.p(this).getInt("roam_speed",2)%3+1;Link.p(this).edit().putInt("roam_speed",s).apply();toast("গতি: "+new String[]{"","ধীর","মাঝারি","দ্রুত"}[s]);});
  btn(r,"📋 এখনকার ক্লিপ রাখুন",()->startActivity(new Intent(this,ClipActivity.class).setAction("save")));
  btn(r,"📝 দ্রুত নোট ও সাম্প্রতিক ক্লিপ",()->startActivity(new Intent(this,QuickActivity.class)));
  btn(r,"⏸ কপি-ধরা বিরতি / চালু",()->{boolean p=!Link.paused(this);Link.p(this).edit().putBoolean("paused",p).apply();toast(p?"বিরতিতে":"চালু");refresh();});
  btn(r,"👆 স্বয়ংক্রিয় কপি-ধরা (Accessibility)",()->new AlertDialog.Builder(this).setTitle("অনুমতি চাই").setMessage(getString(R.string.a11y)+"\n\nরাজি থাকলে পরের পাতায় «রয়েল কপি-ধরা» চালু করুন।")
   .setPositiveButton("রাজি",(d,w)->{Link.p(this).edit().putBoolean("a11y_consent",true).apply();startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));})
   .setNegativeButton("না",(d,w)->Link.p(this).edit().putBoolean("a11y_consent",false).apply()).show());
  btn(r,"🌐 রয়েল নোটবুক খুলুন",()->startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(Link.BASE+"/notes/"))));
  btn(r,"🔄 নতুন করে যুক্ত করুন",()->{Link.p(this).edit().remove("token").remove("device").apply();stopService(new Intent(this,LinkService.class));Link.start(this);toast("নতুন অনুরোধ পাঠানো হলো — Approve দিন");});
  ScrollView sv=new ScrollView(this);sv.addView(r);setContentView(sv);}
 void btn(LinearLayout r,String s,Runnable a){Button b=new Button(this);b.setText(s);b.setAllCaps(false);b.setOnClickListener(x->a.run());r.addView(b);}
 void toast(String s){Toast.makeText(this,s,0).show();}
 protected void onResume(){super.onResume();refresh();}
 public void onWindowFocusChanged(boolean f){super.onWindowFocusChanged(f);if(f)try{ClipData d=((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).getPrimaryClip();if(d!=null&&d.getItemCount()>0)Link.saveClip(this,String.valueOf(d.getItemAt(0).coerceToText(this)),false);}catch(Exception e){}}
 void refresh(){st.setText(LinkService.state+"\nডিভাইস: "+Link.p(this).getString("device","—")+(Link.paused(this)?"\n⏸ কপি-ধরা বিরতিতে":""));}}
