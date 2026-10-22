# বাংলা ভাই — নিজে চালানোর গাইড (Windows ল্যাপটপ)

এই গাইড মেনে চললে অ্যাপটা আপনার নিজের ল্যাপটপে চলবে, কোনো অ্যাসিস্ট্যান্টের দরকার হবে না।

## ১. প্রথমবার ইনস্টল (এক ক্লিকে)
1. এই লিংক থেকে **install.bat** ডাউনলোড করুন: https://raw.githubusercontent.com/Royel999/bangla-bhai/main/windows/install.bat
   (ব্রাউজারে লেখা দেখালে Ctrl+S চেপে `install.bat` নামে সেভ করুন।)
2. ফাইলটায় ডাবল-ক্লিক করুন। Windows সতর্কতা দিলে **More info → Run anyway**।
   - Git, Python, প্যাকেজ নিজে থেকে বসে যাবে, আর GitHub-এর main থেকে কোড নেমে আসবে `C:\Users\<আপনার নাম>\bangla_bhai` ফোল্ডারে।
   - মালিকের ইউজারনেম, পাসওয়ার্ড, ইমেইল আর ফ্রি AI চাবি চাইবে (চাবি লেখার সময় দেখা যাবে না):
     - Groq: https://console.groq.com/keys
     - Gemini: https://aistudio.google.com/apikey
     - OpenRouter: https://openrouter.ai/keys
   - Cloudflare টানেল বসাবেন কি না জিজ্ঞেস করবে (ডোমেইন ল্যাপটপে আনতে চাইলে `y`)।
   - সব তথ্য `bangla_bhai\.env` ফাইলে থাকে। পরে বদলাতে Notepad দিয়ে খুলুন। এই ফাইল কখনো কাউকে দেবেন না।
3. ল্যাপটপ চালু করে লগইন করলেই অ্যাপ নিজে চালু হবে (টাস্কের নাম "BanglaBhai")।

## ২. চালু / বন্ধ
- চালু: `bangla_bhai\windows\start.bat` ডাবল-ক্লিক → ব্রাউজারে http://localhost:8090 খুলবে
- বন্ধ: `windows\stop.bat` ডাবল-ক্লিক
- সমস্যা হলে লগ দেখুন: `logs\app.log`, `logs\tunnel.log`

## ৩. আপডেট
`windows\update.bat` ডাবল-ক্লিক। এটা আগে ব্যাকআপ নেয়, তারপর GitHub থেকে নতুন কোড নামিয়ে অ্যাপ আবার চালু করে। ফোনের ইনস্টল করা অ্যাপ নিজে থেকেই নতুন সংস্করণ পাবে।

## ৪. ব্যাকআপ
`windows\backup.bat` ডাবল-ক্লিক। `backups\` ফোল্ডারে তারিখসহ একটা zip তৈরি হবে (`.env`, ডাটাবেস, ছবি আর চাবি এনক্রিপশনের ফাইল)। zip-টা Google Drive-এ রেখে দিন। ফেরত আনতে zip খুলে ফাইলগুলো `bangla_bhai` ফোল্ডারে বসান।

## ৫. banglabhai.dpdns.org ডোমেইন ল্যাপটপে আনা (Cloudflare Tunnel)
একবারই করতে হবে। PowerShell খুলে একটা একটা করে চালান।

Cloudflare-এ লগইন (ব্রাউজার খুলবে, skbadol3210@gmail.com দিয়ে ঢুকে banglabhai.dpdns.org বাছুন):

```powershell
cloudflared tunnel login
```

টানেল তৈরি:

```powershell
cloudflared tunnel create banglabhai-laptop
```

এটা একটা টানেল আইডি দেখাবে (যেমন `1a2b3c...`)। সেটা লিখে রাখুন।

ডোমেইন টানেলে যুক্ত করা:

```powershell
cloudflared tunnel route dns --overwrite-dns banglabhai-laptop banglabhai.dpdns.org
```

```powershell
cloudflared tunnel route dns --overwrite-dns banglabhai-laptop www.banglabhai.dpdns.org
```

কনফিগ ফাইল বসানো:

```powershell
copy $env:USERPROFILE\bangla_bhai\windows\cloudflared-config.example.yml $env:USERPROFILE\.cloudflared\config.yml
```

```powershell
notepad $env:USERPROFILE\.cloudflared\config.yml
```

Notepad-এ `<TUNNEL-ID>` জায়গায় আপনার টানেল আইডি আর `<USER>` জায়গায় Windows ইউজারনাম বসিয়ে সেভ করুন।

পরীক্ষা:

```powershell
cloudflared tunnel run banglabhai-laptop
```

ফোনে https://banglabhai.dpdns.org খুললে অ্যাপ আসলে ঠিক আছে। এরপর Ctrl+C চেপে বন্ধ করে `windows\start.bat` চালান। এখন থেকে টানেলও নিজে চালু হবে।

> জরুরি: এখন ডোমেইনটা Cloudflare Worker `banglabhai-proxy` হয়ে পুরনো সার্ভারে যায়। ল্যাপটপে আনার আগে Cloudflare ড্যাশবোর্ড → Workers & Pages → banglabhai-proxy → Settings → Domains & Routes থেকে banglabhai.dpdns.org আর www রুট মুছে দিন, নাহলে টানেল কাজ করবে না।

## ৬. মনে রাখবেন
- ল্যাপটপ বন্ধ থাকলে অ্যাপও বন্ধ থাকবে। Power Options-এ "Sleep: Never" রাখুন।
- সব কিছু বিনামূল্যে: Cloudflare Free, dpdns.org ফ্রি ডোমেইন, Groq/Gemini/OpenRouter ফ্রি চাবি।
- ডোমেইন বছরে একবার https://dashboard.digitalplat.org থেকে নবায়ন করতে হতে পারে।
