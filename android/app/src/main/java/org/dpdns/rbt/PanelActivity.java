package org.dpdns.rbt;
import android.app.Activity;import android.content.*;import android.graphics.Color;import android.os.*;import android.webkit.*;import android.Manifest;import android.content.pm.PackageManager;
/* Glass control panel: same panel.html as web/Windows, bridged through the "RBT" JS interface. */
public class PanelActivity extends Activity{WebView w;final Handler h=new Handler(Looper.getMainLooper());
 protected void onCreate(Bundle b){super.onCreate(b);w=new WebView(this);w.setBackgroundColor(Color.TRANSPARENT);WebSettings s=w.getSettings();s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);s.setMediaPlaybackRequiresUserGesture(false);
  w.addJavascriptInterface(new Bridge(),"RBT");w.setWebViewClient(new WebViewClient());
  w.setWebChromeClient(new WebChromeClient(){public void onPermissionRequest(PermissionRequest r){h.post(()->{
   if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},7);r.deny();}else r.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});});}});
  setContentView(w);w.loadUrl(Link.BASE+"/bb/static/notes/panel.html?m=and&v=2");}
 public void onBackPressed(){finish();}
 class Bridge{
  @JavascriptInterface public String token(){return Link.tok(PanelActivity.this);}
  @JavascriptInterface public void bird(String c,String a){h.post(()->{Link.mascotCmd(c,a);});}
  @JavascriptInterface public String status(){if(GirlService.I!=null)return GirlService.I.status();BubbleService s=BubbleService.I;return s!=null?s.status():"{\"state\":\"off\",\"net\":null,\"speed\":2,\"sound\":false,\"roam\":false,\"paused\":"+Link.paused(PanelActivity.this)+"}";}
  @JavascriptInterface public String clipboard(){final String[] r={""};final Object lock=new Object();
   h.post(()->{try{ClipboardManager cm=(ClipboardManager)getSystemService(CLIPBOARD_SERVICE);ClipData d=cm.getPrimaryClip();r[0]=d!=null&&d.getItemCount()>0?String.valueOf(d.getItemAt(0).coerceToText(PanelActivity.this)):"";}catch(Exception e){}synchronized(lock){lock.notify();}});
   synchronized(lock){try{lock.wait(1500);}catch(Exception e){}}return r[0];}
  @JavascriptInterface public void copy(String t){h.post(()->((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("rbt",t)));}
  @JavascriptInterface public void open(String u){h.post(()->{try{startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse(u)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}catch(Exception e){}});}
  @JavascriptInterface public void close(){h.post(()->finish());}
  @JavascriptInterface public String screenshot(){return "";}
  @JavascriptInterface public String learn_state(){return Coach.state(PanelActivity.this);}
  @JavascriptInterface public boolean learn_set(String k,String v){return Coach.set(PanelActivity.this,k,v);}
  @JavascriptInterface public boolean learn_delete(){return Coach.delete(PanelActivity.this);}}
 boolean clipDone;public void onWindowFocusChanged(boolean f){super.onWindowFocusChanged(f);if(f&&!clipDone){clipDone=true;try{ClipData d=((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).getPrimaryClip();if(d!=null&&d.getItemCount()>0)Link.saveClip(this,String.valueOf(d.getItemAt(0).coerceToText(this)),false);}catch(Exception e){}}}}
