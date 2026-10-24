"""Build the analysis-ready car dataset from the raw Bama API scrape.

raw/cars_bama_api.csv  ->  processed/cars_bama_prepared.csv

This merges two former steps (price review + dataset preparation) into one.
Nothing is deleted: suspicious rows are only flagged.
"""
import re

import pandas as pd

from config import PREPARED_FILE, RAW_FILE

PRICE_LOW_LIMIT = 100_000_000          # below this a "price" is suspicious
PRICE_HIGH_LIMIT = 100_000_000_000     # above this a "price" is extreme
MILEAGE_LIMIT = 500_000

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def parse_number(value):
    if pd.isna(value):
        return None
    text = str(value).strip().translate(PERSIAN_DIGITS)
    text = text.replace(",", "").replace("٬", "")
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


def parse_mileage(value):
    if pd.isna(value):
        return None
    if "صفر کیلومتر" in str(value):
        return 0
    return parse_number(value)


def classify_year(value):
    year = parse_number(value)
    if year is None:
        return "unknown"
    if 1300 <= year <= 1499:
        return "solar_hijri"
    if 1900 <= year <= 2035:
        return "gregorian"
    return "out_of_range"


def classify_price(df):
    """Assign analysis_price_status. The first matching rule wins."""
    price = pd.to_numeric(df["price_value"], errors="coerce")
    has_terms = (
        df["payment_terms_in_description"].astype(str).str.lower()
        .isin(["true", "1"])
    )
    rules = [
        ("review_extreme_high_price", price > PRICE_HIGH_LIMIT),
        ("review_suspicious_low_price",
         (price > 0) & (price < PRICE_LOW_LIMIT)),
        ("review_non_lumpsum",
         ~df["price_type"].isin(["lumpsum", "negotiable"])),
        ("review_payment_terms", has_terms),
        ("missing_price", price.isna() | (price <= 0)),
    ]
    status = pd.Series("candidate_unverified_lumpsum", index=df.index)
    for name, condition in reversed(rules):   # reversed => first rule wins
        status = status.where(~condition, name)
    return status


def main():
    df = pd.read_csv(RAW_FILE, encoding="utf-8-sig", low_memory=False)

    df["analysis_price_status"] = classify_price(df)
    df["eligible_for_initial_price_analysis"] = (
        df["analysis_price_status"] == "candidate_unverified_lumpsum"
    )

    df["price_value"] = pd.to_numeric(df["price_value"], errors="coerce")
    df["model_year_numeric"] = df["model_year_raw"].map(parse_number)
    df["model_year_system"] = df["model_year_raw"].map(classify_year)
    df["mileage_km"] = df["mileage_raw"].map(parse_mileage)

    df["price_suspicious_low"] = (
        df["price_value"].notna()
        & (df["price_value"] > 0)
        & (df["price_value"] < PRICE_LOW_LIMIT)
    )
    df["price_extreme_high"] = df["price_value"] > PRICE_HIGH_LIMIT
    df["mileage_suspicious"] = (
        df["mileage_km"].notna() & (df["mileage_km"] > MILEAGE_LIMIT)
    )
    df["year_out_of_range"] = df["model_year_system"].eq("out_of_range")

    PREPARED_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PREPARED_FILE, index=False, encoding="utf-8-sig")

    print("BAMA PREPARED DATASET")
    print("=" * 45)
    print(f"Rows saved: {len(df):,}")
    print(f"Output: {PREPARED_FILE}")
    print("\nPrice status:")
    print(df["analysis_price_status"].value_counts().to_string())
    print("\nYear system:")
    print(df["model_year_system"].value_counts(dropna=False).to_string())
    print(f"\nMissing mileage: {df['mileage_km'].isna().sum():,}")
    print(f"Suspicious mileage > {MILEAGE_LIMIT:,} km: "
          f"{df['mileage_suspicious'].sum():,}")


if __name__ == "__main__":
    main()
