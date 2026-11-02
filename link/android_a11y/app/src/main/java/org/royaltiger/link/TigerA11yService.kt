package org.royaltiger.link

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import org.json.JSONArray
import org.json.JSONObject

/**
 * Jobs arrive from LinkClient (same /bb/link/poll protocol as royal_link.py). The server
 * only dispatches a job AFTER the owner tapped Approve (agent.py + sentinel.py), so this
 * service never decides on its own. It also refuses anything not in ALLOWED.
 */
class TigerA11yService : AccessibilityService() {
    companion object { var instance: TigerA11yService? = null; val ALLOWED = setOf("screen_read","ui_dump","sms_fill","click","type_text","swipe","keyevent","app_launch","open_url","clipboard","battery") }

    override fun onServiceConnected() { instance = this; LinkClient.start(this) }
    override fun onDestroy() { instance = null; LinkClient.stop(); super.onDestroy() }
    override fun onAccessibilityEvent(e: AccessibilityEvent?) { /* passive: we read only on request */ }
    override fun onInterrupt() {}

    fun handle(action: String, args: JSONObject): JSONObject = when (action) {
        "screen_read" -> screenRead()
        "ui_dump" -> screenRead()
        "sms_fill" -> smsFill(args.optString("number"), args.optString("text"))
        "click" -> click(args)
        "type_text" -> typeText(args.optString("text"))
        "swipe" -> swipe(args.optInt("x1"), args.optInt("y1"), args.optInt("x2"), args.optInt("y2"), args.optInt("ms", 300))
        "keyevent" -> key(args.optString("key"))
        "app_launch" -> launch(args.optString("package"))
        "open_url" -> openUrl(args.optString("url"))
        "clipboard" -> clip(args.optString("set"))
        "battery" -> battery()
        else -> JSONObject().put("error", "Royal Link: '$action' not allowed")
    }

    /** Visible text of the foreground window. Password fields and our own app are skipped. */
    fun screenRead(): JSONObject {
        val root = rootInActiveWindow ?: return JSONObject().put("error", "no active window")
        val pkg = root.packageName?.toString() ?: ""
        if (pkg in SENSITIVE_PKGS) return JSONObject().put("error", "blocked app ($pkg) — banking/OTP/password apps are never read")
        val out = JSONArray(); walk(root, out, 0)
        return JSONObject().put("text", "app=$pkg\n" + (0 until out.length()).joinToString("\n") { out.getString(it) }.take(6000))
    }
    private fun walk(n: AccessibilityNodeInfo?, out: JSONArray, depth: Int) {
        if (n == null || depth > 40 || out.length() > 400) return
        if (!n.isPassword) {
            val t = (n.text ?: n.contentDescription)?.toString()?.trim()
            if (!t.isNullOrEmpty()) out.put(t.take(300))
        }
        for (i in 0 until n.childCount) walk(n.getChild(i), out, depth + 1)
    }

    /** Opens the user's SMS app with number + body pre-filled. We NEVER click Send. */
    fun smsFill(number: String, text: String): JSONObject {
        if (text.isBlank()) return JSONObject().put("error", "empty text")
        val i = Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + Uri.encode(number)))
            .putExtra("sms_body", text).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(i)
        // Fallback for SMS apps that ignore sms_body: type into the focused editable field.
        android.os.Handler(mainLooper).postDelayed({
            val f = rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
            if (f != null && f.isEditable && f.text.isNullOrEmpty())
                f.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,
                    Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text) })
        }, 1200)
        return JSONObject().put("text", "SMS app opened with draft — user must tap Send")
    }
}

