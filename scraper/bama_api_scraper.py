
import csv
import json
import re
import time
from urllib.parse import urljoin

import requests

from config import RAW_FILE, SCRAPE_SUMMARY_FILE


BASE_URL = "https://bama.ir"
API_URL = f"{BASE_URL}/cad/api/search"

OUTPUT_FILE = RAW_FILE
REPORT_FILE = SCRAPE_SUMMARY_FILE

PAGE_SIZE = 12
REQUEST_DELAY = 0.8
TIMEOUT = 30
MAX_PAGES = 500

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{BASE_URL}/car",
}


def clean_text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def to_number(value):
    """Convert Persian/Arabic digits and separators to a number."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    translation = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )
    text = text.translate(translation)
    text = text.replace(",", "").replace("٬", "").replace("،", "")

    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None

    try:
        number = float(match.group())
        return int(number) if number.is_integer() else number
    except ValueError:
        return None


def parse_mileage(value):
    text = clean_text(value)
    if not text:
        return None

    if "صفر" in text:
        return 0

    return to_number(text)


def extract_record(item):
    detail = item.get("detail") or {}
    price = item.get("price") or {}
    specs = item.get("specs") or {}
    dealer = item.get("dealer") or {}
    images = item.get("images") or []

    code = clean_text(detail.get("code"))
    relative_url = clean_text(detail.get("url"))

    if relative_url:
        url = urljoin(BASE_URL, relative_url)
    elif code:
        url = f"{BASE_URL}/car/detail-{code}"
    else:
        url = ""

    image_url = ""
    if images and isinstance(images, list):
        first_image = images[0] or {}
        image_url = clean_text(
            first_image.get("large")
            or first_image.get("small")
            or first_image.get("thumb")
        )

    raw_price = to_number(price.get("price"))
    raw_prepayment = to_number(price.get("prepayment"))
    raw_payment = to_number(price.get("payment"))

    price_type = clean_text(price.get("type")).lower()

    # A zero or absent price is not a usable market price.
    usable_price = (
        raw_price
        if raw_price is not None and raw_price > 0
        else None
    )

    description = clean_text(detail.get("description"))

    # Keep payment-related signals for later price auditing.
    payment_terms = bool(
        re.search(
            r"اقساط|اقساطی|قسط|پیش.?پرداخت|بازپرداخت|"
            r"ماهیانه|ماهانه|چک|لیزینگ|تسهیلات",
            description,
            flags=re.IGNORECASE,
        )
    )

    if price_type == "lumpsum" and usable_price is not None:
        price_status = (
            "lumpsum_requires_text_review"
            if payment_terms
            else "lumpsum_unverified"
        )
    elif price_type == "negotiable":
        price_status = "negotiable_or_price_unavailable"
    elif price_type:
        price_status = f"review_price_type_{price_type}"
    else:
        price_status = "unknown_price_type"

    return {
        "source": "bama_api",
        "code": code,
        "url": url,
        "title": clean_text(detail.get("title")),
        "subtitle": clean_text(detail.get("subtitle")),
        "brand": clean_text(detail.get("brand_fa")),
        "brand_slug": clean_text(detail.get("brand")),
        "model_year_raw": clean_text(detail.get("year")),
        "mileage_raw": clean_text(detail.get("mileage")),
        "mileage_km": parse_mileage(detail.get("mileage")),
        "transmission": clean_text(detail.get("transmission")),
        "fuel_type": clean_text(detail.get("fuel")),
        "body_type": clean_text(
            detail.get("body_type_fa") or detail.get("body_type")
        ),
        "color": clean_text(detail.get("color")),
        "body_status": clean_text(detail.get("body_status")),
        "location": clean_text(detail.get("location")),
        "price_type": price_type,
        "price_value": usable_price,
        "prepayment_value": raw_prepayment,
        "payment_value": raw_payment,
        "installments": to_number(price.get("installments")),
        "month_number": to_number(price.get("month_number")),
        "delivery_days": to_number(price.get("delivery_days")),
        "price_status": price_status,
        "payment_terms_in_description": payment_terms,
        "description": description,
        "engine": clean_text(
            detail.get("engine") or specs.get("engine")
        ),
        "volume": clean_text(
            detail.get("volume") or specs.get("volume")
        ),
        "battery_capacity": clean_text(
            detail.get("battery_capacity")
            or specs.get("battery_capacity")
        ),
        "all_electric_range": clean_text(
            detail.get("all_electric_range")
            or specs.get("all_electric_range")
        ),
        "image": image_url or clean_text(detail.get("image")),
        "image_count": to_number(detail.get("image_count")),
        "dealer_name": clean_text(dealer.get("name")),
        "dealer_type": clean_text(dealer.get("type")),
        "dealer_url": (
            urljoin(BASE_URL, clean_text(dealer.get("link")))
            if dealer.get("link")
            else ""
        ),
        "modified_date": clean_text(detail.get("modified_date")),
        "cursor": clean_text(item.get("cursor")),
    }



def fetch_page(session, page_index):
    response = session.get(
        API_URL,
        params={
            "pageIndex": page_index,
            "pageSize": PAGE_SIZE,
        },
        timeout=TIMEOUT,
    )

    if not response.ok:
        raise RuntimeError(
            f"HTTP {response.status_code} on page {page_index}. "
            f"Response: {response.text[:1000]}"
        )

    try:
        payload = response.json()
    except ValueError as error:
        raise RuntimeError(
            f"API returned non-JSON response on page {page_index}: "
            f"{response.text[:500]}"
        ) from error

    if not isinstance(payload, dict):
        raise RuntimeError(
            f"Unexpected API response on page {page_index}: "
            f"{str(payload)[:500]}"
        )

    if payload.get("status") is False:
        raise RuntimeError(
            f"API status=false on page {page_index}: "
            f"{payload.get('errors', payload)}"
        )

    return payload


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)

    records_by_key = {}
    pages_visited = 0
    banners_skipped = 0
    errors = []
    reported_total = None

    try:
        for page_index in range(MAX_PAGES):
            try:
                payload = fetch_page(session, page_index)
            except Exception as error:
                errors.append(f"Page {page_index}: {error}")
                print(f"ERROR on page {page_index}: {error}")
                break

            pages_visited += 1
            metadata = payload.get("metadata") or {}
            data = payload.get("data") or {}
            ads = data.get("ads") or []

            reported_total = metadata.get("total_count", reported_total)
            has_next = metadata.get("has_next")

            valid_ads_on_page = 0

            for item in ads:
                if not isinstance(item, dict):
                    continue

                if item.get("type") != "ad":
                    banners_skipped += 1
                    continue

                detail = item.get("detail") or {}
                record = extract_record(item)

                if not record["code"] and not record["url"]:
                    continue

                key = record["code"] or record["url"]

                if key not in records_by_key:
                    records_by_key[key] = record
                    valid_ads_on_page += 1

            print(
                f"Page {page_index}: "
                f"API items={len(ads)}, "
                f"new ads={valid_ads_on_page}, "
                f"unique total={len(records_by_key)}, "
                f"has_next={has_next}"
            )

            if has_next is False:
                break

            # Older or inconsistent API responses may omit has_next.
            if has_next is None and not ads:
                break

            time.sleep(REQUEST_DELAY)

        records = list(records_by_key.values())

        if records:
            fieldnames = list(records[0].keys())
            with OUTPUT_FILE.open(
                "w",
                newline="",
                encoding="utf-8-sig",
            ) as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=fieldnames,
                    extrasaction="ignore",
                )
                writer.writeheader()
                writer.writerows(records)

        price_count = sum(
            row["price_value"] is not None for row in records
        )
        mileage_count = sum(
            row["mileage_km"] is not None for row in records
        )
        year_count = sum(
            bool(row["model_year_raw"]) for row in records
        )
        lumpsum_count = sum(
            row["price_type"] == "lumpsum" for row in records
        )

        summary = [
            "BAMA API SCRAPE SUMMARY",
            "=" * 40,
            f"Pages visited: {pages_visited}",
            f"API total_count (last response): {reported_total}",
            f"Unique ads saved: {len(records)}",
            f"Ads with positive numeric price: {price_count}",
            f"Ads with mileage: {mileage_count}",
            f"Ads with model year: {year_count}",
            f"Ads marked lumpsum: {lumpsum_count}",
            f"Non-ad items skipped: {banners_skipped}",
            f"Errors: {len(errors)}",
            f"CSV: {OUTPUT_FILE.resolve()}",
        ]

        if errors:
            summary.append("")
            summary.append("ERROR DETAILS:")
            summary.extend(errors)

        report_text = "\n".join(summary) + "\n"
        REPORT_FILE.write_text(report_text, encoding="utf-8")

        print("\n" + report_text)

    finally:
        session.close()


if __name__ == "__main__":
    main()
