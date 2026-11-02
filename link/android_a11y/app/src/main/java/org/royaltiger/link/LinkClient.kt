package org.royaltiger.link

import android.content.Context
import kotlinx.coroutines.*
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Same protocol as link/royal_link.py. Token in MODE_PRIVATE prefs; never logged. */
object LinkClient {
    private var job: Job? = null
    var base = "https://banglabhai.dpdns.org"

    fun claim(ctx: Context, code: String): JSONObject {
        val sp = ctx.getSharedPreferences("royal_link", Context.MODE_PRIVATE)
        base = sp.getString("base", base)!!
        val r = http("POST", "/bb/link/claim",
            JSONObject().put("code", code).put("name", android.os.Build.MODEL)
                .put("kind", "phone"))
        if (r.has("error")) throw RuntimeException(r.getString("error"))
        val tok = r.getString("token")
        sp.edit().putString("token", tok).putString("device", r.getString("device")).apply()
        return r
    }

    fun start(ctx: Context) {
        val sp = ctx.getSharedPreferences("royal_link", Context.MODE_PRIVATE)
        base = sp.getString("base", base)!!
        if (job?.isActive == true) return
        job = CoroutineScope(Dispatchers.IO).launch {
            var tok = sp.getString("token", null) ?: return@launch
            while (isActive) {
                try {
                    val st = http("GET", "/bb/link/status?token=$tok", null).optString("status")
                    if (st != "approved") { delay(3000); continue }
                    val j = http("GET", "/bb/link/poll?token=$tok", null).optJSONObject("job") ?: continue
                    val svc = TigerA11yService.instance
                    val res = if (svc == null) JSONObject().put("error", "Accessibility is off")
                              else withContext(Dispatchers.Main) { svc.handle(j.getString("action"), j.optJSONObject("args") ?: JSONObject()) }
                    http("POST", "/bb/link/result", JSONObject().put("token", tok).put("cid", j.getString("cid")).put("result", res))
                } catch (e: Exception) { delay(3000) }
            }
        }
    }
    fun stop() { job?.cancel(); job = null }

    private fun http(m: String, path: String, body: JSONObject?): JSONObject {
        val c = URL(base + path).openConnection() as HttpURLConnection
        c.requestMethod = m; c.connectTimeout = 15000; c.readTimeout = 35000
        c.setRequestProperty("Content-Type", "application/json"); c.setRequestProperty("User-Agent", "RoyalLinkA11y/0.2")
        if (body != null) { c.doOutput = true; c.outputStream.use { it.write(body.toString().toByteArray()) } }
        val stream = if (c.responseCode in 200..299) c.inputStream else c.errorStream
        val txt = stream?.bufferedReader()?.readText() ?: "{}"
        return try { JSONObject(txt) } catch (_: Exception) { JSONObject().put("error", "HTTP ${c.responseCode}") }
    }
}
