# বাংলা ভাই — নিজে চালানোর গাইড (Windows ল্যাপটপ)

এই গাইড মেনে চললে অ্যাপটা আপনার নিজের ল্যাপটপে চলবে, কোনো অ্যাসিস্ট্যান্টের দরকার হবে না।

## ১. প্রথমবার ইনস্টল
1. GitHub থেকে কোড নামান। Git না থাকলে আগে এটা চালান (PowerShell-এ):

```powershell
winget install -e --id Git.Git
```

```powershell
git clone https://github.com/Royel999/bangla-bhai.git C:\BanglaBhai
```

2. `C:\BanglaBhai` ফোল্ডারে গিয়ে **install.bat**-এ ডাবল-ক্লিক করুন।
   - Python, প্যাকেজ আর cloudflared নিজে থেকে বসে যাবে।
   - মালিকের ইউজারনেম, পাসওয়ার্ড আর ফ্রি AI চাবি চাইবে (লেখা দেখা যাবে না):
     - Groq: https://console.groq.com/keys
     - Gemini: https://aistudio.google.com/apikey
     - OpenRouter: https://openrouter.ai/keys
   - সব তথ্য `.env` ফাইলে থাকে। পরে বদলাতে Notepad দিয়ে খুলুন। এই ফাইল কখনো কাউকে দেবেন না।
3. ল্যাপটপ চালু করে লগইন করলেই অ্যাপ নিজে চালু হবে (টাস্কের নাম "BanglaBhai")।

## ২. চালু / বন্ধ
- চালু: **start.bat** ডাবল-ক্লিক → ব্রাউজারে http://127.0.0.1:8090 খুলবে
- বন্ধ: **stop.bat** ডাবল-ক্লিক
- সমস্যা হলে লগ দেখুন: `logs\app.log`, `logs\tunnel.log`

## ৩. আপডেট
**update.bat** ডাবল-ক্লিক। এটা আগে ব্যাকআপ নেয়, তারপর GitHub থেকে নতুন কোড নামিয়ে অ্যাপ আবার চালু করে। ফোনের ইনস্টল করা অ্যাপ নিজে থেকেই নতুন সংস্করণ পাবে।

## ৪. ব্যাকআপ
**backup.bat** ডাবল-ক্লিক। `backups\` ফোল্ডারে তারিখসহ একটা zip তৈরি হবে (`.env`, ডাটাবেস, লগ)। zip-টা Google Drive-এ রেখে দিন। ফেরত আনতে zip খুলে ফাইলগুলো `C:\BanglaBhai`-তে বসান।

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
copy C:\BanglaBhai\windows\cloudflared-config.example.yml $env:USERPROFILE\.cloudflared\config.yml
```

```powershell
notepad $env:USERPROFILE\.cloudflared\config.yml
```

Notepad-এ `<TUNNEL-ID>` জায়গায় আপনার টানেল আইডি আর `<USER>` জায়গায় Windows ইউজারনাম বসিয়ে সেভ করুন।

পরীক্ষা:

```powershell
cloudflared tunnel run banglabhai-laptop
```

ফোনে https://banglabhai.dpdns.org খুললে অ্যাপ আসলে ঠিক আছে। এরপর Ctrl+C চেপে বন্ধ করে **start.bat** চালান। এখন থেকে টানেলও নিজে চালু হবে।

> জরুরি: এখন ডোমেইনটা Cloudflare Worker `banglabhai-proxy` হয়ে পুরনো সার্ভারে যায়। ল্যাপটপে আনার আগে Cloudflare ড্যাশবোর্ড → Workers & Pages → banglabhai-proxy → Settings → Domains & Routes থেকে banglabhai.dpdns.org আর www রুট মুছে দিন, নাহলে টানেল কাজ করবে না।

## ৬. মনে রাখবেন
- ল্যাপটপ বন্ধ থাকলে অ্যাপও বন্ধ থাকবে। Power Options-এ "Sleep: Never" রাখুন।
- সব কিছু বিনামূল্যে: Cloudflare Free, dpdns.org ফ্রি ডোমেইন, Groq/Gemini/OpenRouter ফ্রি চাবি।
- ডোমেইন বছরে একবার https://dashboard.digitalplat.org থেকে নবায়ন করতে হতে পারে।
