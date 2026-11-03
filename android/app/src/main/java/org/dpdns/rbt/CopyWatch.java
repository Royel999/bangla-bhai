package org.dpdns.rbt;
import android.accessibilityservice.AccessibilityService;import android.view.accessibility.AccessibilityEvent;import android.content.*;
public class CopyWatch extends AccessibilityService{long lastT;
 public void onAccessibilityEvent(AccessibilityEvent e){if(Link.paused(this)||!Link.p(this).getBoolean("a11y_consent",false))return;
  if(e.getEventType()!=AccessibilityEvent.TYPE_VIEW_CLICKED)return;String t=(String.valueOf(e.getText())+" "+e.getContentDescription()).toLowerCase();
  if(!(t.contains("copy")||t.contains("কপি")))return;long n=System.currentTimeMillis();if(n-lastT<1500)return;lastT=n;
  new android.os.Handler(getMainLooper()).postDelayed(()->{try{startActivity(new Intent(this,ClipActivity.class).setAction("auto").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_NO_ANIMATION));}catch(Exception x){}},350);}
 public void onInterrupt(){}}
