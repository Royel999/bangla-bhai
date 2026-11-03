# Android ক্লিপবোর্ড — সৎ পরিকল্পনা
Android 10+ এ সাধারণ অ্যাপ **পেছনে থেকে** ক্লিপবোর্ড পড়তে পারে না (শুধু ফোকাসে থাকা অ্যাপ বা ডিফল্ট কিবোর্ড পারে)। তাই ওয়েব/PWA থেকে স্বয়ংক্রিয় ধরা সম্ভব নয়।
বৈধ পথ (যেকোনো একটা):
1. **Royal কিবোর্ড (IME)** — নিজস্ব InputMethodService; ব্যবহারকারী ডিফল্ট কিবোর্ড বানালে `ClipboardManager.addPrimaryClipChangedListener` পেছনেও কাজ করে। সবচেয়ে নির্ভরযোগ্য।
2. **Share-target / Quick Settings টাইল** — "কপি → শেয়ার → Royal" বা টাইলে চাপ দিলে অ্যাপ এক মুহূর্ত ফোকাস নিয়ে ক্লিপ পড়ে `/bb/link/clip`-এ পাঠায়।
3. **Shizuku/ADB** — `appops set <pkg> READ_CLIPBOARD allow` দিয়ে ফোরগ্রাউন্ড সার্ভিস থেকে পড়া (Android 10-12-এ কাজ করে, 13+ এ নোটিফিকেশন দেখায়)।
প্রতিটিতে: দৃশ্যমান নোটিফিকেশন, ⏸ থামানোর বোতাম, OTP/পাসওয়ার্ড/কার্ড ফিল্টার (link/royal_clip.py-র `sensitive()` এর মতো)।
API: `POST /bb/link/clip {token, kind:text|image|url, content}` · `GET /bb/link/clips?token=`.
