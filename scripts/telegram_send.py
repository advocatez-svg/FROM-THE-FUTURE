#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يرسل أفضل 10 فرص (data/top_deals.json) إلى تيليجرام عبر Bot API.
المتغيرات المطلوبة: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
اختياري: DASHBOARD_URL (رابط الداشبورد المنشور)."""
import json, os, html, urllib.request, urllib.parse, urllib.error, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")
DASH  = os.environ.get("DASHBOARD_URL", "")

def esc(s): return html.escape(str(s))

def build_message():
    deals = json.load(open(os.path.join(ROOT, "data", "top_deals.json"), encoding="utf-8"))
    try:
        summ = json.load(open(os.path.join(ROOT, "data", "summary.json"), encoding="utf-8"))
        date = summ.get("date", "")
    except Exception:
        date = datetime.date.today().isoformat()
    lines = [f"🏙️ <b>أفضل {len(deals)} فرص شقق (أرضي/روف) — عمّان</b>", f"📅 {esc(date)}", ""]
    if not deals:
        lines.append("لا توجد فرص مطابقة اليوم.")
    for i, d in enumerate(deals, 1):
        t = esc(d.get("title", ""))
        if d.get("url"):
            t = f'<a href="{esc(d["url"])}">{t}</a>'
        lines.append(
            f"<b>{i}. {esc(d['area'])} · {esc(d['ft'])}</b>\n"
            f"   {d['size']}م² · {int(d['price']):,} دينار · <b>{d['ppm']}/م²</b>\n"
            f"   🟢 أرخص بـ <b>{abs(d['diff'])}%</b> من السعر العادل (~{int(d['fair']):,})\n"
            f"   👤 {esc(d.get('advertiser_type', 'غير محدد'))}"
            f"{' · 📞 ' + esc(d.get('phone')) if d.get('phone') else ''}\n"
            f"   {t}\n")
    if DASH:
        lines.append(f"📊 الداشبورد الكامل: {esc(DASH)}")
    lines.append("\n<i>أسعار عرض — السعر النهائي غالباً أقل بـ 5–15%. للاسترشاد.</i>")
    return "\n".join(lines)

def send(text):
    if not TOKEN or not CHAT:
        print("⚠️ TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID غير مضبوطين — طباعة الرسالة فقط:\n")
        print(text)
        return
    print(f"chat_id المستخدم = {CHAT!r}  (طوله {len(CHAT)})")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT, "text": text, "parse_mode": "HTML",
        "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
            print("✅ تم الإرسال — Telegram status:", r.status)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"❌ خطأ من تيليجرام: HTTP {e.code}")
        print("الوصف:", body)
        print("\nإرشاد: إن ظهر 'chat not found' فإن chat_id غير صحيح "
              "(للقناة العامة استخدم @username، وللخاصة الرقم -100..). "
              "وإن ظهر 'not enough rights' أو 'bot is not a member' فأضف البوت مشرفاً مع صلاحية النشر.")
        raise

if __name__ == "__main__":
    send(build_message())
