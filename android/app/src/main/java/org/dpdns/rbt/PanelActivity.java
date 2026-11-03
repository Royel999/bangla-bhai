package org.dpdns.rbt;
import android.app.Activity;import android.content.*;import android.graphics.Color;import android.os.*;import android.webkit.*;import android.Manifest;import android.content.pm.PackageManager;
/* Glass control panel: same panel.html as web/Windows, bridged through the "RBT" JS interface. */
public class PanelActivity extends Activity{WebView w;final Handler h=new Handler(Looper.getMainLooper());
 protected void onCreate(Bundle b){super.onCreate(b);w=new WebView(this);w.setBackgroundColor(Color.TRANSPARENT);WebSettings s=w.getSettings();s.setJavaScriptEnabled(true);s.setDomStorageEnabled(true);s.setMediaPlaybackRequiresUserGesture(false);
  w.addJavascriptInterface(new Bridge(),"RBT");w.setWebViewClient(new WebViewClient());
  w.setWebChromeClient(new WebChromeClient(){public void onPermissionRequest(PermissionRequest r){h.post(()->{
   if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},7);r.deny();}else r.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});});}});
  setContentView(w);w.loadUrl(Link.BASE+"/bb/static/notes/panel.html?m=and&v=1");}
 public void onBackPressed(){finish();}
 class Bridge{
  @JavascriptInterface public String token(){return Link.tok(PanelActivity.this);}
  @JavascriptInterface public void bird(String c,String a){h.post(()->{BubbleService s=BubbleService.I;if(s!=null)s.cmd(c,a);else if("hide".equals(c)){}});}
  @JavascriptInterface public String status(){BubbleService s=BubbleService.I;return s!=null?s.status():"{\"state\":\"off\",\"net\":null,\"speed\":2,\"sound\":false,\"roam\":false,\"paused\":"+Link.paused(PanelActivity.this)+"}";}
  @JavascriptInterface public String clipboard(){final String[] r={""};final Object lock=new Object();
   h.post(()->{try{ClipboardManager cm=(ClipboardManager)getSystemService(CLIPBOARD_SERVICE);ClipData d=cm.getPrimaryClip();r[0]=d!=null&&d.getItemCount()>0?String.valueOf(d.getItemAt(0).coerceToText(PanelActivity.this)):"";}catch(Exception e){}synchronized(lock){lock.notify();}});
   synchronized(lock){try{lock.wait(1500);}catch(Exception e){}}return r[0];}
  @JavascriptInterface public void copy(String t){h.post(()->((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("rbt",t)));}
  @JavascriptInterface public void open(String u){h.post(()->{try{startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse(u)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}catch(Exception e){}});}
  @JavascriptInterface public void close(){h.post(()->finish());}
  @JavascriptInterface public String screenshot(){return "";}}}
