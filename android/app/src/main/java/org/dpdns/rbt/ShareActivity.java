package org.dpdns.rbt;
import android.app.Activity;import android.content.Intent;import android.os.Bundle;
public class ShareActivity extends Activity{protected void onCreate(Bundle b){super.onCreate(b);Intent i=getIntent();CharSequence s=Intent.ACTION_PROCESS_TEXT.equals(i.getAction())?i.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT):i.getStringExtra(Intent.EXTRA_TEXT);
 String sub=i.getStringExtra(Intent.EXTRA_SUBJECT);Link.saveClip(this,(sub!=null&&s!=null&&!String.valueOf(s).contains(sub)?sub+"\n":"")+(s==null?"":s),true);finish();}}
