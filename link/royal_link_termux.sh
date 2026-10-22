#!/data/data/com.termux/files/usr/bin/bash
# বাংলা ভাই · Royal Link (Termux + optional Shizuku rish)
# সব কাজ বাংলা ভাই UI-তে Approve/Deny এর পরই চলে। গোপন কিছু নেই।
set -e
BB_URL="${BB_URL:-https://banglabhai.dpdns.org}"
BB_URL="${BB_URL%/}"
CFG="$HOME/.bangla_bhai_link.json"
NAME="${BB_NAME:-$(getprop ro.product.model 2>/dev/null || echo termux)}"
TO=15   # termux-api / rish timeout seconds

# ---------- Shizuku rish ----------
rish_cmd(){
  if command -v rish >/dev/null 2>&1; then timeout "$TO" rish -c "$*"; return $?; fi
  for R in "$HOME/bin/rish" "$HOME/rish" /data/local/tmp/rish; do
    [ -x "$R" ] && { timeout "$TO" "$R" -c "$*"; return $?; }
  done
  return 127
}
have_rish(){ rish_cmd 'id' >/dev/null 2>&1; }

# termux-api with timeout + Bengali error
tapi(){
  local bin="$1"; shift
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "{\"error\":\"$bin নেই। pkg install termux-api করুন এবং F-Droid থেকে Termux:API অ্যাপ ইনস্টল/খুলে অনুমতি দিন।\"}"
    return 0
  fi
  local out
  if ! out=$(timeout "$TO" "$bin" "$@" 2>&1); then
    local ec=$?
    if [ $ec -eq 124 ]; then
      echo "{\"error\":\"⏰ $bin ${TO}সেকেন্ডে সাড়া দেয়নি। Termux:API অ্যাপ খুলে অনুমতি দিন, Force stop করে আবার চালু করুন, অথবা ফোন রিস্টার্ট করুন।\"}"
    else
      echo "{\"error\":\"$bin ব্যর্থ (কোড $ec): $(printf '%s' "$out" | head -c 300)\"}"
    fi
    return 0
  fi
  printf '%s' "$out"
}

json_text(){ python3 -c "import json,sys;print(json.dumps({'text':sys.stdin.read()[:12000]},ensure_ascii=False))"; }
json_err(){ python3 -c "import json,sys;print(json.dumps({'error':sys.argv[1]},ensure_ascii=False))" "$1"; }
arg(){ echo "$ARGS" | python3 -c "import sys,json;a=json.load(sys.stdin);print(a.get('$1','$2'))"; }

pair(){
  if [ -f "$CFG" ]; then
    TOK=$(python3 -c "import json;print(json.load(open('$CFG'))['token'])")
    ST=$(curl -fsS "$BB_URL/bb/link/status?token=$TOK" | python3 -c "import sys,json;print(json.load(sys.stdin).get('status'))")
    [ "$ST" = approved ] && return 0
  fi
  SHIZUKU=false; have_rish && SHIZUKU=true
  RES=$(curl -fsS -X POST "$BB_URL/bb/link/pair" -H 'Content-Type: application/json' \
    -d "{\"name\":\"$NAME\",\"kind\":\"android\",\"info\":{\"termux\":true,\"shizuku\":$SHIZUKU}}")
  echo "$RES" | python3 -c "import sys,json;d=json.load(sys.stdin);open('$CFG','w').write(json.dumps({'device':d['device'],'token':d['token']}));print(d['device'])"
  CODE=$(echo "$RES" | python3 -c "import sys,json;print(json.load(sys.stdin)['device'])")
  echo ""
  echo "══════════════════════════════════════"
  echo "  পেয়ার কোড:  $CODE"
  echo "  বাংলা ভাই → সেটিংস → অনুমতি কেন্দ্র"
  echo "  থেকে এই ডিভাইস 'যুক্ত করুন' চাপুন"
  echo "══════════════════════════════════════"
  while true; do
    TOK=$(python3 -c "import json;print(json.load(open('$CFG'))['token'])")
    ST=$(curl -fsS "$BB_URL/bb/link/status?token=$TOK" | python3 -c "import sys,json;print(json.load(sys.stdin).get('status'))")
    [ "$ST" = approved ] && echo "✅ অনুমোদিত" && break
    [ "$ST" = denied ] && echo "বাতিল" && exit 1
    sleep 3
  done
}

