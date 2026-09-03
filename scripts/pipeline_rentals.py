#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Daily rental-apartment research pipeline for the same Amman areas as sales.

This job only writes rental data files in this repository. It does not send
Telegram messages and does not publish anything to the website.
"""

from __future__ import annotations

import datetime
import json
import math
import os
import re
import statistics as st
import time
import urllib.parse

import pipeline as base

ROOT = base.ROOT
DATA = base.DATA

TOP_PER_TYPE = int(os.environ.get("RENTAL_TOP_PER_TYPE", "10"))
MIN_MONTHLY_RENT = int(os.environ.get("RENTAL_MIN_MONTHLY_RENT", "100"))
MAX_MONTHLY_RENT = int(os.environ.get("RENTAL_MAX_MONTHLY_RENT", "10000"))
MIN_SIZE = int(os.environ.get("RENTAL_MIN_SIZE", "30"))
MAX_SIZE = int(os.environ.get("RENTAL_MAX_SIZE", "800"))

RENT_WORDS = (
    "للايجار", "للإيجار", "ايجار", "إيجار", "تأجير",
    "for rent", "for-rent", "rental",
)
ANNUAL_WORDS = ("سنوي", "سنويا", "سنوية", "سنة", "سنويًا", "annual", "yearly", "per year")
MONTHLY_WORDS = ("شهري", "شهريا", "شهرية", "شهريًا", "monthly", "per month", "/month")
UNFURNISHED_WORDS = ("غير مفروش", "غير مفروشة", "unfurnished")
FURNISHED_WORDS = ("مفروش", "مفروشة", "furnished")


def _text(*values):
    return " ".join(str(value or "") for value in values).lower()


def _rent_period(*values):
    text = _text(*values)
    if any(word in text for word in ANNUAL_WORDS):
        return "annual"
    if any(word in text for word in MONTHLY_WORDS):
        return "monthly"
    return "unknown"


def _is_rental(*values):
    text = _text(*values)
    return any(word in text for word in RENT_WORDS)


def _furnishing(*values):
    text = _text(*values)
    if any(word in text for word in UNFURNISHED_WORDS):
        return "غير مفروشة"
    if any(word in text for word in FURNISHED_WORDS):
        return "مفروشة"
    return "غير محدد"


def _monthly_price(price, period):
    if not isinstance(price, (int, float)) or price <= 0:
        return None
    if period == "annual":
        return round(price / 12, 2)
    if period == "monthly":
        return round(price, 2)
    return None


def _period_label(period):
    return {
        "annual": "سنوي",
        "monthly": "شهري",
        "unknown": "غير محدد",
    }.get(period, "غير محدد")


def _extract_size(text):
    text = base._ar2en(text or "")
    match = (
        re.search(r"المساحة\s*[:：]?\s*([\d,]+)\s*م", text)
        or re.search(r"مساح\w*\s*[:：]?\s*([\d,]+)\s*م", text)
        or re.search(r"(?<!\d)([\d]{2,4})\s*م(?:تر)?\b", text)
    )
    if not match:
        return None
    value = int(match.group(1).replace(",", ""))
    return value if MIN_SIZE <= value <= MAX_SIZE else None


def scrape_bayut_rentals(slug, max_pages=None):
    if not slug:
        return []
    max_pages = max_pages or base.SCRAPE_MAX_PAGES
    base_url = f"https://www.bayut.jo/en/amman/apartments-for-rent-in-{slug}/"
    output = {}

    for page in range(1, max_pages + 1):
        url = base_url if page == 1 else base_url + f"page-{page}/"
        hits = []
        for _ in range(5):
            hits = base._bayut_hits(base.fetch(url))
            if hits:
                break
            time.sleep(1)
        if not hits:
            break

        new_items = 0
        for item in hits:
            purpose = str(item.get("purpose") or "").lower()
            if purpose and purpose not in ("for-rent", "rent"):
                continue
            categories = [
                category.get("name")
                for category in item.get("category", [])
                if isinstance(category, dict)
            ]
            if "Apartments" not in categories:
                continue

            identifier = item.get("externalID")
            price = item.get("price")
            size = item.get("area")
            if not identifier or not price or not size or identifier in output:
                continue

            listing_slug = item.get("slug") or ""
            title = item.get("title") or ""
            frequency = (
                item.get("priceFrequency")
                or item.get("rentFrequency")
                or item.get("frequency")
                or ""
            )
            agency = item.get("agency") or {}
            agency_name = (
                (agency.get("name_l1") or agency.get("name"))
                if isinstance(agency, dict)
                else ""
            )
            output[identifier] = {
                "price": int(price),
                "size": int(size),
                "title": title,
                "url": (
                    f"https://www.bayut.jo/en/property/{listing_slug}.html"
                    if listing_slug
                    else ""
                ),
                "source": "Bayut",
                "period": _rent_period(frequency, title),
                "furnishing": _furnishing(title),
                "advertiser_type": (
                    "وسيط / منصة عقارية" if agency_name else "غير محدد"
                ),
            }
            new_items += 1

        if page > 1 and new_items == 0:
            break
        time.sleep(0.3)

    return list(output.values())


def scrape_opensooq_rentals(slug, max_pages=None):
    if not slug:
        return []
    max_pages = max_pages or base.SCRAPE_MAX_PAGES
    base_url = (
        "https://jo.opensooq.com/ar/"
        + urllib.parse.quote("عمان")
        + "/"
        + urllib.parse.quote(slug)
        + "/"
        + urllib.parse.quote("عقارات")
        + "/"
        + urllib.parse.quote("شقق-للإيجار")
    )
    output = {}

    for page in range(1, max_pages + 1):
        url = base_url + (f"?page={page}" if page > 1 else "")
        html = base.fetch_html(url)
        if not html:
            break

        next_data = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html,
        )
        items = []
        if next_data:
            try:
                payload = json.loads(next_data.group(1))
                items = payload["props"]["pageProps"]["serpApiResponse"]["listings"]["items"]
            except (KeyError, TypeError, ValueError):
                items = []

        new_items = 0
        for item in items:
            title = item.get("title") or ""
            price_text = item.get("price_amount") or ""
            price_digits = re.sub(r"\D+", "", base._ar2en(str(price_text)))
            detail_text = " ".join(
                [
                    title,
                    item.get("highlights") or "",
                    " ".join(item.get("cps") or []),
                    str(item.get("price_type") or ""),
                    str(item.get("price_period") or ""),
                ]
            )
            size = _extract_size(detail_text)
            if not title or not price_digits or not size:
                continue

            price = int(price_digits)
            post_url = item.get("post_url") or ""
            if post_url.startswith("/"):
                post_url = "https://jo.opensooq.com/ar" + post_url
            identifier = item.get("id") or post_url or title[:80]
            key = (identifier, price)
            if key in output:
                continue

            is_shop = bool(item.get("shop_name")) or "شركة" in (
                item.get("member_display_name") or ""
            )
            output[key] = {
                "price": price,
                "size": size,
                "title": title,
                "url": post_url,
                "source": "السوق المفتوح",
                "period": _rent_period(detail_text, post_url),
                "furnishing": _furnishing(detail_text),
                "advertiser_type": (
                    "وسيط / منصة عقارية"
                    if is_shop
                    else "مالك مباشر / معلن فردي"
                ),
            }
            new_items += 1

        if not items or (page > 1 and new_items == 0):
            break
        time.sleep(0.3)

    return list(output.values())


def scrape_qoshan_rentals(slug):
    rows = []
    for item in base.scrape_qoshan(slug) if slug else []:
        text = _text(item.get("title"), item.get("url"))
        if not _is_rental(text):
            continue
        rows.append(
            {
                **item,
                "source": "قوشان",
                "period": _rent_period(text),
                "furnishing": _furnishing(text),
                "advertiser_type": "وسيط / منصة عقارية",
            }
        )
    return rows


def _valid_monthly_rent(value):
    return isinstance(value, (int, float)) and MIN_MONTHLY_RENT <= value <= MAX_MONTHLY_RENT


def _valid_size(value):
    return isinstance(value, (int, float)) and MIN_SIZE <= value <= MAX_SIZE


def collect_rows():
    rows = []
    seen = set()

    for area, qoshan_slug, bayut_slug, opensooq_slug in base.AREAS:
        candidates = []
        candidates.extend(scrape_qoshan_rentals(qoshan_slug))
        candidates.extend(scrape_bayut_rentals(bayut_slug))
        candidates.extend(scrape_opensooq_rentals(opensooq_slug))

        accepted = 0
        for candidate in candidates:
            base.fix_size(candidate)
            title = candidate.get("title") or ""
            if not base.is_apt(title):
                continue

            period = candidate.get("period") or _rent_period(title, candidate.get("url"))
            furnishing = candidate.get("furnishing") or _furnishing(title)
            monthly = _monthly_price(candidate.get("price"), period)
            size = candidate.get("size")
            key = (
                candidate.get("url") or title[:80],
                candidate.get("price"),
                size,
            )
            if key in seen:
                continue
            seen.add(key)

            record = {
                "area": area,
                "furnishing": furnishing,
                "period": period,
                "period_label": _period_label(period),
                "price": candidate.get("price"),
                "monthly_price": monthly,
                "size": size,
                "source": candidate.get("source"),
                "title": title,
                "url": candidate.get("url") or "",
                "advertiser_type": candidate.get("advertiser_type", "غير محدد"),
            }
            if _valid_monthly_rent(monthly) and _valid_size(size):
                record["monthly_price_per_sqm"] = round(monthly / size, 2)
            else:
                record["monthly_price_per_sqm"] = None
            rows.append(record)
            accepted += 1

        print(f"{area}: {accepted} rental listings", flush=True)

    return rows


def _quartile(values, fraction):
    values = sorted(values)
    index = fraction * (len(values) - 1)
    low = math.floor(index)
    high = math.ceil(index)
    return values[low] if low == high else values[low] + (values[high] - values[low]) * (index - low)


def evaluate(rows):
    stats = {}
    for area, _, _, _ in base.AREAS:
        for furnishing in ("مفروشة", "غير مفروشة"):
            values = [
                row["monthly_price_per_sqm"]
                for row in rows
                if row["area"] == area
                and row["furnishing"] == furnishing
                and row.get("monthly_price_per_sqm") is not None
            ]
            if values:
                stats[(area, furnishing)] = {
                    "sample_size": len(values),
                    "median_monthly_per_sqm": round(st.median(values), 2),
                    "q1_monthly_per_sqm": round(_quartile(values, 0.25), 2),
                    "q3_monthly_per_sqm": round(_quartile(values, 0.75), 2),
                }

    evaluated = []
    for row in rows:
        item = dict(row)
        reference = stats.get((item["area"], item["furnishing"]))
        rate = item.get("monthly_price_per_sqm")
        if reference and rate is not None:
            median = reference["median_monthly_per_sqm"]
            q1 = reference["q1_monthly_per_sqm"]
            q3 = reference["q3_monthly_per_sqm"]
            item["reference_monthly_rent"] = round(median * item["size"], 2)
            item["difference_from_reference_pct"] = round(
                (item["monthly_price"] - item["reference_monthly_rent"])
                / item["reference_monthly_rent"]
                * 100
            )
            item["outlier_warning"] = rate < 0.6 * median
            if rate < q1:
                item["value_label"] = "🟢 فرصة إيجار"
            elif rate <= median:
                item["value_label"] = "✅ عند/دون مرجع العرض"
            elif rate <= q3:
                item["value_label"] = "🟡 أعلى من مرجع العرض"
            else:
                item["value_label"] = "🔴 أعلى من مرجع العرض"
            if reference["sample_size"] < 3:
                item["value_label"] += " (عيّنة صغيرة)"
        else:
            item.update(
                reference_monthly_rent=None,
                difference_from_reference_pct=None,
                outlier_warning=False,
                value_label="— بيانات مقارنة غير كافية",
            )
        evaluated.append(item)

    return stats, evaluated


def select_deals(rows, furnishing):
    candidates = [
        row
        for row in rows
        if row["furnishing"] == furnishing
        and row.get("url")
        and row.get("monthly_price_per_sqm") is not None
        and row.get("difference_from_reference_pct") is not None
        and not row.get("outlier_warning")
        and row.get("value_label", "").startswith(("🟢", "✅"))
    ]
    candidates.sort(
        key=lambda row: (
            row["difference_from_reference_pct"],
            row["monthly_price_per_sqm"],
            row["monthly_price"],
        )
    )
    return candidates[:TOP_PER_TYPE]


def run():
    rows = collect_rows()
    stats, listings = evaluate(rows)
    furnished = select_deals(listings, "مفروشة")
    unfurnished = select_deals(listings, "غير مفروشة")

    today = datetime.date.today().isoformat()
    summary = {
        "date": today,
        "areas": [],
        "total_listings": len(listings),
        "furnished_count": sum(row["furnishing"] == "مفروشة" for row in listings),
        "unfurnished_count": sum(row["furnishing"] == "غير مفروشة" for row in listings),
        "unknown_furnishing_count": sum(row["furnishing"] == "غير محدد" for row in listings),
        "top_per_type": TOP_PER_TYPE,
        "telegram_delivery": False,
    }
    for area, _, _, _ in base.AREAS:
        area_stats = {"name": area}
        for furnishing, key in (
            ("مفروشة", "furnished"),
            ("غير مفروشة", "unfurnished"),
        ):
            reference = stats.get((area, furnishing))
            if reference:
                area_stats[key] = reference
        summary["areas"].append(area_stats)

    base.write_json("rentals_summary.json", summary, indent=1)
    base.write_json("rentals_listings.json", listings)
    base.write_json("rentals_furnished_top_deals.json", furnished, indent=1)
    base.write_json("rentals_unfurnished_top_deals.json", unfurnished, indent=1)
    base.write_json(
        "rentals_top_deals.json",
        {"furnished": furnished, "unfurnished": unfurnished},
        indent=1,
    )

    print(
        "DONE · rental listings: "
        f"{len(listings)} · furnished: {len(furnished)} · "
        f"unfurnished: {len(unfurnished)} · date: {today}",
        flush=True,
    )


if __name__ == "__main__":
    run()
