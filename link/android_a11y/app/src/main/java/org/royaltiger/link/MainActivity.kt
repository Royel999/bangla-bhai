package org.royaltiger.link

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.Gravity
import android.widget.*

/**
 * One-tap pairing: open royallink://pair?code=NNNNNN (or /link/pair deep link),
 * or type the 6-digit code from the site (Me → Royal Link → Pair this phone).
 * Accessibility must be on before jobs run; pairing itself only needs the code.
 */
class MainActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var codeIn: EditText

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 72, 48, 48)
            setBackgroundColor(Color.parseColor("#0D0D12"))
        }
        fun tv(t: String, size: Float = 15f, color: Int = Color.WHITE) =
            TextView(this).apply { text = t; textSize = size; setTextColor(color); setPadding(0, 8, 0, 8) }
        root.addView(tv("🐯 Royal Link", 26f, Color.parseColor("#C9A227")))
        root.addView(tv("1. Turn on Accessibility\n2. Enter the 6-digit code from the site\n   (or open the Pair button / link)", 14f, 0xFFBBBBBB.toInt()))
        root.addView(Button(this).apply {
            text = "Turn on Accessibility / অ্যাক্সেসিবিলিটি"
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        })
        codeIn = EditText(this).apply {
            hint = "6-digit code"; inputType = InputType.TYPE_CLASS_NUMBER
            setTextColor(Color.WHITE); setHintTextColor(0xFF888888.toInt())
            gravity = Gravity.CENTER; textSize = 28f; letterSpacing = 0.3f
            setPadding(24, 24, 24, 24)
        }
        root.addView(codeIn)
        root.addView(Button(this).apply {
            text = "Pair / পেয়ার"
            setBackgroundColor(Color.parseColor("#006A4E")); setTextColor(Color.WHITE)
            setOnClickListener { doPair(codeIn.text.toString()) }
        })
        status = tv("Waiting…", 14f, 0xFFAAAAAA.toInt())
        root.addView(status)
        setContentView(root)
        handleIntent(intent)
    }

    override fun onNewIntent(i: Intent?) { super.onNewIntent(i); handleIntent(i) }

    private fun handleIntent(i: Intent?) {
        val data: Uri? = i?.data
        val code = when {
            data == null -> null
            data.getQueryParameter("code") != null -> data.getQueryParameter("code")
            data.host == "pair" -> data.getQueryParameter("code")
            else -> data.lastPathSegment
        }?.filter { it.isDigit() }?.take(6)
        if (!code.isNullOrEmpty()) { codeIn.setText(code); doPair(code) }
    }

    private fun doPair(raw: String) {
        val code = raw.filter { it.isDigit() }.take(6)
        if (code.length != 6) { status.text = "Enter the 6-digit code from banglabhai.dpdns.org"; return }
        status.text = "Pairing…"
        Thread {
            try {
                val r = LinkClient.claim(this, code)
                runOnUiThread {
                    status.text = "✅ Paired as ${r.optString("device")}\nKeep Accessibility ON. Each screen/SMS still needs Approve."
                    Toast.makeText(this, "Paired", Toast.LENGTH_SHORT).show()
                }
                LinkClient.start(this)
            } catch (e: Exception) {
                runOnUiThread { status.text = "❌ ${e.message ?: "failed"}" }
            }
        }.start()
    }
}
