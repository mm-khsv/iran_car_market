import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import FIGURES_DIR, PREPARED_FILE, REPORTS_DIR

SOURCE = PREPARED_FILE
OUT = FIGURES_DIR / "overview"
REPORTS = REPORTS_DIR

MIN_GROUP = 40
RANDOM_STATE = 42

OUT.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)


def as_bool(series):
    return series.astype(str).str.strip().str.lower().isin(
        ["true", "1", "yes"]
    )


def save_fig(name):
    plt.tight_layout()
    plt.savefig(OUT / name, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Saved: {OUT / name}")


def main():
    df = pd.read_csv(SOURCE, encoding="utf-8-sig", low_memory=False)

    for col in ["price_value", "mileage_km", "model_year_numeric"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    candidates = as_bool(df["eligible_for_initial_price_analysis"])
    data = df.loc[candidates].copy()
    data = data[
        data["price_value"].notna()
        & (data["price_value"] > 0)
    ].copy()

    # Keep suspicious mileage flagged, but exclude it from the main
    # mileage scatter so extreme odometer values do not dominate the view.
    mileage_data = data[
        data["mileage_km"].notna()
        & (data["mileage_km"] >= 0)
        & (data["mileage_km"] <= 500_000)
    ].copy()

    # 1. Most represented brands among initial price candidates
    brand_counts = data["brand"].fillna("نامشخص").value_counts().head(20)
    plt.figure(figsize=(11, 8))
    brand_counts.sort_values().plot(kind="barh")
    plt.title("Top 20 brands in initial price-analysis candidates")
    plt.xlabel("Number of listings")
    plt.ylabel("Brand")
    save_fig("01_top_brands.png")

    # 2. Mileage versus listed price; logarithmic price axis
    used = mileage_data[mileage_data["mileage_km"] > 0]
    zero = mileage_data[mileage_data["mileage_km"] == 0]

    # Sample large groups for readability; counts are printed below.
    if len(used) > 12000:
        used = used.sample(12000, random_state=RANDOM_STATE)
    if len(zero) > 3000:
        zero = zero.sample(3000, random_state=RANDOM_STATE)

    plt.figure(figsize=(11, 7))
    plt.scatter(
        used["mileage_km"], used["price_value"],
        alpha=0.35, s=14, label="Used"
    )
    plt.scatter(
        zero["mileage_km"], zero["price_value"],
        alpha=0.45, s=16, label="Zero km"
    )
    plt.yscale("log")
    plt.title("Mileage vs listed price")
    plt.xlabel("Mileage (km)")
    plt.ylabel("Listed price (source units, log scale)")
    plt.legend()
    save_fig("02_mileage_vs_price.png")

    # 3. Price distributions for brands with enough candidate listings
    brand_counts_all = data["brand"].value_counts()
    selected_brands = brand_counts_all[
        brand_counts_all >= MIN_GROUP
    ].head(12).index.tolist()

    box_data = [
        data.loc[data["brand"] == brand, "price_value"].dropna().values
        for brand in selected_brands
    ]
    box_labels = selected_brands

    if box_data:
        plt.figure(figsize=(max(12, len(box_labels) * 1.2), 7))
        plt.boxplot(
            box_data,
            tick_labels=box_labels,
            showfliers=False
        )
        plt.yscale("log")
        plt.title(
            f"Listed price distribution by brand "
            f"(brands with at least {MIN_GROUP} candidates; fliers hidden)"
        )
        plt.xlabel("Brand")
        plt.ylabel("Listed price (source units, log scale)")
        plt.xticks(rotation=35, ha="right")
        save_fig("03_price_by_brand.png")

    # 4. Median price by model year, keeping calendar systems separate.
    year_data = data[
        data["model_year_system"].isin(["solar_hijri", "gregorian"])
        & data["model_year_numeric"].notna()
    ].copy()

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    year_systems = [
        ("solar_hijri", "Solar Hijri model years"),
        ("gregorian", "Gregorian model years"),
    ]

    for ax, (system, title) in zip(axes, year_systems):
        subset = year_data[year_data["model_year_system"] == system]
        stats = (
            subset.groupby("model_year_numeric")["price_value"]
            .agg(["median", "count"])
        )
        stats = stats[stats["count"] >= MIN_GROUP].sort_index()

        if not stats.empty:
            ax.plot(
                stats.index.astype(int).astype(str),
                stats["median"],
                marker="o"
            )
            ax.tick_params(axis="x", rotation=45)
        else:
            ax.text(
                0.5, 0.5, "Not enough data",
                ha="center", va="center",
                transform=ax.transAxes
            )

        ax.set_title(title)
        ax.set_xlabel("Raw model year")
        ax.set_ylabel("Median listed price (source units)")
        ax.grid(True, alpha=0.25)

    fig.suptitle(
        f"Median listed price by model year "
        f"(minimum {MIN_GROUP} listings per year)"
    )
    save_fig("04_price_by_model_year_system.png")

    # 5. Median price by fuel type, only sufficiently represented groups
    fuel_data = data.copy()
    fuel_data["fuel_type"] = fuel_data["fuel_type"].fillna("نامشخص")
    fuel_stats = (
        fuel_data.groupby("fuel_type")["price_value"]
        .agg(["median", "count"])
    )
    fuel_stats = fuel_stats[fuel_stats["count"] >= MIN_GROUP]
    fuel_stats = fuel_stats.sort_values("median")

    if not fuel_stats.empty:
        plt.figure(figsize=(10, 6))
        fuel_stats["median"].plot(kind="barh")
        plt.title(
            f"Median listed price by fuel type "
            f"(minimum {MIN_GROUP} listings)"
        )
        plt.xlabel("Median listed price (source units)")
        plt.ylabel("Fuel type")
        save_fig("05_price_by_fuel_type.png")

    # 6. Sample coverage by price-review status
    status_counts = (
        df["analysis_price_status"]
        .fillna("unknown")
        .value_counts()
        .sort_values()
    )
    plt.figure(figsize=(11, 6))
    status_counts.plot(kind="barh")
    plt.title("Price review status across collected listings")
    plt.xlabel("Number of listings")
    plt.ylabel("Review status")
    save_fig("06_price_review_status.png")

    # Export compact summary tables
    data.groupby("brand").agg(
        listings=("price_value", "size"),
        median_listed_price=("price_value", "median"),
        mean_listed_price=("price_value", "mean"),
    ).sort_values("listings", ascending=False).to_csv(
        REPORTS / "bama_brand_price_summary.csv",
        encoding="utf-8-sig"
    )

    year_data.groupby(
        ["model_year_system", "model_year_numeric"]
    ).agg(
        listings=("price_value", "size"),
        median_listed_price=("price_value", "median"),
    ).reset_index().to_csv(
        REPORTS / "bama_year_price_summary.csv",
        index=False,
        encoding="utf-8-sig"
    )

    status_counts.rename("listing_count").to_csv(
        REPORTS / "bama_price_review_counts.csv",
        encoding="utf-8-sig"
    )

    print("\n" + "=" * 55)
    print("BAMA VISUALIZATION SUMMARY")
    print("=" * 55)
    print(f"All collected rows: {len(df):,}")
    print(f"Initial price candidates: {len(data):,}")
    print(f"Rows included in mileage plot: {len(mileage_data):,}")
    print(f"Rows with mileage > 500,000 excluded from mileage plot: "
          f"{(data['mileage_km'] > 500_000).sum():,}")
    print(f"Zero-kilometer candidates: {(data['mileage_km'] == 0).sum():,}")
    print(f"Brands shown in boxplot: {len(selected_brands)}")
    print(f"Output figures: {OUT.resolve()}")
    print("\nReminder: prices are listing values and are not independently")
    print("verified as final cash prices. This dataset is not the full Bama site.")


if __name__ == "__main__":
    main()
