#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""خط أنابيب منفصل لشقق الطوابق الأخرى غير الأرضي والروف."""
import datetime
import json
import os
import statistics as st

import pipeline as base

ROOT = base.ROOT
DATA = base.DATA
TOP_LIMIT = int(os.environ.get("STANDARD_FLOOR_TOP_LIMIT", "15"))

FLOOR_LABELS = [
    ("أول", "طابق أول"),
    ("اول", "طابق أول"),
    ("ثاني", "طابق ثاني"),
    ("ثالث", "طابق ثالث"),
    ("رابع", "طابق رابع"),
    ("خامس", "طابق خامس"),
    ("سادس", "طابق سادس"),
    ("سابع", "طابق سابع"),
    ("أخير", "طابق أخير"),
    ("اخير", "طابق أخير"),
]


def standard_floor_type(title):
    title = title or ""
    if base.floor_type(title):
        return None
    if any(x in title for x in base.GEXCL):
        return None
    if any(x in title for x in ["دوبلكس", "دبلكس", "تربلكس", "ترابلكس"]):
        return None
    if not base.is_apt(title):
        return None
    for key, label in FLOOR_LABELS:
        if key in title:
            return label
    return "الطابق غير مذكور"


def collect_rows():
    raw = {}
    for name, qs, bs, os_ in base.AREAS:
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
    for name, _, _, _ in base.AREAS:
        for r in raw[name]:
            title = r.get("title") or ""
            ft = standard_floor_type(title)
            if not ft:
                continue
            key = (title[:50], r.get("price"))
            if key in seen:
                continue
            seen.add(key)
            out.append(dict(base.area_breakdown(r, ft), area=name, ft=ft))
    return out


def evaluate(rows):
    stats = {}
    for name, _, _, _ in base.AREAS:
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
                tier=base.tier(st.median(ppm)),
            )

    listings = []
    for r in rows:
        p, s, name = r["price"], r["size"], r["area"]
        rec = dict(
            area=name,
            area_tier=stats.get(name, {}).get("tier", ""),
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
        else:
            rec.update(ppm="", fair="", diff="", target="", warn=0, ev="— ناقص")
        listings.append(rec)
    return stats, listings


def run():
    rows = collect_rows()
    stats, listings = evaluate(rows)
    order = sorted(stats, key=lambda a: -stats[a]["med"])

    deals = [
        x for x in listings
        if x.get("url") and x.get("ev", "").startswith(("🟢", "✅"))
        and x.get("warn") == 0 and isinstance(x.get("diff"), int)
    ]
    deals.sort(key=lambda x: (x["diff"], x.get("ppm") or 999999))
    top = deals[:TOP_LIMIT]
    for deal in top:
        deal.update(base.contact_details(deal.get("url", ""), deal.get("src", ""), deal.get("title", "")))

    today = datetime.date.today().isoformat()
    summary = dict(
        date=today,
        total_standard_floor=len(listings),
        top_limit=TOP_LIMIT,
        areas=[dict(name=a, **stats[a]) for a in order],
    )
    base.write_json("standard_floor_summary.json", summary, indent=1)
    base.write_json("standard_floor_listings.json", listings)
    base.write_json("standard_floor_top_deals.json", top, indent=1)
    print(f"\nDONE · standard-floor listings: {len(listings)} · deals: {len(top)} · date: {today}", flush=True)
    return top


if __name__ == "__main__":
    run()
