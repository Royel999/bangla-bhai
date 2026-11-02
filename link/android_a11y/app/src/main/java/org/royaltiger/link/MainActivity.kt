package org.royaltiger.link

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/** SCAFFOLD: one screen — explains, then deep-links to Android Accessibility settings.
 *  Android itself shows the system consent dialog; we cannot (and do not try to) auto-enable. */
class MainActivity : Activity() {
    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        val l = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(48, 96, 48, 48) }
        l.addView(TextView(this).apply { text = getString(R.string.a11y_desc); textSize = 16f })
        l.addView(Button(this).apply { text = "Open Accessibility settings / অ্যাক্সেসিবিলিটি খুলুন"
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) } })
        setContentView(l)
    }
}
