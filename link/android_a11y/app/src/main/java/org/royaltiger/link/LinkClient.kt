package org.royaltiger.link

import android.content.Context
import kotlinx.coroutines.*
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** SCAFFOLD. Same protocol as link/royal_link.py: pair -> owner approves in app -> poll -> result.
 *  Token kept in app-private SharedPreferences (MODE_PRIVATE); never logged. */
object LinkClient {
    private var job: Job? = null
    var base = "https://banglabhai.dpdns.org"

    fun start(ctx: Context) {
        val sp = ctx.getSharedPreferences("royal_link", Context.MODE_PRIVATE)
        base = sp.getString("base", base)!!
        job = CoroutineScope(Dispatchers.IO).launch {
            var tok = sp.getString("token", null)
            if (tok == null) {
                val r = http("POST", "/bb/link/pair", JSONObject().put("name", android.os.Build.MODEL)
                    .put("kind", "phone").put("info", JSONObject().put("client", "royal-link-a11y").put("sdk", android.os.Build.VERSION.SDK_INT)))
                tok = r.getString("token"); sp.edit().putString("token", tok).putString("device", r.getString("device")).apply()
            }
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
    fun stop() { job?.cancel() }

    private fun http(m: String, path: String, body: JSONObject?): JSONObject {
        val c = URL(base + path).openConnection() as HttpURLConnection
        c.requestMethod = m; c.connectTimeout = 15000; c.readTimeout = 35000
        c.setRequestProperty("Content-Type", "application/json"); c.setRequestProperty("User-Agent", "RoyalLinkA11y/0.1")
        if (body != null) { c.doOutput = true; c.outputStream.use { it.write(body.toString().toByteArray()) } }
        return JSONObject(c.inputStream.bufferedReader().readText())
    }
}
