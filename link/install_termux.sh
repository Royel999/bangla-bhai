#!/data/data/com.termux/files/usr/bin/bash
# বাংলা ভাই · one-shot Termux installer + pair
# Usage: curl -fsSL <URL>/bb/link/install_termux.sh | bash -s -- <PAIR_CODE_OR_URL>
set -e
BB_URL="${1:-https://banglabhai.dpdns.org}"
PAIR="${2:-}"
# allow: bash -s -- https://host   OR   bash -s -- https://host CODE
if [[ "$BB_URL" != http* ]]; then
  echo "Usage: curl -fsSL https://YOUR/bb/link/install_termux.sh | bash -s -- https://YOUR [PAIR_CODE]"
  exit 1
fi
BB_URL="${BB_URL%/}"
pkg update -y >/dev/null 2>&1 || true
pkg install -y curl python termux-api 2>/dev/null || pkg install -y curl python
mkdir -p "$HOME/bangla_bhai"
curl -fsSL "$BB_URL/bb/link/royal_link_termux.sh" -o "$HOME/bangla_bhai/royal_link_termux.sh"
chmod +x "$HOME/bangla_bhai/royal_link_termux.sh"
# optional pair code saved for display
if [ -n "$PAIR" ]; then echo "$PAIR" > "$HOME/bangla_bhai/pair.code"; fi
# detect rish / Shizuku
if command -v rish >/dev/null 2>&1; then
  echo "✅ Shizuku rish পাওয়া গেছে"
elif [ -x /data/local/tmp/rish ]; then
  echo "export PATH=\"/data/local/tmp:\$PATH\"" >> "$HOME/.bashrc"
  echo "✅ /data/local/tmp/rish পাথ যোগ করা হয়েছে"
else
  echo "ℹ️ Shizuku+rish না থাকলেও চলবে (ক্যামেরা/মাইক)। স্ক্রিন/ট্যাপের জন্য Shizuku অ্যাপে rish চালু করুন।"
fi
echo ""
echo "এখন পেয়ারিং শুরু:"
echo "  BB_URL=$BB_URL bash $HOME/bangla_bhai/royal_link_termux.sh"
echo ""
export BB_URL
exec bash "$HOME/bangla_bhai/royal_link_termux.sh"
