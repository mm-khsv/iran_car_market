import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import FIGURES_DIR, PREPARED_FILE, REPORTS_DIR

SOURCE = PREPARED_FILE
OUT = FIGURES_DIR / "detailed"
REPORTS = REPORTS_DIR
MIN_GROUP = 40
RANDOM_STATE = 42

OUT.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)


def as_bool(s):
    return s.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])


def save(name):
    plt.tight_layout()
    plt.savefig(OUT / name, dpi=180, bbox_inches="tight")
    plt.close()
    print("Saved:", OUT / name)


def boxplot_groups(df, group_col, value_col, min_count=MIN_GROUP,
                   top_n=12, title="", filename="", log=True):
    if group_col not in df or value_col not in df:
        return

    counts = df[group_col].fillna("نامشخص").value_counts()
    groups = counts[counts >= min_count].head(top_n).index.tolist()
    if not groups:
        return

    samples, labels = [], []
    for group in groups:
        vals = df.loc[df[group_col].fillna("نامشخص") == group, value_col]
        vals = vals[pd.to_numeric(vals, errors="coerce").gt(0)].dropna()
        if len(vals) >= min_count:
            samples.append(vals.to_numpy())
            labels.append(str(group))

    if not samples:
        return

    plt.figure(figsize=(max(10, len(labels) * 1.05), 7))
    plt.boxplot(samples, tick_labels=labels, showfliers=False)
    if log:
        plt.yscale("log")
    plt.title(title)
    plt.ylabel("Listed price (source units)" + ("; log scale" if log else ""))
    plt.xlabel(group_col)
    plt.xticks(rotation=35, ha="right")
    save(filename)


