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
class MainActivity : Activity(), android.speech.tts.TextToSpeech.OnInitListener {
    private var tts: android.speech.tts.TextToSpeech? = null
    private var sr: android.speech.SpeechRecognizer? = null
    private lateinit var orb: TextView
    override fun onInit(s: Int) { tts?.language = java.util.Locale.US }
    private fun say(t: String) { status.text = t; tts?.speak(t.take(600), android.speech.tts.TextToSpeech.QUEUE_FLUSH, null, "rl") }
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
        status = tv(if (TigerA11yService.instance != null) "Accessibility ON ✅" else "Accessibility OFF — tap the first button", 14f, 0xFFAAAAAA.toInt())
        root.addView(status)
        root.addView(tv("\nVoice / ভয়েস — tap the seal and speak:\n“read screen” · “go back” · “home” · “notifications”\n“message 017XXXXXXXX hello” (draft only — you tap Send)", 13f, 0xFFBBBBBB.toInt()))
        orb = TextView(this).apply {
            text = "🐯"; textSize = 64f; gravity = Gravity.CENTER; setPadding(0, 40, 0, 40)
            background = android.graphics.drawable.GradientDrawable().apply { shape = android.graphics.drawable.GradientDrawable.OVAL
                setColor(Color.parseColor("#006A4E")); setStroke(10, Color.parseColor("#C9A227")) }
            setOnClickListener { listen() }
        }
        root.addView(orb, LinearLayout.LayoutParams(420, 420).apply { gravity = Gravity.CENTER_HORIZONTAL; topMargin = 24 })
        tts = android.speech.tts.TextToSpeech(this, this)
        setContentView(root)
        handleIntent(intent)
    }

    private fun pulse(on: Boolean) { orb.animate().scaleX(if (on) 1.12f else 1f).scaleY(if (on) 1.12f else 1f).setDuration(350).start() }

    private fun listen() {
        if (checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(android.Manifest.permission.RECORD_AUDIO), 7); return }
        if (!android.speech.SpeechRecognizer.isRecognitionAvailable(this)) { say("Speech recognition not available on this phone"); return }
        sr?.destroy(); sr = android.speech.SpeechRecognizer.createSpeechRecognizer(this)
        sr!!.setRecognitionListener(object : android.speech.RecognitionListener {
            override fun onResults(r: Bundle?) { pulse(false); r?.getStringArrayList(android.speech.SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.let { command(it) } }
            override fun onError(e: Int) { pulse(false); status.text = "Didn't catch that ($e) — tap again" }
            override fun onReadyForSpeech(p: Bundle?) { pulse(true); status.text = "Listening…" }
            override fun onBeginningOfSpeech() {}; override fun onRmsChanged(v: Float) { orb.scaleX = 1f + (v.coerceIn(0f, 10f) / 60f); orb.scaleY = orb.scaleX }
            override fun onBufferReceived(b: ByteArray?) {}; override fun onEndOfSpeech() {}
            override fun onPartialResults(p: Bundle?) {}; override fun onEvent(t: Int, p: Bundle?) {}
        })
        sr!!.startListening(Intent(android.speech.RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE_MODEL, android.speech.RecognizerIntent.LANGUAGE_MODEL_FREE_FORM))
    }

    /** Local voice commands — run only what you said yourself, on your own phone. */
    private fun command(raw: String) {
        val t = raw.lowercase().trim(); status.text = "You: $raw"
        val svc = TigerA11yService.instance ?: return say("Turn on Accessibility first")
        val sms = Regex("^(message|sms|text|মেসেজ)\\s+([+0-9 ]{6,})\\s+(.+)$").find(t)
        when {
            sms != null -> { svc.smsFill(sms.groupValues[2].replace(" ", ""), raw.substring(raw.length - sms.groupValues[3].length)); say("Draft ready. You tap Send.") }
            t.contains("read") || t.contains("পড়") -> {
                // Our own window is in front; go back to the previous app, then read it.
                svc.performGlobalAction(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK)
                orb.postDelayed({ val r = svc.screenRead(); say(r.optString("text", r.optString("error")).substringAfter("\n").replace("\n", ". ").take(500)) }, 900)
            }
            t.contains("back") || t.contains("পেছন") -> svc.key("BACK").let { say("Back") }
            t.contains("home") || t.contains("হোম") -> svc.key("HOME").let { say("Home") }
            t.contains("notification") -> svc.key("NOTIFICATIONS").let { say("Notifications") }
            t.contains("recent") -> svc.key("RECENTS").let { say("Recent apps") }
            else -> say("I can: read screen, back, home, notifications, recents, or message a number. For anything else, ask in the Royal Bengal Tiger chat.")
        }
    }

    override fun onDestroy() { sr?.destroy(); tts?.shutdown(); super.onDestroy() }

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
