package org.dpdns.rbt;
import android.app.Activity;import android.content.*;
public class ClipActivity extends Activity{boolean did;
 public void onWindowFocusChanged(boolean f){super.onWindowFocusChanged(f);if(!f||did)return;did=true;
  try{ClipboardManager cm=(ClipboardManager)getSystemService(CLIPBOARD_SERVICE);ClipData d=cm.getPrimaryClip();String s=d!=null&&d.getItemCount()>0?String.valueOf(d.getItemAt(0).coerceToText(this)):"";
   Link.saveClip(this,s,!"auto".equals(getIntent().getAction()));}catch(Exception e){}
  finish();overridePendingTransition(0,0);}}
