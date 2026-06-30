#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يرسل أفضل فرص (data/top_deals.json) إلى تيليجرام عبر Bot API.
المتغيرات المطلوبة: TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID أو TELEGRAM_CHAT_ID
اختياري: DASHBOARD_URL, FACEBOOK_GROUP_URL, TELEGRAM_BATCH_INDEX, TELEGRAM_BATCH_SIZE."""
import json, os, html, urllib.request, urllib.parse, urllib.error, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT  = os.environ.get("TELEGRAM_CHANNEL_ID") or os.environ.get("TELEGRAM_CHAT_ID", "")
DASH  = os.environ.get("DASHBOARD_URL", "")
FACEBOOK_GROUP = os.environ.get("FACEBOOK_GROUP_URL", "https://www.facebook.com/groups/JordanPropertyGroup")
BATCH_INDEX = os.environ.get("TELEGRAM_BATCH_INDEX", "")
BATCH_SIZE = int(os.environ.get("TELEGRAM_BATCH_SIZE", "2"))

def esc(s): return html.escape(str(s))

def area_lines(d):
    basis = d.get("price_per_sqm_basis") or "المساحة المعلنة"
    internal = d.get("internal_size")
    external = d.get("external_size")
    advertised = d.get("advertised_size") or d.get("size")
    confidence = d.get("area_confidence", "")
    needs_check = confidence == "needs_area_verification" or (
        not confidence and d.get("ft") == "روف" and not internal
    )
    lines = []
    if internal:
        lines.append(f"   📐 داخلي/قوشان: <b>{esc(internal)}</b>م²")
        if advertised and str(advertised) != str(internal):
            lines.append(f"   📏 المساحة المعلنة: {esc(advertised)}م²")
    elif advertised:
        lines.append(f"   📐 المساحة المعلنة: <b>{esc(advertised)}</b>م²")
    if external:
        lines.append(f"   🌿 خارجي/استعمال: <b>{esc(external)}</b>م²")
    if needs_check:
        lines.append("   ⚠️ يجب تأكيد مساحة القوشان قبل اعتماد سعر المتر.")
    lines.append(f"   💵 سعر المتر على {esc(basis)}: <b>{esc(d.get('ppm', ''))}/م²</b>")
    return "\n".join(lines)

def build_message():
    deals = json.load(open(os.path.join(ROOT, "data", "top_deals.json"), encoding="utf-8"))
    batch_label = ""
    start = 0
    if BATCH_INDEX != "":
        start = int(BATCH_INDEX) * BATCH_SIZE
        deals = deals[start:start + BATCH_SIZE]
        total_batches = max(1, (len(json.load(open(os.path.join(ROOT, "data", "top_deals.json"), encoding="utf-8"))) + BATCH_SIZE - 1) // BATCH_SIZE)
        batch_label = f" — الدفعة {int(BATCH_INDEX) + 1}/{total_batches}"
    try:
        summ = json.load(open(os.path.join(ROOT, "data", "summary.json"), encoding="utf-8"))
        date = summ.get("date", "")
    except Exception:
        date = datetime.date.today().isoformat()
    lines = [f"🏙️ <b>فرص عقارية مختارة — عمّان{batch_label}</b>", f"📅 {esc(date)}", ""]
    if not deals:
        lines.append("لا توجد فرص في هذه الدفعة.")
    for i, d in enumerate(deals, start + 1):
        t = esc(d.get("title", ""))
        if d.get("url"):
            t = f'<a href="{esc(d["url"])}">{t}</a>'
        lines.append(
            f"<b>{i}. {esc(d['area'])} · {esc(d['ft'])}</b>\n"
            f"   💰 {int(d['price']):,} دينار\n"
            f"{area_lines(d)}\n"
            f"   🟢 أقل بـ <b>{abs(d['diff'])}%</b> من مرجع أسعار العرض (~{int(d['fair']):,})\n"
            f"   👤 {esc(d.get('advertiser_type', 'غير محدد'))}"
            f"{' · 📞 ' + esc(d.get('phone')) if d.get('phone') else ''}\n"
            f"   {t}\n")
    if DASH:
        lines.append(f"📊 الداشبورد الكامل: {esc(DASH)}")
    if FACEBOOK_GROUP:
        lines.append(f"📘 مجموعة فيسبوك: {esc(FACEBOOK_GROUP)}")
    lines.append("\n<i>أسعار عرض — المقارنة مع مرجع أسعار العرض في المنطقة، وليست تقييماً عقارياً نهائياً.</i>")
    return "\n".join(lines)

def send(text):
    if not TOKEN or not CHAT:
        print("⚠️ TELEGRAM_BOT_TOKEN / TELEGRAM_CHANNEL_ID غير مضبوطين — طباعة الرسالة فقط:\n")
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
