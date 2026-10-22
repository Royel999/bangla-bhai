# Shizuku + rish সেটআপ (বাংলা)

পূর্ণ ফোন নিয়ন্ত্রণ (স্ক্রিন, ট্যাপ, সেটিংস, অ্যাপ force-stop, কল end/answer) এর জন্য **Shizuku** লাগবে।

## ১) Shizuku চালু
1. F-Droid / GitHub থেকে **Shizuku** অ্যাপ ইনস্টল করুন।
2. অ্যাপ খুলে **Start** (Wireless debugging / Pairing code) দিয়ে চালু রাখুন। নোটিফিকেশনে Shizuku running দেখা যাবে।

## ২) rish টার্মউক্সে আনুন
1. Shizuku অ্যাপে **Use Shizuku in terminal apps** (বা “Export files”) খুলুন।
2. `rish` এবং `rish_shizuku.dex` এক্সপোর্ট/কপি করুন।
3. Termux এ:
```bash
mkdir -p ~/bin
# ফাইল দুটো ~/bin এ রাখুন (যেভাবে কপি করেছেন)
cp /sdcard/Download/rish ~/bin/ 2>/dev/null || true
cp /sdcard/Download/rish_shizuku.dex ~/bin/ 2>/dev/null || true
chmod +x ~/bin/rish
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
# পরীক্ষা:
rish -c 'id'
```
`uid=...` দেখালে ঠিক আছে।

## ৩) Termux:API
```bash
pkg install termux-api
```
F-Droid থেকে **Termux:API** অ্যাপ ইনস্টল করে SMS/Phone/Location/Camera অনুমতি দিন। হ্যাং হলে অ্যাপ Force stop → আবার খুলুন।

## ৪) বাংলা ভাই লিংক আবার চালান
নিচের এক লাইন (রিপোর্টেও আছে)।
