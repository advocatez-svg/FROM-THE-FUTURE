#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""خط أنابيب يومي: سحب أسعار الشقق (أرضي/روف) من قوشان + Bayut + السوق المفتوح،
تنظيف البيانات، توليد داشبورد HTML، واستخراج أفضل الفرص (top deals)."""
import json, re, time, urllib.request, urllib.parse, statistics as st, math, os, datetime

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
os.makedirs(DATA, exist_ok=True)
FETCH_TRIES = int(os.environ.get("FETCH_TRIES", "2"))
FETCH_TIMEOUT = int(os.environ.get("FETCH_TIMEOUT", "12"))
SCRAPE_MAX_PAGES = int(os.environ.get("SCRAPE_MAX_PAGES", "8"))

# (الاسم, سلَق قوشان بالعربي أو None, سلَق Bayut بالإنجليزي أو None, سلَق السوق المفتوح بالعربي أو None)
AREAS = [
    ("عبدون",        "عبدون",        None,            "عبدون"),
    ("دابوق",        "دابوق",        "dabouq",        "دابوق"),
    ("دير غبار",     "دير-غبار",     "dair-ghbar",    "دير-غبار"),
    ("خلدا",         "خلدا",         "khalda",        "خلدا"),
    ("أم السماق",    "أم-السماق",    "um-al-summaq",  "ام-السماق"),
    ("ضاحية النخيل", "ضاحية-النخيل", None,            "ضاحية-النخيل"),
    ("طريق المطار",  "طريق-المطار",  "airport-road",  "طريق-المطار"),
    ("حي الصحابة",   "حي-الصحابة",   None,            "حي-الصحابة"),
    ("الجبيهة",      None,           "al-jubaiha",    "الجبيهة"),
    ("شفا بدران",    "شفا-بدران",    "shafa-badran",  "شفا-بدران"),
]

def fetch(url, tries=None):
    if tries is None:
        tries = FETCH_TRIES
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            time.sleep(1.5 * (a + 1))
    return ""

def fetch_html(url, tries=None):
    tries = tries or FETCH_TRIES
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ar,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            try:
                return e.read().decode("utf-8", "replace")
            except Exception:
                return ""
        except Exception:
            time.sleep(1.5 * (a + 1))
    return ""

def normalize_phone(value):
    digits = re.sub(r"\D+", "", value or "")
    if digits.startswith("00962"):
        digits = "0" + digits[5:]
    elif digits.startswith("962"):
        digits = "0" + digits[3:]
    elif digits.startswith("7") and len(digits) == 9:
        digits = "0" + digits
    return digits if re.fullmatch(r"07[789]\d{7}", digits) else ""

def contact_details(url, source, title=""):
    details = {
        "phone": "",
        "advertiser_type": "غير محدد",
        "contact_note": "رقم الهاتف ونوع المعلن غير متوفرين في البيانات المستخرجة"
    }
    if not url:
        return details

    h = fetch(url, tries=2)
    phones = []
    for match in re.findall(r'tel:([^"\'<>\s]+)', h, flags=re.I):
        phone = normalize_phone(match)
        if phone and phone not in phones:
            phones.append(phone)
    if not phones:
        for match in re.findall(r'(?:\+?962|00962|0)?7[789][\d\s\-]{7,12}', h):
            phone = normalize_phone(match)
            if phone and phone not in phones:
                phones.append(phone)

    text = re.sub(r"<[^>]+>", " ", h)
    probe = f"{title} {text[:8000]}"
    if any(k in probe for k in ["عمولة", "وسيط", "مكتب", "شركة عقارية", "مستشارك العقاري"]):
        advertiser_type = "وسيط / مكتب عقاري"
    elif any(k in probe for k in ["المالك مباشرة", "من المالك", "مالك مباشر"]):
        advertiser_type = "مالك مباشر"
    elif source == "Bayut" or "qoshan.com" in url:
        advertiser_type = "وسيط / منصة عقارية"
    else:
        advertiser_type = "غير محدد"

    if phones:
        details["phone"] = phones[0]
        details["contact_note"] = "تم استخراج رقم الهاتف من صفحة الإعلان الأصلية"
    details["advertiser_type"] = advertiser_type
    return details

# ---------- قوشان (Houzez) ----------
def scrape_qoshan(slug, maxp=None):
    maxp = maxp or SCRAPE_MAX_PAGES
    base = "https://qoshan.com/city/" + urllib.parse.quote(slug) + "/"
    out = {}
    for p in range(1, maxp + 1):
        h = fetch(base if p == 1 else base + f"page/{p}/")
        if not h: break
        cards = [c for c in re.split(r'(?=<div class="item-wrap item-wrap-v1)', h) if "data-listid" in c]
        if not cards: break
        new = 0
        for c in cards:
            pid = re.search(r'data-listid="(\d+)"', c)
            price = re.search(r'item-price">\s*([\d,]+)\s*دينار', c)
            size = re.search(r'hz-figure">([\d,]+)</span>\s*<span class="area_postfix">متر', c)
            title = re.search(r'item-title[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', c)
            if not pid: continue
            k = pid.group(1)
            if k in out: continue
            out[k] = dict(price=int(price.group(1).replace(",", "")) if price else None,
                          size=int(size.group(1).replace(",", "")) if size else None,
                          title=(title.group(2).strip() if title else ""),
                          url=(title.group(1) if title else ""))
            new += 1
        if p > 1 and new == 0: break
        time.sleep(0.3)
    return list(out.values())

# ---------- Bayut (Algolia hits) ----------
_dec = json.JSONDecoder()
def _bayut_hits(h):
    i = h.find('"hits":[')
    if i < 0: return []
    pos = i + 8; out = []
    while True:
        while pos < len(h) and h[pos] in ' ,\n\r\t': pos += 1
        if pos >= len(h) or h[pos] != '{': break
        try: obj, pos = _dec.raw_decode(h, pos)
        except Exception: break
        out.append(obj)
    return out

def scrape_bayut(slug, maxp=None):
    if not slug: return []
    maxp = maxp or SCRAPE_MAX_PAGES
    base = f"https://www.bayut.jo/en/amman/apartments-for-sale-in-{slug}/"
    out = {}
    for p in range(1, maxp + 1):
        url = base if p == 1 else base + f"page-{p}/"
        hits = []
        for _ in range(5):
            hits = _bayut_hits(fetch(url))
            if hits: break
            time.sleep(1)
        if not hits: break
        new = 0
        for it in hits:
            if it.get("purpose") != "for-sale": continue
            cats = [c.get("name") for c in it.get("category", []) if isinstance(c, dict)]
            if "Apartments" not in cats: continue
            eid = it.get("externalID"); price = it.get("price"); area = it.get("area")
            if eid and price and area and eid not in out:
                listing_slug = it.get("slug") or ""
                phone_data = it.get("phoneNumber") or {}
                phones = []
                if isinstance(phone_data, dict):
                    for value in phone_data.get("mobileNumbers", []) + phone_data.get("phoneNumbers", []):
                        phone = normalize_phone(value)
                        if phone and phone not in phones:
                            phones.append(phone)
                    for key in ("mobile", "phone"):
                        phone = normalize_phone(phone_data.get(key, ""))
                        if phone and phone not in phones:
                            phones.append(phone)
                agency = it.get("agency") or {}
                agency_name = agency.get("name_l1") or agency.get("name") if isinstance(agency, dict) else ""
                out[eid] = dict(
                    price=price,
                    size=area,
                    title=it.get("title", ""),
                    url=(f"https://www.bayut.jo/en/property/{listing_slug}.html" if listing_slug else ""),
                    phone=(phones[0] if phones else ""),
                    advertiser_type=("وسيط / منصة عقارية" if agency_name else "غير محدد"),
                    contact_note=("تم استخراج رقم الهاتف من بيانات Bayut" if phones else "رقم الهاتف غير متوفر في البيانات المستخرجة"),
                )
                new += 1
        if p > 1 and new == 0: break
        time.sleep(0.3)
    return list(out.values())

# ---------- السوق المفتوح (OpenSooq) ----------
def _ar2en(s): return (s or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
def scrape_opensooq(slug, maxp=None):
    if not slug: return []
    maxp = maxp or SCRAPE_MAX_PAGES
    base = ("https://jo.opensooq.com/ar/" + urllib.parse.quote("عمان") + "/" +
            urllib.parse.quote(slug) + "/" + urllib.parse.quote("عقارات") + "/" +
            urllib.parse.quote("شقق-للبيع"))
    out = {}
    for p in range(1, maxp + 1):
        h = fetch_html(base + (f"?page={p}" if p > 1 else ""))
        if not h: break
        new = 0
        next_data = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', h)
        items = []
        if next_data:
            try:
                payload = json.loads(next_data.group(1))
                items = payload["props"]["pageProps"]["serpApiResponse"]["listings"]["items"]
            except Exception:
                items = []
        for item in items:
            name = item.get("title") or ""
            price_text = item.get("price_amount") or ""
            price_digits = re.sub(r"\D+", "", _ar2en(price_text))
            if not name or not price_digits:
                continue
            tt = _ar2en(" ".join([name, item.get("highlights") or "", " ".join(item.get("cps") or [])]))
            m = re.search(r'المساحة:\s*([\d,]+)\s*م', tt) or re.search(r'مساح\w*\s*([\d,]+)\s*م', tt) or re.search(r'(?<!\d)([\d]{2,4})\s*م(?:تر)?\b', tt)
            if not m: continue
            size = int(m.group(1).replace(",", "")); price = int(price_digits)
            if not (30 <= size <= 2000 and price >= 5000): continue
            url = item.get("post_url") or ""
            if url.startswith("/"):
                url = "https://jo.opensooq.com/ar" + url
            phone = item.get("phone_number") or ""
            phone_complete = normalize_phone(phone)
            is_shop = bool(item.get("shop_name")) or "شركة" in (item.get("member_display_name") or "")
            advertiser_type = "وسيط / منصة عقارية" if is_shop else "مالك مباشر / معلن فردي"
            key = (item.get("id") or name[:60], price)
            if key not in out:
                out[key] = dict(
                    price=price,
                    size=size,
                    title=name,
                    url=url,
                    phone=phone_complete,
                    masked_phone=(phone if not phone_complete else ""),
                    advertiser_type=advertiser_type,
                    contact_note=("رقم الهاتف ظاهر كاملا في بيانات السوق المفتوح" if phone_complete else "رقم الهاتف مخفي جزئيا في نتائج السوق المفتوح؛ يظهر كاملا داخل صفحة الإعلان أو بعد تسجيل الدخول"),
                )
                new += 1
        if not items:
            pairs = re.findall(r'"name":"([^"]{6,160})".{0,1500}?"url":"([^"]+)".{0,1500}?"price":(\d+),"priceCurrency":"JOD"', h)
            for name, url, price in pairs:
                tt = _ar2en(name)
                m = re.search(r'مساح\w*\s*([\d,]+)\s*م', tt) or re.search(r'(?<!\d)([\d]{2,4})\s*م(?:تر)?\b', tt)
                if not m: continue
                size = int(m.group(1).replace(",", "")); price = int(price)
                if not (30 <= size <= 2000 and price >= 5000): continue
                key = (url, price)
                if key not in out:
                    out[key] = dict(price=price, size=size, title=name, url=url, phone="", masked_phone="", advertiser_type="غير محدد")
                    new += 1
        if p > 1 and new == 0: break
        time.sleep(0.3)
    return list(out.values())

# ---------- تنظيف وتصنيف ----------
VILLA = ['فيلا','ڤيلا','ﭬيلا','ڤلل','ﭬلل','فيلتين','فلل','فله','فيلل','قصر','تاون','بيت مستقل','بيت ريفي','منزل مستقل']
LAND  = ['اراضي','أراضي','قطعة','أرض للبيع','ارض للبيع','مزرعة','مزارع','شاليه','قطع أراضي','مصنع','مستودع']
OFFICE= ['مكتب','مكاتب','محل','محلات','عمارة','بناية كاملة','معرض']
GEXCL = ['شبه','تسوية','معلق','معلّق','نص ارضي','نصف ارضي','نص أرضي','بيزمنت','قبو']

def is_apt(t):
    t = t or ""
    if any(k in t for k in ['شقة','شقق','استوديو','ستوديو','بنتهاوس','رووف','روف','طابق']): return True
    if any(k in t for k in VILLA + LAND + OFFICE): return False
    return True
def floor_type(t):
    t = t or ""
    if any(k in t for k in ['رووف','روف','بنتهاوس','بنت هاوس']): return "روف"
    if (not any(x in t for x in GEXCL)) and (('أرضي' in t) or ('أرضية' in t)): return "أرضي"
    return None
def title_sizes(t):
    return sorted(set(int(c) for c in re.findall(r'([\d]{2,4})\s*(?:م²|م2|متر|م)\b', _ar2en(t)) if 40 <= int(c) <= 1500))
def fix_size(r):
    # تصحيح تلوّث المساحة 325 من العنوان
    if r.get("size") == 325:
        ts = title_sizes(r.get("title", ""))
        r["size"] = ts[0] if len(ts) == 1 else None
    return r

def _first_area(patterns, text):
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            value = int(m.group(1).replace(",", ""))
            if 30 <= value <= 2000:
                return value
    return None

def _external_areas(text, include_roof=False):
    vals = []
    external_words = "ترس|تراس|تراسات|حديقة|حدائق|خارجي|خارجية|خارجيه"
    if include_roof:
        external_words = "ترس|تراس|تراسات|حديقة|حدائق|روف|رووف|سطح|خارجي|خارجية|خارجيه"
    patterns = [
        rf'(?:مع|و|وال|بالإضافة إلى)\s*(?:{external_words})\D{{0,18}}([\d,]{{2,4}})\s*(?:م²|م2|متر|م)?',
        rf'(?:{external_words})\D{{0,18}}([\d,]{{2,4}})\s*(?:م²|م2|متر|م)?',
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            value = int(m.group(1).replace(",", ""))
            if 20 <= value <= 2000 and value not in vals:
                vals.append(value)
    return sum(vals) if vals else None

def area_breakdown(row, ft):
    """يفصل مساحة القوشان عن المساحات الخارجية عندما يذكرها العنوان بوضوح."""
    title = _ar2en(row.get("title", ""))
    advertised = row.get("size")
    deed = _first_area([
        r'(?:على|ع)\s*(?:القوشان|الكوشان)\D{0,18}([\d,]{2,4})',
        r'(?:مساحة\s*)?(?:القوشان|الكوشان)\D{0,18}([\d,]{2,4})',
        r'(?:مساحة\s*)?(?:داخلي|داخلية|داخليه)\D{0,18}([\d,]{2,4})',
        r'(?:مساحة\s*)?(?:الشقة|الشقه)\D{0,18}([\d,]{2,4})',
        r'(?:شقة|شقه)(?:\s+[^\d\s]+){0,4}\s+([\d,]{2,4})\s*(?:م²|م2|متر|م)\b',
    ], title)
    external = _external_areas(title, include_roof=bool(deed))

    if deed and advertised and advertised > deed and not external:
        external = advertised - deed

    risk_words = ["حديقة", "حدائق", "ترس", "تراس", "تراسات", "روف", "رووف", "سطح", "خارجي", "خارجية", "خارجيه"]
    has_area_risk = ft == "روف" or any(w in title for w in risk_words)

    pricing_size = deed or advertised
    if deed:
        confidence = "deed_area_extracted"
        basis = "مساحة القوشان/الداخلية"
        note = "تم استخراج مساحة داخلية/قوشان من نص الإعلان؛ راجع السند قبل الشراء."
    elif has_area_risk and advertised:
        confidence = "needs_area_verification"
        basis = "المساحة المعلنة"
        note = "المساحة قد تشمل روف/ترس/حديقة أو مساحة استعمال؛ يجب تأكيد مساحة القوشان."
    elif advertised:
        confidence = "advertised_area_only"
        basis = "المساحة المعلنة"
        note = "لم يظهر فصل بين مساحة القوشان والمساحات الخارجية في العنوان."
    else:
        confidence = "missing_area"
        basis = "غير محدد"
        note = "المساحة غير كافية لحساب سعر متر موثوق."

    out = dict(row)
    out.update(advertised_size=advertised, internal_size=deed or "",
               external_size=external or "", size=pricing_size,
               price_per_sqm_basis=basis, area_confidence=confidence,
               area_note=note)
    return out

def ok(p, s):
    return p and s and 40 <= s <= 1500 and p >= 20000 and 150 <= p / s <= 5000 and not (p == 450000 and s == 325)
def q(v, x):
    v = sorted(v); i = x * (len(v) - 1); lo = math.floor(i); hi = math.ceil(i)
    return v[lo] if lo == hi else v[lo] + (v[hi] - v[lo]) * (i - lo)
def tier(m): return "فاخرة" if m >= 1000 else "راقية" if m >= 800 else "متوسطة" if m >= 700 else "اقتصادية"

def write_json(name, payload, **kwargs):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, **kwargs)

def run():
    raw = {}
    for name, qs, bs, os_ in AREAS:
        rows = []
        rows += [dict(r, source="قوشان") for r in (scrape_qoshan(qs) if qs else [])]
        rows += [dict(r, source="Bayut") for r in scrape_bayut(bs)]
        rows += [dict(r, source="السوق المفتوح") for r in scrape_opensooq(os_)]
        for r in rows: fix_size(r)
        raw[name] = rows
        print(f"{name}: {len(rows)}", flush=True)

    # أرضي/روف فقط (الداشبورد كله مخصّص لشراء أرضي أو روف)
    floor_rows = []
    seen = set()
    for name, _, _, _ in AREAS:
        for r in raw[name]:
            ft = floor_type(r["title"])
            if not ft: continue
            k = (r["title"][:50], r["price"])
            if k in seen: continue
            seen.add(k)
            floor_rows.append(dict(area_breakdown(r, ft), area=name, ft=ft))

    # إحصاء الأرضي/الروف لكل منطقة (للترتيب والشرائح والأعمدة)
    areastats = {}
    for name, _, _, _ in AREAS:
        ppm = [r["price"]/r["size"] for r in floor_rows if r["area"] == name and ok(r["price"], r["size"])]
        if ppm:
            areastats[name] = dict(med=round(st.median(ppm)), n=len(ppm),
                                   q1=round(q(ppm, .25)), q3=round(q(ppm, .75)), tier=tier(st.median(ppm)))
    order = sorted(areastats, key=lambda a: -areastats[a]["med"])

    # مرجع الأرضي/الروف لكل منطقة
    ref = {}
    for name in areastats:
        for ft in ("أرضي", "روف"):
            v = [r["price"]/r["size"] for r in floor_rows if r["area"] == name and r["ft"] == ft and ok(r["price"], r["size"])]
            if v:
                ref[(name, ft)] = (len(v), round(st.median(v)), round(q(v, .25)), round(q(v, .75)))

    # بناء قائمة الإعلانات مع التقييم
    listings = []
    for r in floor_rows:
        p, s, name, ft = r["price"], r["size"], r["area"], r["ft"]
        rec = dict(area=name, area_tier=(areastats.get(name, {}).get("tier", "")), ft=ft,
                   size=s, advertised_size=r.get("advertised_size", ""),
                   internal_size=r.get("internal_size", ""), external_size=r.get("external_size", ""),
                   price_per_sqm_basis=r.get("price_per_sqm_basis", ""),
                   area_confidence=r.get("area_confidence", ""), area_note=r.get("area_note", ""),
                   price=p, src=r["source"], title=r["title"], url=r.get("url", ""))
        if ok(p, s):
            ppm = round(p / s); rec["ppm"] = ppm
            k = (name, ft)
            if k in ref:
                n, m, q1, q3 = ref[k]
                rec["fair"] = round(m * s); rec["diff"] = round((p - m * s) / (m * s) * 100)
                rec["target"] = round(m * s * 0.92)
                rec["warn"] = 1 if ppm < 0.6 * m else 0
                rec["ev"] = ("🟢 صفقة" if ppm < q1 else "✅ عادل-أدنى" if ppm <= m else
                             "🟡 عادل-أعلى" if ppm <= q3 else "🔴 مرتفع") + ("" if n >= 3 else " (عيّنة صغيرة)")
            else:
                rec.update(fair="", diff="", target="", warn=0, ev="— لا مرجع")
        else:
            rec.update(ppm="", fair="", diff="", target="", warn=0, ev="— ناقص")
        listings.append(rec)

    # أفضل الفرص: أرضي/روف برابط، أقل سعر متر مقابل مرجع أسعار العرض، بلا تنبيه
    # أفضل الفرص المتاحة: أرضي/روف برابط، قيمة جيدة (عند/دون المتوسط)، بلا تنبيه — مرتّبة بالأكثر توفيراً
    deals = [x for x in listings if x.get("url") and x.get("ev", "").startswith(("🟢", "✅"))
             and x.get("warn") == 0 and isinstance(x.get("diff"), int)]
    deals.sort(key=lambda x: x["diff"])
    top = deals[:10]   # يرسل المتاح فقط إن كان أقل من 10
    for deal in top:
        deal.update(contact_details(deal.get("url", ""), deal.get("src", ""), deal.get("title", "")))

    today = datetime.date.today().isoformat()
    summary = dict(date=today, total_floor=len(listings),
                   areas=[dict(name=a, **areastats[a]) for a in order],
                   gap=round((areastats[order[0]]["med"] - areastats[order[-1]]["med"]) / areastats[order[-1]]["med"] * 100) if order else 0)
    write_json("summary.json", summary, indent=1)
    write_json("listings.json", listings)
    write_json("top_deals.json", top, indent=1)

    fair_out = [dict(area=a, **{t: list(ref[(a, t)]) if (a, t) in ref else None for t in ("أرضي", "روف")}) for a in order]
    build_dashboard(summary, listings, fair_out, today)
    print(f"\nDONE · floor listings: {len(listings)} · deals: {len(top)} · date: {today}", flush=True)
    return top

def build_dashboard(summary, listings, fair, today):
    tmpl = open(os.path.join(ROOT, "scripts", "dashboard_template.html"), encoding="utf-8").read()
    data = dict(areas=summary["areas"], listings=listings, fair=fair,
                tot=sum(a["n"] for a in summary["areas"]), gap=summary["gap"],
                maxmed=max((a["med"] for a in summary["areas"]), default=1), date=today)
    html = tmpl.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    open(os.path.join(ROOT, "dashboard.html"), "w", encoding="utf-8").write(html)

if __name__ == "__main__":
    run()
