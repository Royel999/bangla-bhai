package org.dpdns.rbt;
import android.app.Activity;import android.content.*;import android.os.*;import android.widget.*;import android.view.*;import org.json.*;
public class QuickActivity extends Activity{LinearLayout list;
 protected void onCreate(Bundle b){super.onCreate(b);setTitle("🐯 রয়েল নোটবুক");LinearLayout r=new LinearLayout(this);r.setOrientation(1);r.setPadding(32,16,32,16);
  EditText et=new EditText(this);et.setHint("দ্রুত নোট লিখুন…");et.setMinLines(3);r.addView(et);
  LinearLayout row=new LinearLayout(this);Button s=new Button(this);s.setText("📝 নোট রাখুন");s.setOnClickListener(x->{if(et.getText().length()>0){Link.note(this,et.getText().toString());finish();}});
  Button c=new Button(this);c.setText("📋 ক্লিপ রাখুন");c.setOnClickListener(x->grab());Button o=new Button(this);o.setText("🌐 খুলুন");o.setOnClickListener(x->{startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse(Link.BASE+"/notes/")));finish();});
  row.addView(s);row.addView(c);row.addView(o);r.addView(row);TextView h=new TextView(this);h.setText("সাম্প্রতিক ক্লিপ (চাপলে কপি হবে)");h.setPadding(0,16,0,8);r.addView(h);
  list=new LinearLayout(this);list.setOrientation(1);ScrollView sv=new ScrollView(this);sv.addView(list);r.addView(sv,new LinearLayout.LayoutParams(-1,(int)(320*getResources().getDisplayMetrics().density)));setContentView(r);load();}
 void grab(){try{ClipData d=((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).getPrimaryClip();Link.saveClip(this,d!=null&&d.getItemCount()>0?String.valueOf(d.getItemAt(0).coerceToText(this)):"",true);}catch(Exception e){}new Handler().postDelayed(this::load,1500);}
 void load(){Handler h=new Handler(Looper.getMainLooper());new Thread(()->{try{JSONArray a=Link.get("/bb/link/clips?n=20&token="+Link.tok(this)).getJSONArray("clips");h.post(()->{list.removeAllViews();
   for(int i=0;i<a.length();i++){String t=a.optJSONObject(i).optString("content");TextView tv=new TextView(this);tv.setText("• "+(t.length()>140?t.substring(0,140)+"…":t));tv.setPadding(0,10,0,10);
    tv.setOnClickListener(x->{((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("rbt",t));Toast.makeText(this,"কপি হলো",0).show();});list.addView(tv);}
   if(a.length()==0){TextView tv=new TextView(this);tv.setText("এখনো কোনো ক্লিপ নেই");list.addView(tv);}});}catch(Exception e){h.post(()->{TextView tv=new TextView(this);tv.setText("ক্লিপ আনা যায়নি (ডিভাইস অনুমোদিত কি?)");list.addView(tv);});}}).start();}}
