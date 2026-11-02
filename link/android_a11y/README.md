# Royal Link — Android Accessibility (SCAFFOLD)
Status: **source scaffold only — not compiled, no APK, not tested on a phone.** Build with Android Studio (free) / `gradle assembleDebug`, then sideload.

- `TigerA11yService` — reads visible screen text (`screen_read`), pre-fills SMS (`sms_fill`). Skips password fields + banking/OTP apps. Never presses Send; no SEND_SMS permission.
- `LinkClient` — same pair/poll/result protocol as `royal_link.py`; owner approves the device in the app.
- Every job only reaches the phone after an Approve card (agent.py force_card + sentinel.py "send").
See `/link/ROYAL_LINK_A11Y_SPEC.md` for limits (Play Store policy, Android 13+ restricted-settings, user must enable manually).