def main():
    df = pd.read_csv(SOURCE, encoding="utf-8-sig", low_memory=False)

    for col in ["price_value", "mileage_km", "model_year_numeric"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    candidates = as_bool(df["eligible_for_initial_price_analysis"])
    all_rows = df.copy()
    data = df.loc[candidates].copy()
    data = data[data["price_value"].gt(0) & data["price_value"].notna()].copy()

    # Exclude extreme odometer values only from the main mileage plots.
    mileage = data[
        data["mileage_km"].notna()
        & data["mileage_km"].between(0, 500_000)
    ].copy()

    # 01: Price distribution with percentile markers.
    prices = data["price_value"]
    if len(prices):
        plt.figure(figsize=(10, 6))
        plt.hist(np.log10(prices), bins=45)
        ticks = [prices.quantile(q) for q in [0.25, 0.5, 0.75]]
        for value, label in zip(ticks, ["25th percentile", "Median", "75th percentile"]):
            plt.axvline(np.log10(value), linestyle="--", label=f"{label}: {value:,.0f}")
        plt.title("Listed price distribution among initial candidates")
        plt.xlabel("log10(listed price; source units)")
        plt.ylabel("Number of listings")
        plt.legend()
        save("01_price_distribution_percentiles.png")

    # 02: Price against mileage, sampled for readability.
    plot = mileage.copy()
    if len(plot) > 15000:
        plot = plot.sample(15000, random_state=RANDOM_STATE)

    used = plot[plot["mileage_km"] > 0]
    zero = plot[plot["mileage_km"] == 0]
    plt.figure(figsize=(11, 7))
    plt.scatter(used["mileage_km"], used["price_value"], s=13, alpha=0.35, label="Used")
    plt.scatter(zero["mileage_km"], zero["price_value"], s=18, alpha=0.45, label="Zero km")
    plt.yscale("log")
    plt.xlabel("Mileage (km)")
    plt.ylabel("Listed price (log scale)")
    plt.title("Mileage versus listed price")
    plt.legend()
    save("02_price_vs_mileage.png")

    # 03: Median price by mileage bands.
    bands = [-1, 0, 20000, 50000, 100000, 150000, 200000, 300000, 500000]
    labels = ["Zero", "1–20k", "20–50k", "50–100k", "100–150k",
              "150–200k", "200–300k", "300–500k"]
    mileage["mileage_band"] = pd.cut(
        mileage["mileage_km"], bins=bands, labels=labels, include_lowest=True
    )
    mileage_stats = mileage.groupby("mileage_band", observed=False).agg(
        listing_count=("price_value", "size"),
        median_price=("price_value", "median"),
        q25=("price_value", lambda s: s.quantile(0.25)),
        q75=("price_value", lambda s: s.quantile(0.75)),
    ).dropna(subset=["median_price"])
    mileage_stats.to_csv(REPORTS / "bama_mileage_band_summary.csv", encoding="utf-8-sig")
    if not mileage_stats.empty:
        plt.figure(figsize=(11, 6))
        plt.errorbar(
            mileage_stats.index.astype(str),
            mileage_stats["median_price"],
            yerr=[
                mileage_stats["median_price"] - mileage_stats["q25"],
                mileage_stats["q75"] - mileage_stats["median_price"],
            ],
            fmt="o-", capsize=4
        )
        plt.yscale("log")
        plt.xlabel("Mileage band")
        plt.ylabel("Median price and interquartile range (log scale)")
        plt.title("Price by mileage band")
        plt.xticks(rotation=25, ha="right")
        save("03_price_by_mileage_band.png")

    # 04: Price distribution by transmission.
    boxplot_groups(
        data, "transmission", "price_value", min_count=MIN_GROUP,
        top_n=10, title="Listed price by transmission",
        filename="04_price_by_transmission.png"
    )

    # 05: Price distribution by fuel type.
    boxplot_groups(
        data, "fuel_type", "price_value", min_count=MIN_GROUP,
        top_n=10, title="Listed price by fuel type",
        filename="05_price_by_fuel_type_boxplot.png"
    )

    # 06: Price distribution for the most represented brands.
    boxplot_groups(
        data, "brand", "price_value", min_count=MIN_GROUP,
        top_n=15, title="Listed price by brand (top brands with enough samples)",
        filename="06_price_by_brand_detailed.png"
    )

    # 07: Model year, calendar systems separated.
    years = data[
        data["model_year_system"].isin(["solar_hijri", "gregorian"])
        & data["model_year_numeric"].notna()
    ].copy()

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for ax, system, title in [
        (axes[0], "solar_hijri", "Solar Hijri years"),
        (axes[1], "gregorian", "Gregorian years"),
    ]:
        part = years[years["model_year_system"] == system]
        stats = part.groupby("model_year_numeric").agg(
            count=("price_value", "size"),
            median=("price_value", "median")
        )
        stats = stats[stats["count"] >= MIN_GROUP].sort_index()
        if len(stats):
            ax.plot(stats.index.astype(int).astype(str), stats["median"], marker="o")
            ax.tick_params(axis="x", rotation=45)
        else:
            ax.text(0.5, 0.5, "Insufficient data", ha="center", transform=ax.transAxes)
        ax.set_title(title)
        ax.set_xlabel("Raw model year")
        ax.set_ylabel("Median listed price")
        ax.set_yscale("log")
        ax.grid(alpha=0.25)
    fig.suptitle("Median listed price by model year (calendars kept separate)")
    save("07_price_by_model_year.png")

    # 08: Price by body condition.
    if "body_status" in data:
        boxplot_groups(
            data, "body_status", "price_value", min_count=MIN_GROUP,
            top_n=12, title="Listed price by body condition",
            filename="08_price_by_body_condition.png"
        )

    # 09: Median price by location, only locations with enough ads.
    if "location" in data:
        loc = data.copy()
        loc["location"] = loc["location"].fillna("نامشخص")
        loc_stats = loc.groupby("location").agg(
            listings=("price_value", "size"),
            median_price=("price_value", "median")
        )
        loc_stats = loc_stats[loc_stats["listings"] >= MIN_GROUP]
        loc_stats = loc_stats.sort_values("listings", ascending=False).head(15)
        loc_stats.to_csv(REPORTS / "bama_location_price_summary.csv", encoding="utf-8-sig")
        if not loc_stats.empty:
            plt.figure(figsize=(11, 7))
            loc_stats.sort_values("median_price")["median_price"].plot(kind="barh")
            plt.xlabel("Median listed price (source units)")
            plt.ylabel("Location")
            plt.title("Median listed price by location (top locations by sample size)")
            save("09_median_price_by_location.png")

    # 10: Heatmap of median price by fuel type and mileage band.
    heat = mileage.dropna(subset=["fuel_type", "mileage_band"]).copy()
    fuel_counts = heat["fuel_type"].value_counts()
    fuels = fuel_counts[fuel_counts >= MIN_GROUP].index.tolist()
    heat = heat[heat["fuel_type"].isin(fuels)]
    pivot = heat.pivot_table(
        index="fuel_type", columns="mileage_band",
        values="price_value", aggfunc="median", observed=False
    )
    if not pivot.empty:
        plt.figure(figsize=(12, max(5, 0.55 * len(pivot))))
        values = pivot.to_numpy(dtype=float)
        masked = np.ma.masked_invalid(values)
        image = plt.imshow(masked, aspect="auto", interpolation="nearest")
        plt.colorbar(image, label="Median listed price (source units)")
        plt.yticks(range(len(pivot.index)), pivot.index.astype(str))
        plt.xticks(range(len(pivot.columns)), pivot.columns.astype(str), rotation=25, ha="right")
        plt.title("Median price heatmap: fuel type × mileage band")
        plt.xlabel("Mileage band")
        plt.ylabel("Fuel type")
        save("10_price_heatmap_fuel_mileage.png")
        pivot.to_csv(REPORTS / "bama_fuel_mileage_price_heatmap.csv", encoding="utf-8-sig")

    # 11: Transmission and fuel mix.
    mix = pd.crosstab(data["fuel_type"].fillna("نامشخص"),
                      data["transmission"].fillna("نامشخص"))
    mix.to_csv(REPORTS / "bama_fuel_transmission_counts.csv", encoding="utf-8-sig")
    if not mix.empty:
        mix.plot(kind="bar", figsize=(12, 6))
        plt.title("Listing counts by fuel type and transmission")
        plt.xlabel("Fuel type")
        plt.ylabel("Number of listings")
        plt.xticks(rotation=30, ha="right")
        plt.legend(title="Transmission")
        save("11_fuel_transmission_counts.png")

    # 12: Price-review categories for the complete collected dataset.
    review_counts = all_rows["analysis_price_status"].fillna("unknown").value_counts()
    review_counts.to_csv(REPORTS / "bama_price_review_status_counts.csv", encoding="utf-8-sig")
    plt.figure(figsize=(11, 6))
    review_counts.sort_values().plot(kind="barh")
    plt.xlabel("Number of listings")
    plt.ylabel("Review status")
    plt.title("Price-review status across all collected listings")
    save("12_price_review_status.png")

    # Summary tables for later reporting.
    data.groupby("brand").agg(
        listings=("price_value", "size"),
        median_listed_price=("price_value", "median"),
        q25=("price_value", lambda s: s.quantile(.25)),
        q75=("price_value", lambda s: s.quantile(.75)),
    ).sort_values("listings", ascending=False).to_csv(
        REPORTS / "bama_brand_price_detailed_summary.csv", encoding="utf-8-sig"
    )

    years.groupby(["model_year_system", "model_year_numeric"]).agg(
        listings=("price_value", "size"),
        median_listed_price=("price_value", "median"),
    ).reset_index().to_csv(
        REPORTS / "bama_year_price_detailed_summary.csv",
        index=False, encoding="utf-8-sig"
    )

    print("\n" + "=" * 55)
    print("DETAILED BAMA ANALYSIS COMPLETE")
    print("=" * 55)
    print(f"All collected listings: {len(all_rows):,}")
    print(f"Initial price candidates: {len(data):,}")
    print(f"Listings in mileage range 0–500,000 km: {len(mileage):,}")
    print(f"Zero-kilometer candidates: {(data['mileage_km'] == 0).sum():,}")
    print(f"Charts folder: {OUT.resolve()}")
    print(f"Summary tables folder: {REPORTS.resolve()}")
    print("Note: prices are listing values, not independently verified cash prices.")


if __name__ == "__main__":
    main()
