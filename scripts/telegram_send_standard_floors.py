#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يرسل فرص شقق الطوابق الأخرى من data/standard_floor_top_deals.json إلى تيليجرام."""
import datetime
import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from telegram_send import area_lines

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHANNEL_ID") or os.environ.get("TELEGRAM_CHAT_ID", "")
DASH = os.environ.get("STANDARD_FLOOR_DASHBOARD_URL", "")
FACEBOOK_GROUP = os.environ.get("FACEBOOK_GROUP_URL", "https://www.facebook.com/groups/JordanPropertyGroup")
BATCH_INDEX = os.environ.get("TELEGRAM_BATCH_INDEX", "")
BATCH_SIZE = int(os.environ.get("TELEGRAM_BATCH_SIZE", "2"))


def esc(value):
    return html.escape(str(value))


def _load_json(name):
    return json.load(open(os.path.join(ROOT, "data", name), encoding="utf-8"))


def build_message():
    all_deals = _load_json("standard_floor_top_deals.json")
    deals = all_deals
    batch_label = ""
    start = 0
    if BATCH_INDEX != "":
        start = int(BATCH_INDEX) * BATCH_SIZE
        deals = all_deals[start:start + BATCH_SIZE]
        total_batches = max(1, (len(all_deals) + BATCH_SIZE - 1) // BATCH_SIZE)
        batch_label = f" — الدفعة {int(BATCH_INDEX) + 1}/{total_batches}"
    try:
        date = _load_json("standard_floor_summary.json").get("date", "")
    except Exception:
        date = datetime.date.today().isoformat()

    lines = [f"🏢 <b>فرص شقق الطوابق الأخرى — عمّان{batch_label}</b>", f"📅 {esc(date)}", ""]
    if not deals:
        lines.append("لا توجد فرص في هذه الدفعة.")
    for i, d in enumerate(deals, start + 1):
        title = esc(d.get("title", ""))
        if d.get("url"):
            title = f'<a href="{esc(d["url"])}">{title}</a>'
        lines.append(
            f"<b>{i}. {esc(d['area'])} · {esc(d['ft'])}</b>\n"
            f"   💰 {int(d['price']):,} دينار\n"
            f"{area_lines(d)}\n"
            f"   🟢 أقل بـ <b>{abs(d['diff'])}%</b> من مرجع أسعار العرض (~{int(d['fair']):,})\n"
            f"   👤 {esc(d.get('advertiser_type', 'غير محدد'))}"
            f"{' · 📞 ' + esc(d.get('phone')) if d.get('phone') else ''}\n"
            f"   {title}\n"
        )
    if DASH:
        lines.append(f"📊 داشبورد الطوابق الأخرى: {esc(DASH)}")
    if FACEBOOK_GROUP:
        lines.append(f"📘 مجموعة فيسبوك: {esc(FACEBOOK_GROUP)}")
    lines.append("\n<i>أسعار عرض — المقارنة هنا مع مرجع أسعار العرض لشقق الطوابق الأخرى، وليست تقييماً عقارياً نهائياً.</i>")
    return "\n".join(lines)


def send(text):
    if not TOKEN or not CHAT:
        print("⚠️ TELEGRAM_BOT_TOKEN / TELEGRAM_CHANNEL_ID غير مضبوطين — طباعة الرسالة فقط:\n")
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
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
            print("✅ تم الإرسال — Telegram status:", r.status)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"❌ خطأ من تيليجرام: HTTP {e.code}")
        print("الوصف:", body)
        raise


if __name__ == "__main__":
    send(build_message())