do_job(){
  ACT="$1"; ARGS="$2"
  case "$ACT" in
    shell)
      CMD=$(arg cmd)
      echo "🔴 শেল: $CMD" >&2
      if have_rish; then OUT=$(rish_cmd "$CMD" 2>&1 | tail -c 8000) || true
      else OUT=$(timeout "$TO" bash -lc "$CMD" 2>&1 | tail -c 8000) || true; fi
      printf '%s' "$OUT" | json_text
      ;;
    screenshot)
      echo "🔴 স্ক্রিনশট" >&2; F="$HOME/bb_ss.png"
      if have_rish; then
        rish_cmd "screencap -p /sdcard/bb_ss.png" && cp -f /sdcard/bb_ss.png "$F" 2>/dev/null || rish_cmd "screencap -p" > "$F" || true
      else json_err "স্ক্রিনশটের জন্য Shizuku (rish) চালু করুন"; return; fi
      [ -s "$F" ] || { json_err "screencap ব্যর্থ"; return; }
      python3 -c "import base64,json;print(json.dumps({'image_b64':base64.b64encode(open('$F','rb').read()).decode(),'ext':'png','text':'ss'}))"
      ;;
    click)
      X=$(arg x 0); Y=$(arg y 0); echo "🔴 ট্যাপ $X,$Y" >&2
      have_rish || { json_err "ট্যাপের জন্য Shizuku rish লাগবে"; return; }
      rish_cmd "input tap $X $Y" && echo '{"text":"tapped"}' || json_err "tap ব্যর্থ"
      ;;
    type_text)
      T=$(echo "$ARGS"|python3 -c "import sys,json;print(json.load(sys.stdin).get('text','').replace(' ','%s').replace(\"'\",\"'\\\\''\"))")
      echo "🔴 টাইপ" >&2; have_rish || { json_err "টাইপের জন্য Shizuku rish লাগবে"; return; }
      rish_cmd "input text '$T'" && echo '{"text":"typed"}' || json_err "type ব্যর্থ"
      ;;
    swipe)
      eval "$(echo "$ARGS"|python3 -c "import sys,json;a=json.load(sys.stdin);print('X1=%d Y1=%d X2=%d Y2=%d MS=%d'%(int(a.get('x1',0)),int(a.get('y1',0)),int(a.get('x2',0)),int(a.get('y2',0)),int(a.get('ms',300))))")"
      echo "🔴 সোয়াইপ" >&2; have_rish || { json_err "সোয়াইপের জন্য Shizuku rish লাগবে"; return; }
      rish_cmd "input swipe $X1 $Y1 $X2 $Y2 $MS" && echo '{"text":"swiped"}' || json_err "swipe ব্যর্থ"
      ;;
    keyevent)
      KEY=$(arg key KEYCODE_BACK)
      # allow names or numbers
      echo "🔴 keyevent $KEY" >&2; have_rish || { json_err "keyevent এর জন্য Shizuku rish লাগবে"; return; }
      case "$KEY" in
        BACK|back) KEY=KEYCODE_BACK;; HOME|home) KEY=KEYCODE_HOME;; ENTER|enter) KEY=KEYCODE_ENTER;;
        CALL|call|answer) KEY=KEYCODE_CALL;; END|end|ENDCALL|reject|hangup) KEY=KEYCODE_ENDCALL;;
      esac
      rish_cmd "input keyevent $KEY" && echo "{\"text\":\"key $KEY\"}" || json_err "keyevent ব্যর্থ"
      ;;
    ui_dump)
      echo "🔴 UI dump" >&2; have_rish || { json_err "ui_dump এর জন্য Shizuku rish লাগবে"; return; }
      F="/sdcard/bb_ui.xml"
      rish_cmd "uiautomator dump $F" >/dev/null 2>&1 || { json_err "uiautomator dump ব্যর্থ"; return; }
      rish_cmd "cat $F" 2>/dev/null | head -c 100000 | json_text
      ;;
    am_start)
      COMP=$(arg component); [ -z "$COMP" ] && COMP=$(arg intent)
      echo "🔴 am start $COMP" >&2; have_rish || { json_err "am start এর জন্য Shizuku rish লাগবে"; return; }
      rish_cmd "am start -n $COMP" && echo '{"text":"started"}' || json_err "am start ব্যর্থ"
      ;;
    camera_photo)
      echo "🔴 ক্যামেরা" >&2; F="$HOME/bb_cam.jpg"
      R=$(tapi termux-camera-photo -c 0 "$F")
      echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
      [ -s "$F" ] || { json_err "ক্যামেরা ফাইল খালি — Termux:API ক্যামেরা অনুমতি দিন"; return; }
      python3 -c "import base64,json;print(json.dumps({'image_b64':base64.b64encode(open('$F','rb').read()).decode(),'ext':'jpg','text':'ছবি'}))"
      ;;
    mic_record)
      SEC=$(arg seconds 4); echo "🔴 মাইক ${SEC}s" >&2; F="$HOME/bb_mic.wav"
      R=$(tapi termux-microphone-record -f "$F" -l "$SEC")
      echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
      sleep "$SEC"; termux-microphone-record -q 2>/dev/null || true
      [ -s "$F" ] || { json_err "মাইক ফাইল খালি"; return; }
      python3 -c "import base64,json;print(json.dumps({'image_b64':base64.b64encode(open('$F','rb').read()).decode(),'ext':'wav','text':'${SEC}s'}))"
      ;;
    sms_list)
      L=$(arg limit 200); echo "🔴 SMS list -$L" >&2
      R=$(tapi termux-sms-list -l "$L" -t inbox)
      echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
      printf '%s' "$R" | python3 -c "import sys,json;d=sys.stdin.read();
