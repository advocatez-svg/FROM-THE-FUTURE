#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a focused feed for middle-class apartment opportunities in Amman."""
import datetime
import json
import os
import statistics as st

import pipeline as base
from pipeline_standard_floors import standard_floor_type

ROOT = base.ROOT
DATA = base.DATA

TOP_LIMIT = int(os.environ.get("MIDDLE_CLASS_TOP_LIMIT", "15"))
PRICE_MIN = int(os.environ.get("MIDDLE_CLASS_PRICE_MIN", "35000"))
PRICE_MAX = int(os.environ.get("MIDDLE_CLASS_PRICE_MAX", "150000"))
SIZE_MIN = int(os.environ.get("MIDDLE_CLASS_SIZE_MIN", "75"))
SIZE_MAX = int(os.environ.get("MIDDLE_CLASS_SIZE_MAX", "260"))

MIDDLE_CLASS_AREAS = [
    ("شفا بدران", "شفا-بدران", "shafa-badran", "شفا-بدران"),
    ("الجبيهة", None, "al-jubaiha", "الجبيهة"),
    ("تلاع العلي", "تلاع-العلي", "tlaa-al-ali", "تلاع-العلي"),
]


def classify_apartment(title):
    ft = base.floor_type(title)
    if ft:
        return ft
    ft = standard_floor_type(title)
    if ft:
        return ft
    if base.is_apt(title):
        return "الطابق غير مذكور"
    return None


def collect_rows():
    raw = {}
    for name, qs, bs, os_ in MIDDLE_CLASS_AREAS:
        rows = []
        rows += [dict(r, source="قوشان") for r in (base.scrape_qoshan(qs) if qs else [])]
        rows += [dict(r, source="Bayut") for r in base.scrape_bayut(bs)]
        rows += [dict(r, source="السوق المفتوح") for r in base.scrape_opensooq(os_)]
        for r in rows:
            base.fix_size(r)
        raw[name] = rows
        print(f"{name}: {len(rows)}", flush=True)

    out = []
    seen = set()
    for name, _, _, _ in MIDDLE_CLASS_AREAS:
        for r in raw[name]:
            title = r.get("title") or ""
            ft = classify_apartment(title)
            if not ft:
                continue
            key = (r.get("url") or title[:80], r.get("price"), r.get("size"))
            if key in seen:
                continue
            seen.add(key)
            out.append(dict(base.area_breakdown(r, ft), area=name, ft=ft))
    return out


def _median_stats(rows):
    stats = {}
    for name, _, _, _ in MIDDLE_CLASS_AREAS:
        ppm = [
            r["price"] / r["size"]
            for r in rows
            if r["area"] == name and base.ok(r["price"], r["size"])
        ]
        if ppm:
            stats[name] = dict(
                med=round(st.median(ppm)),
                n=len(ppm),
                q1=round(base.q(ppm, .25)),
                q3=round(base.q(ppm, .75)),
                tier="متوسطة",
            )
    return stats


def _is_middle_class_fit(rec):
    price = rec.get("price")
    size = rec.get("size")
    if not isinstance(price, int) or not isinstance(size, int):
        return False
    return PRICE_MIN <= price <= PRICE_MAX and SIZE_MIN <= size <= SIZE_MAX


def evaluate(rows):
    stats = _median_stats(rows)
    listings = []
    for r in rows:
        p, s, name = r["price"], r["size"], r["area"]
        rec = dict(
            area=name,
            area_tier="متوسطة",
            segment="الطبقة المتوسطة",
            ft=r["ft"],
            size=s,
            advertised_size=r.get("advertised_size", ""),
            internal_size=r.get("internal_size", ""),
            external_size=r.get("external_size", ""),
            price_per_sqm_basis=r.get("price_per_sqm_basis", ""),
            area_confidence=r.get("area_confidence", ""),
            area_note=r.get("area_note", ""),
            price=p,
            src=r["source"],
            title=r["title"],
            url=r.get("url", ""),
            middle_class_fit=False,
        )
        if base.ok(p, s) and name in stats:
            ppm = round(p / s)
            med = stats[name]["med"]
            q1 = stats[name]["q1"]
            q3 = stats[name]["q3"]
            rec["ppm"] = ppm
            rec["fair"] = round(med * s)
            rec["diff"] = round((p - med * s) / (med * s) * 100)
            rec["target"] = round(med * s * 0.92)
            rec["warn"] = 1 if ppm < 0.6 * med else 0
            rec["ev"] = (
                "🟢 صفقة" if ppm < q1 else
                "✅ عادل-أدنى" if ppm <= med else
                "🟡 عادل-أعلى" if ppm <= q3 else
                "🔴 مرتفع"
            ) + ("" if stats[name]["n"] >= 3 else " (عيّنة صغيرة)")
            rec["middle_class_fit"] = _is_middle_class_fit(rec)
        else:
            rec.update(ppm="", fair="", diff="", target="", warn=0, ev="— ناقص")
        listings.append(rec)
    return stats, listings


def select_deals(listings):
    deals = [
        x for x in listings
        if x.get("middle_class_fit")
        and x.get("ev", "").startswith(("🟢", "✅"))
        and x.get("warn") == 0
        and isinstance(x.get("diff"), int)
    ]
    deals.sort(key=lambda x: (x["diff"], x.get("ppm") or 999999, x.get("price") or 999999))
    top = deals[:TOP_LIMIT]
    for deal in top:
        deal.update(base.contact_details(deal.get("url", ""), deal.get("src", ""), deal.get("title", "")))
    return top


def run():
    rows = collect_rows()
    stats, listings = evaluate(rows)
    top = select_deals(listings)
    today = datetime.date.today().isoformat()
    summary = dict(
        date=today,
        segment="middle_class",
        segment_ar="الطبقة المتوسطة",
        total_middle_class_listings=len(listings),
        top_limit=TOP_LIMIT,
        price_min=PRICE_MIN,
        price_max=PRICE_MAX,
        size_min=SIZE_MIN,
        size_max=SIZE_MAX,
        areas=[dict(name=a, **stats[a]) for a in sorted(stats)],
    )
    base.write_json("middle_class_summary.json", summary, indent=1)
    base.write_json("middle_class_listings.json", listings)
    base.write_json("middle_class_top_deals.json", top, indent=1)
    print(f"\nDONE · middle-class listings: {len(listings)} · deals: {len(top)} · date: {today}", flush=True)
    return top


if __name__ == "__main__":
    run()
