# Royal Link · Accessibility path (screen + SMS) — spec v0.1 (2 Nov 2026)

## Goal
With the user's permission, The Royal Bengal Tiger can (1) read the text on the phone's current screen and (2) draft an SMS and place it in the phone's SMS app. Every sensitive step goes through the Approve card + Sentinel.

## Flow
1. v4 → Me → **Royal Link · Screen & SMS**: 4 steps (install → pair → turn on Accessibility → choose permissions). Explicit consent text.
2. Phone: user installs the Royal Link app and **turns on the "Royal Link" service themselves** in Android Settings → Accessibility. Android shows its own warning; we cannot turn it on automatically.
3. Pair: the existing `/bb/link/pair` call → owner approves in the Permission center.
4. Agent tools (agent.py):
   - `screen_read` (cap `screen`): visible text only. Skips password fields; banking/bKash/Nagad/authenticator/Settings apps are blocked.
   - `sms_fill` (cap `sms_send`): opens the SMS app with the number and text filled in. **The user presses Send.** It is in `force_card`, so an Approve card always appears, even with "Always allow". Sentinel category = `send` → audit_events.
   - Existing `sms_send` (Termux/Shizuku) is unchanged: still an Approve card every time.
5. Each run is recorded in `audit_events` (`link_dispatch`/`link_result`).

## Real vs stub
| Part | Status |
|---|---|
| Tool registration in agent.py, force_card, sentinel `send` category | **Real** (tested locally) |
| v4 permission sheet (steps, device status, cap modes, consent) | **Real** UI, reads `/bb/api/devices` (owner) |
| Browser "See my screen" (one frame) + SMS draft → `sms:` link | **Real** (from the previous round) |
| Kotlin AccessibilityService + LinkClient (`link/android_a11y/`) | **Scaffold** — not compiled, no APK, not tested on a device |
| Background screen reading on the phone / filling the SMS field | Works only after the APK is built and installed |

## Honest limits
- **Play Store:** Google allows the Accessibility API only for real accessibility tools; a general "AI assistant" will likely be rejected or need a declaration and video. So distribution is **sideload (APK)** only; free.
- **Android 13+ "Restricted settings":** for a sideloaded app, the user must go to App info → ⋮ → "Allow restricted settings" before Accessibility can be turned on.
- The user must turn it on **themselves**; some brands (Xiaomi/Oppo/Vivo) turn it off again for battery saving, so set battery to "No restriction".
- We **never press SMS Send** and do not take the SEND_SMS permission (Play policy + Sentinel rule).
- We do not read password/OTP/bank screens. Not hidden: Android always shows its own indicator while the service is on.
- An APK build needs Android Studio/SDK (free); it is not on the box, so it has not been compiled.