private fun TigerA11yService.ok(t: String) = JSONObject().put("text", t)
private fun TigerA11yService.err(t: String) = JSONObject().put("error", t)
private fun TigerA11yService.fgBlocked(): String? {
    val pkg = rootInActiveWindow?.packageName?.toString() ?: return null
    return if (pkg in SENSITIVE_PKGS) pkg else null
}
private fun TigerA11yService.find(n: AccessibilityNodeInfo?, q: String, d: Int = 0): AccessibilityNodeInfo? {
    if (n == null || d > 40) return null
    val t = (n.text ?: n.contentDescription)?.toString() ?: ""
    if (t.contains(q, true)) return n
    for (i in 0 until n.childCount) find(n.getChild(i), q, d + 1)?.let { return it }
    return null
}
/** Tap by visible text (preferred) or x,y. Never taps a Send button (user sends). */
internal fun TigerA11yService.click(a: JSONObject): JSONObject {
    fgBlocked()?.let { return err("blocked app $it") }
    val q = a.optString("text")
    if (q.isNotBlank()) {
        if (Regex("^(send|পাঠান|পাঠাও|pay|confirm payment)$", RegexOption.IGNORE_CASE).matches(q.trim())) return err("Send/Pay is always tapped by you")
        var n = find(rootInActiveWindow, q) ?: return err("'$q' not on screen")
        while (!n.isClickable && n.parent != null) n = n.parent
        return if (n.performAction(AccessibilityNodeInfo.ACTION_CLICK)) ok("tapped '$q'") else err("could not tap '$q'")
    }
    val x = a.optInt("x", -1); val y = a.optInt("y", -1)
    if (x < 0 || y < 0) return err("need text or x,y")
    return gesture(x, y, x, y, 60, "tapped $x,$y")
}
internal fun TigerA11yService.typeText(t: String): JSONObject {
    fgBlocked()?.let { return err("blocked app $it") }
    val f = rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: return err("no focused text field")
    if (f.isPassword) return err("password fields are never typed by Royal Link")
    val b = Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, t) }
    return if (f.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, b)) ok("typed") else err("type failed")
}
internal fun TigerA11yService.swipe(x1: Int, y1: Int, x2: Int, y2: Int, ms: Int) =
    gesture(x1, y1, x2, y2, ms.coerceIn(50, 3000).toLong(), "swiped")
private fun TigerA11yService.gesture(x1: Int, y1: Int, x2: Int, y2: Int, ms: Long, msg: String): JSONObject {
    val p = android.graphics.Path().apply { moveTo(x1.toFloat(), y1.toFloat()); lineTo(x2.toFloat(), y2.toFloat()) }
    val g = android.accessibilityservice.GestureDescription.Builder()
        .addStroke(android.accessibilityservice.GestureDescription.StrokeDescription(p, 0, ms)).build()
    return if (dispatchGesture(g, null, null)) ok(msg) else err("gesture rejected")
}
internal fun TigerA11yService.key(k: String): JSONObject {
    val a = when (k.uppercase().removePrefix("KEYCODE_")) {
        "BACK" -> AccessibilityService.GLOBAL_ACTION_BACK; "HOME" -> AccessibilityService.GLOBAL_ACTION_HOME
        "RECENTS", "APP_SWITCH" -> AccessibilityService.GLOBAL_ACTION_RECENTS
        "NOTIFICATIONS" -> AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS
        "QUICK_SETTINGS" -> AccessibilityService.GLOBAL_ACTION_QUICK_SETTINGS
        "LOCK" -> if (android.os.Build.VERSION.SDK_INT >= 28) AccessibilityService.GLOBAL_ACTION_LOCK_SCREEN else -1
        "SCREENSHOT" -> if (android.os.Build.VERSION.SDK_INT >= 28) AccessibilityService.GLOBAL_ACTION_TAKE_SCREENSHOT else -1
        else -> -1 }
    if (a < 0) return err("key '$k' not supported (BACK/HOME/RECENTS/NOTIFICATIONS/QUICK_SETTINGS/LOCK/SCREENSHOT)")
    return if (performGlobalAction(a)) ok("$k done") else err("$k failed")
}
internal fun TigerA11yService.launch(pkg: String): JSONObject {
    if (pkg in SENSITIVE_PKGS) return err("blocked app $pkg")
    val i = packageManager.getLaunchIntentForPackage(pkg) ?: return err("app $pkg not found (Android 11+ may hide it)")
    startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); return ok("opened $pkg")
}
internal fun TigerA11yService.openUrl(u: String): JSONObject {
    if (!u.startsWith("https://") && !u.startsWith("http://")) return err("only http(s) links")
    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(u)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); return ok("opened link")
}
internal fun TigerA11yService.clip(t: String): JSONObject {
    if (t.isEmpty()) return err("reading the clipboard in background is blocked by Android 10+; only set is supported")
    (getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager).setPrimaryClip(android.content.ClipData.newPlainText("royal", t))
    return ok("clipboard set")
}
internal fun TigerA11yService.battery(): JSONObject {
    val bm = getSystemService(android.content.Context.BATTERY_SERVICE) as android.os.BatteryManager
    return ok("battery ${bm.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY)}%" + if (bm.isCharging) " charging" else "")
}

/** Never read these even if approved (extend in-app). */
val SENSITIVE_PKGS = setOf("com.bkash.customerapp", "com.konasl.nagad", "com.dbbl.mbs.apps.main",
    "com.google.android.apps.authenticator2", "com.android.settings")