try: j=json.loads(d); print(json.dumps({'text':json.dumps(j,ensure_ascii=False)[:11000]},ensure_ascii=False))
except Exception: print(json.dumps({'text':d[:11000]},ensure_ascii=False))"
      ;;
    sms_send)
      NUM=$(arg number); TXT=$(echo "$ARGS"|python3 -c "import sys,json;print(json.load(sys.stdin).get('text',''))")
      echo "🔴 SMS send → $NUM" >&2
      [ -n "$NUM" ] && [ -n "$TXT" ] || { json_err "number ও text লাগবে"; return; }
      R=$(tapi termux-sms-send -n "$NUM" "$TXT")
      echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
      echo '{"text":"SMS পাঠানো হয়েছে (অপেক্ষমাণ/সিস্টেম কিউ)"}'
      ;;
    call_make)
      NUM=$(arg number); echo "🔴 কল $NUM" >&2
      [ -n "$NUM" ] || { json_err "number লাগবে"; return; }
      R=$(tapi termux-telephony-call "$NUM")
      echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
      echo '{"text":"কল শুরু করার চেষ্টা করা হয়েছে"}'
      ;;
    call_control)
      DO=$(arg do end); echo "🔴 call_control $DO" >&2
      have_rish || { json_err "কল নিয়ন্ত্রণের জন্য Shizuku rish লাগবে (KEYCODE_CALL/ENDCALL)"; return; }
      case "$DO" in
        answer|pick) rish_cmd "input keyevent KEYCODE_CALL" && echo '{"text":"answer"}' || json_err "answer ব্যর্থ";;
        end|hangup|reject) rish_cmd "input keyevent KEYCODE_ENDCALL" && echo '{"text":"ended"}' || json_err "end ব্যর্থ";;
        *) json_err "do=answer|end|reject";;
      esac
      ;;
    call_log)
      L=$(arg limit 50); echo "🔴 call log" >&2
      R=$(tapi termux-call-log -l "$L")
      echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
      printf '%s' "$R" | json_text
      ;;
    contacts)
      echo "🔴 contacts" >&2
      R=$(tapi termux-contact-list)
      echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
      printf '%s' "$R" | head -c 11000 | json_text
      ;;
    notifications)
      echo "🔴 notifications" >&2
      R=$(tapi termux-notification-list)
      echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
      printf '%s' "$R" | head -c 11000 | json_text
      ;;
    battery)
      echo "🔴 battery" >&2
      R=$(tapi termux-battery-status)
      echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
      printf '%s' "$R" | json_text
      ;;
    location)
      echo "🔴 location" >&2
      R=$(tapi termux-location -p network)
      echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
      printf '%s' "$R" | json_text
      ;;
    sensor)
      SN=$(arg name accelerometer)
      echo "🔴 sensor $SN" >&2
      R=$(tapi termux-sensor -s "$SN" -n 1)
      echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
      printf '%s' "$R" | json_text
      ;;
    clipboard)
      SET=$(echo "$ARGS"|python3 -c "import sys,json;print(json.load(sys.stdin).get('set') or '')")
      if [ -n "$SET" ]; then
        R=$(tapi termux-clipboard-set "$SET")
        echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
        echo '{"text":"clipboard set"}'
      else
        R=$(tapi termux-clipboard-get)
        echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
        printf '%s' "$R" | json_text
      fi
      ;;
    settings_ctl)
      WHAT=$(arg what); VAL=$(arg value)
      echo "🔴 settings $WHAT=$VAL" >&2
      case "$WHAT" in
        wifi)
          if [ "$VAL" = "1" ] || [ "$VAL" = "on" ] || [ "$VAL" = "true" ]; then
            R=$(tapi termux-wifi-enable true); echo "$R" | grep -q '"error"' && printf '%s' "$R" || echo '{"text":"wifi on"}'
          else
            R=$(tapi termux-wifi-enable false); echo "$R" | grep -q '"error"' && printf '%s' "$R" || echo '{"text":"wifi off"}'
          fi
          ;;
        bluetooth)
          have_rish || { json_err "ব্লুটুথের জন্য Shizuku rish লাগবে"; return; }
          if [ "$VAL" = "1" ] || [ "$VAL" = "on" ]; then rish_cmd "svc bluetooth enable" && echo '{"text":"bt on"}' || json_err "bt on ব্যর্থ"
          else rish_cmd "svc bluetooth disable" && echo '{"text":"bt off"}' || json_err "bt off ব্যর্থ"; fi
          ;;
        brightness)
          have_rish || { json_err "ব্রাইটনেসের জন্য Shizuku rish লাগবে"; return; }
          rish_cmd "settings put system screen_brightness ${VAL:-128}" && echo '{"text":"brightness set"}' || json_err "brightness ব্যর্থ"
          ;;
        volume)
          # VAL like music:5 or just 5
          STREAM=$(echo "$VAL"|cut -d: -f1); VOL=$(echo "$VAL"|cut -d: -f2)
          [ "$STREAM" = "$VAL" ] && STREAM=music
          R=$(tapi termux-volume "$STREAM" "${VOL:-5}")
          echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
          echo '{"text":"volume set"}'
          ;;
        torch)
          ON=false; [ "$VAL" = "1" ] || [ "$VAL" = "on" ] || [ "$VAL" = "true" ] && ON=true
          R=$(tapi termux-torch "$ON")
          echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
          echo "{\"text\":\"torch $ON\"}"
          ;;
        airplane)
          have_rish || { json_err "এয়ারপ্লেন মোডের জন্য Shizuku rish লাগবে"; return; }
          if [ "$VAL" = "1" ] || [ "$VAL" = "on" ]; then rish_cmd "cmd connectivity airplane-mode enable" || rish_cmd "settings put global airplane_mode_on 1"
          else rish_cmd "cmd connectivity airplane-mode disable" || rish_cmd "settings put global airplane_mode_on 0"; fi
          echo '{"text":"airplane toggled"}'
          ;;
        dnd)
          have_rish || { json_err "DND এর জন্য Shizuku rish লাগবে"; return; }
          # VAL: on|off
          if [ "$VAL" = "on" ] || [ "$VAL" = "1" ]; then rish_cmd "cmd notification set_dnd priority" && echo '{"text":"dnd on"}' || json_err "dnd ব্যর্থ"
          else rish_cmd "cmd notification set_dnd off" && echo '{"text":"dnd off"}' || json_err "dnd off ব্যর্থ"; fi
          ;;
        put)
          # value: namespace key val  e.g. system screen_brightness 100
          have_rish || { json_err "settings put এর জন্য Shizuku rish লাগবে"; return; }
          rish_cmd "settings put $VAL" && echo '{"text":"settings put ok"}' || json_err "settings put ব্যর্থ"
          ;;
        get)
          have_rish || { json_err "settings get এর জন্য Shizuku rish লাগবে"; return; }
          OUT=$(rish_cmd "settings get $VAL" 2>&1) || true
          printf '%s' "$OUT" | json_text
          ;;
        *) json_err "what=wifi|bluetooth|brightness|volume|torch|airplane|dnd|put|get";;
      esac
      ;;
    app_list)
      echo "🔴 pm list" >&2
      if have_rish; then rish_cmd "pm list packages -3" 2>&1 | head -c 10000 | json_text
      else json_err "অ্যাপ তালিকার জন্য Shizuku rish লাগবে"; fi
      ;;
    app_launch)
      PKG=$(arg package); echo "🔴 launch $PKG" >&2
      [ -n "$PKG" ] || { json_err "package লাগবে"; return; }
      if have_rish; then
        rish_cmd "monkey -p $PKG -c android.intent.category.LAUNCHER 1" && echo '{"text":"launched"}' || json_err "launch ব্যর্থ"
      else
        R=$(tapi termux-open --type application "$PKG" 2>/dev/null) || json_err "launch ব্যর্থ — Shizuku দিয়ে চেষ্টা করুন"
        printf '%s' "${R:-{\"text\":\"opened\"}}"
      fi
      ;;
    app_stop)
      PKG=$(arg package); echo "🔴 force-stop $PKG" >&2
      have_rish || { json_err "force-stop এর জন্য Shizuku rish লাগবে"; return; }
      rish_cmd "am force-stop $PKG" && echo '{"text":"stopped"}' || json_err "stop ব্যর্থ"
      ;;
    open_url)
      U=$(arg url); echo "🔴 open $U" >&2
      R=$(tapi termux-open-url "$U")
      echo "$R" | grep -q '"error"' && { printf '%s' "$R"; return; }
      echo '{"text":"url opened"}'
      ;;
    *) json_err "অসমর্থিত অ্যাকশন: $ACT" ;;
  esac
}

