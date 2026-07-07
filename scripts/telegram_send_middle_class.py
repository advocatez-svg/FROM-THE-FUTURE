#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Send middle-class apartment opportunities to Telegram."""
import datetime
import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHANNEL_ID") or os.environ.get("TELEGRAM_CHAT_ID", "")
DASH = os.environ.get("DASHBOARD_URL", "")
FACEBOOK_GROUP = os.environ.get("FACEBOOK_GROUP_URL", "https://www.facebook.com/groups/JordanPropertyGroup")
BATCH_INDEX = os.environ.get("TELEGRAM_BATCH_INDEX", "")
BATCH_SIZE = int(os.environ.get("TELEGRAM_BATCH_SIZE", "2"))
DRY_RUN = os.environ.get("TELEGRAM_DRY_RUN", "").lower() in {"1", "true", "yes"}


def esc(value):
    return html.escape(str(value))


def _load_json(name):
    return json.load(open(os.path.join(ROOT, "data", name), encoding="utf-8"))


def _display_size(deal):
    return deal.get("internal_size") or deal.get("advertised_size") or deal.get("size") or ""


def build_message():
    all_deals = _load_json("middle_class_top_deals.json")
    deals = all_deals
    batch_label = ""
    start = 0
    if BATCH_INDEX != "":
        start = int(BATCH_INDEX) * BATCH_SIZE
        deals = all_deals[start:start + BATCH_SIZE]
        total_batches = max(1, (len(all_deals) + BATCH_SIZE - 1) // BATCH_SIZE)
        batch_label = f" — الدفعة {int(BATCH_INDEX) + 1}/{total_batches}"

    try:
        summary = _load_json("middle_class_summary.json")
        date = summary.get("date", "")
    except Exception:
        date = datetime.date.today().isoformat()

    headline_count = len(all_deals) if BATCH_INDEX == "" else len(deals)
    headline = f"أفضل {headline_count} فرص شقق مختارة — عمّان"
    if batch_label:
        headline = f"أفضل فرص شقق مختارة — عمّان{batch_label}"

    lines = [
        f"🏙️ <b>{headline}</b>",
        f"📅 {esc(date)}",
        "",
    ]
    if not deals:
        lines.append("لا توجد فرص مناسبة في هذه الدفعة حسب الفلتر الحالي.")
    for i, d in enumerate(deals, start + 1):
        title = esc(d.get("title", ""))
        if d.get("url"):
            title = f'<a href="{esc(d["url"])}">{title}</a>'
        lines.append(
            f"<b>{i}. {esc(d['area'])} · {esc(d['ft'])}</b>\n"
            f"   {esc(_display_size(d))}م² · {int(d['price']):,} دينار · {esc(d.get('ppm', ''))}/م²\n"
            f"   🟢 أرخص بـ <b>{abs(d['diff'])}%</b> من السعر العادل (~{int(d['fair']):,})\n"
            f"   👤 {esc(d.get('advertiser_type', 'غير محدد'))}"
            f"{' · 📞 ' + esc(d.get('phone')) if d.get('phone') else ''}\n"
            f"   {title}\n"
        )
    if DASH:
        lines.append(f"📊 الداشبورد الكامل: {esc(DASH)}")
    if FACEBOOK_GROUP:
        lines.append(f"📘 مجموعة فيسبوك: {esc(FACEBOOK_GROUP)}")
    lines.append("\n<i>أسعار عرض — السعر النهائي غالباً أقل بـ 5–15%. للاسترشاد.</i>")
    return "\n".join(lines)


def send(text):
    if DRY_RUN or not TOKEN or not CHAT:
        reason = "TELEGRAM_DRY_RUN مفعل" if DRY_RUN else "TELEGRAM_BOT_TOKEN / TELEGRAM_CHANNEL_ID غير مضبوطين"
        print(f"{reason} — طباعة الرسالة فقط:\n")
        print(text)
        return
    print(f"chat_id المستخدم = {CHAT!r}  (طوله {len(CHAT)})")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as response:
            print("تم الإرسال — Telegram status:", response.status)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        print(f"خطأ من تيليجرام: HTTP {exc.code}")
        print("الوصف:", body)
        raise


if __name__ == "__main__":
    send(build_message())
