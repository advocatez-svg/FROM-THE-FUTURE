# 🤖 بوت الفرص اليومي + داشبورد أسعار الشقق (عمّان)

يقوم النظام يومياً تلقائياً عبر **GitHub Actions** بـ:
1. **سحب** أسعار الشقق (أرضي/روف) من 3 مصادر: قوشان + Bayut + السوق المفتوح، لعشر مناطق.
2. **تنظيف** البيانات (استبعاد الفلل/الأراضي، تصحيح القيم الملوّثة، استبعاد الشواذ).
3. **تحديث** `dashboard.html` وملفات `data/`.
4. **إرسال أفضل 10 فرص** إلى تيليجرام (الأقل سعراً مقابل السعر العادل، بلا تنبيهات).

## ⚙️ الإعداد (مرة واحدة)

### 1) أنشئ بوت تيليجرام
- افتح [@BotFather](https://t.me/BotFather) → `/newbot` → اتبع الخطوات → ستحصل على **TOKEN**.

### 2) احصل على chat_id
- للإرسال لنفسك: راسل بوتك بأي رسالة، ثم افتح:
  `https://api.telegram.org/bot<TOKEN>/getUpdates` وخذ `chat.id`.
- للإرسال لقناة: أضف البوت **مشرفاً** في القناة، واستخدم `@channelusername` إذا كانت عامة أو معرّف القناة الرقمي بصيغة `-100...`.
- رابط الدعوة الخاص مثل `https://t.me/+...` لا يصلح كـ `chat_id` في Bot API.

### 3) أضف الأسرار في GitHub
المستودع → **Settings → Secrets and variables → Actions → New repository secret**:
| الاسم | القيمة |
|---|---|
| `TELEGRAM_BOT_TOKEN` | توكن البوت من BotFather |
| `TELEGRAM_CHANNEL_ID` | معرّف القناة بصيغة `-100...` أو `@channelusername` |
| `TELEGRAM_CHAT_ID`   | احتياطي فقط للتجربة الشخصية |

(اختياري) في تبويب **Variables** أضف `DASHBOARD_URL` = رابط الداشبورد المنشور (مثلاً عبر GitHub Pages) ليظهر في الرسالة.
(اختياري) أضف `FACEBOOK_GROUP_URL` = رابط مجموعة فيسبوك. إن لم يُضبط، يستخدم السكربت:
`https://www.facebook.com/groups/JordanPropertyGroup`

### 4) فعّل الجدولة
- الـ workflow يعمل تلقائياً يومياً 17:00 UTC (≈ 20:00 عمّان).
- لتغيير الوقت: عدّل `cron` في `.github/workflows/daily-deals.yml`.
- للتشغيل الفوري للتجربة: تبويب **Actions** → الـ workflow → **Run workflow**.

## 🧪 تشغيل محلي (اختياري)
```bash
python3 scripts/pipeline.py            # يحدّث dashboard.html + data/
# طباعة الرسالة فقط (دون إرسال) إن لم تُضبط المتغيرات:
python3 scripts/telegram_send.py
# أو الإرسال فعلياً:
TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHANNEL_ID=-100xxxxxxxxxx python3 scripts/telegram_send.py

# أمر منفصل لشقق الطوابق الأخرى، لا يلمس نظام الأرضي/الروف:
python3 scripts/pipeline_standard_floors.py
python3 scripts/telegram_send_standard_floors.py
```

## 📤 نشر الداشبورد (اختياري)
- المستودع مفعّل عليه GitHub Pages؛ الملف `dashboard.html` في الجذر سيكون متاحاً على:
  `https://<user>.github.io/<repo>/dashboard.html` — ضعه في `DASHBOARD_URL`.

## 🗂️ المخرجات
- `dashboard.html` — الداشبورد التفاعلي (يُحدّث يومياً).
- `data/top_deals.json` — أفضل 10 فرص (تُرسل لتيليجرام على 5 دفعات، كل دفعة عقارين، من 10 صباحاً إلى 10 مساءً).
  - تشمل الآن رقم الهاتف ونوع المعلن عند توفرهما من صفحة الإعلان الأصلية.
- `data/listings.json` — كل إعلانات الأرضي/الروف مع التقييم.
- `data/summary.json` — ملخّص المناطق والمتوسطات.
- `data/standard_floor_top_deals.json` — أفضل فرص شقق الطوابق الأخرى.
- `data/standard_floor_listings.json` — كل إعلانات شقق الطوابق الأخرى مع التقييم.
- `data/standard_floor_summary.json` — ملخّص شقق الطوابق الأخرى.

## 📐 قاعدة المساحات

النظام يفرق بين:

- `advertised_size` — المساحة المعلنة في الإعلان.
- `internal_size` — مساحة القوشان/المساحة الداخلية إذا ظهرت صراحة في النص.
- `external_size` — مساحة خارجية/استعمال مثل روف أو ترس أو حديقة إذا ظهرت صراحة.
- `size` — مساحة التسعير المستخدمة لحساب سعر المتر؛ تكون مساحة القوشان عند توفرها، وإلا المساحة المعلنة.
- `area_confidence` — درجة الثقة بالمساحة، مثل `deed_area_extracted` أو `needs_area_verification`.

رسالة تيليجرام تعرض أساس سعر المتر بوضوح. إذا كانت الشقة روف أو أرضية مع مساحة خارجية ولم تظهر مساحة القوشان، تظهر ملاحظة تحقق قبل اعتماد سعر المتر.

## 🔧 تخصيص
- **عدد الفرص / معايير الفرصة:** في `scripts/pipeline.py` دالة `run()` (المتغيّر `top` والشرط `diff <= -5`).
- **المناطق:** عدّل قائمة `AREAS` في أعلى `pipeline.py`.
- **حدود السحب:** يمكن ضبط `FETCH_TRIES` و`FETCH_TIMEOUT` و`SCRAPE_MAX_PAGES` إذا كان أحد المصادر بطيئاً أو يحجب الطلبات.
- **شقق الطوابق الأخرى:** استخدم workflow `فرص شقق الطوابق الأخرى (يدوي)` أو السكربت `scripts/pipeline_standard_floors.py`.