pair
TOK=$(python3 -c "import json;print(json.load(open('$CFG'))['token'])")
if have_rish; then echo "♛ Royal Link + Shizuku (rish) চলছে — পূর্ণ নিয়ন্ত্রণ"; else
  echo "♛ Royal Link (Termux) চলছে"
  echo "ℹ️ স্ক্রিন/ট্যাপ/সেটিংস/অ্যাপের জন্য Shizuku rish চালু করুন (README দেখুন)"
fi
echo "বন্ধ: Ctrl+C"
while true; do
  JOB=$(curl -fsS --max-time 35 "$BB_URL/bb/link/poll?token=$TOK" || echo '{}')
  CID=$(echo "$JOB"|python3 -c "import sys,json;j=json.load(sys.stdin).get('job') or {};print(j.get('cid',''))" 2>/dev/null || true)
  [ -z "$CID" ] && continue
  ACT=$(echo "$JOB"|python3 -c "import sys,json;print(json.load(sys.stdin)['job']['action'])")
  ARGS=$(echo "$JOB"|python3 -c "import sys,json;print(json.dumps(json.load(sys.stdin)['job'].get('args') or {}))")
  RES=$(do_job "$ACT" "$ARGS")
  # ensure RES is JSON object
  echo "$RES" | python3 -c "import sys,json;json.load(sys.stdin)" 2>/dev/null || RES=$(json_err "অবৈধ ফলাফল")
  curl -fsS -X POST "$BB_URL/bb/link/result" -H 'Content-Type: application/json' \
    -d "$(python3 -c "import json,sys;print(json.dumps({'token':sys.argv[1],'cid':sys.argv[2],'result':json.loads(sys.argv[3])},ensure_ascii=False))" "$TOK" "$CID" "$RES")" >/dev/null || true
done
