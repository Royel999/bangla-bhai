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
 * SCAFFOLD — not yet compiled/tested on a device.
 * Jobs arrive from LinkClient (same /bb/link/poll protocol as royal_link.py). The server
 * only dispatches a job AFTER the owner tapped Approve (agent.py + sentinel.py), so this
 * service never decides on its own. It also refuses anything not in ALLOWED.
 */
class TigerA11yService : AccessibilityService() {
    companion object { var instance: TigerA11yService? = null; val ALLOWED = setOf("screen_read", "sms_fill") }

    override fun onServiceConnected() { instance = this; LinkClient.start(this) }
    override fun onDestroy() { instance = null; LinkClient.stop(); super.onDestroy() }
    override fun onAccessibilityEvent(e: AccessibilityEvent?) { /* passive: we read only on request */ }
    override fun onInterrupt() {}

    fun handle(action: String, args: JSONObject): JSONObject = when (action) {
        "screen_read" -> screenRead()
        "sms_fill" -> smsFill(args.optString("number"), args.optString("text"))
        else -> JSONObject().put("error", "Royal Link: '$action' not allowed")
    }

    /** Visible text of the foreground window. Password fields and our own app are skipped. */
    private fun screenRead(): JSONObject {
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
    private fun smsFill(number: String, text: String): JSONObject {
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

/** Never read these even if approved (extend in-app). */
val SENSITIVE_PKGS = setOf("com.bkash.customerapp", "com.konasl.nagad", "com.dbbl.mbs.apps.main",
    "com.google.android.apps.authenticator2", "com.android.settings")
