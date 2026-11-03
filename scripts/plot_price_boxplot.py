
import csv
import re
from pathlib import Path

import matplotlib.pyplot as plt


# --------------------------------------------------
# Configuration
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

DATA_FILE = ROOT / "data" / "processed" / "cars_bama_prepared.csv"
OUTPUT_DIR = ROOT / "reports" / "figures"
OUTPUT_FILE = OUTPUT_DIR / "peugeot_206_207_boxplot.png"

P206 = "\u067e\u0698\u0648\u060c 206"
P207 = "\u067e\u0698\u0648\u060c 207"

MODELS = {
    P206: "Peugeot 206",
    P207: "Peugeot 207",
}

# Excluded from the primary cleaned analysis
REMOVE_MAIN = {
    "3lyqzepy",
    "uofpnmo4",
    "dgn4fnwu",
    "5xgiwbyw",
    "yyzkl74m",
}

# Additional exclusion for sensitivity analysis
REMOVE_SENSITIVITY = {"vi1cl4g7"}


# --------------------------------------------------
# Data loading
# --------------------------------------------------

def parse_number(value):
    try:
        return float(value) if value else None
    except (ValueError, TypeError):
        return None


def extract_listing_id(url):
    match = re.search(r"/detail-([^-]+)-", url or "")
    return match.group(1) if match else None


def load_data():
    groups = {P206: [], P207: []}

    with open(DATA_FILE, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            title = (row.get("title") or "").strip()

            if title not in groups:
                continue

            if row.get("analysis_price_status") != (
                "candidate_unverified_lumpsum"
            ):
                continue

            price = parse_number(row.get("price_value"))

            if price is None or price <= 0:
                continue

            listing_id = extract_listing_id(row.get("url"))

            groups[title].append({
                "id": listing_id,
                "price": price / 1_000_000_000,
            })

    return groups


# --------------------------------------------------
# Build the three datasets
# --------------------------------------------------

def prepare_datasets(groups):
    datasets = {
        "Original": {},
        "Cleaned": {},
        "Sensitivity": {},
    }

    found_ids = set()

    for model in MODELS:
        records = groups[model]

        original = records

        cleaned = [
            record for record in records
            if record["id"] not in REMOVE_MAIN
        ]

        sensitivity = [
            record for record in records
            if record["id"] not in (
                REMOVE_MAIN | REMOVE_SENSITIVITY
            )
        ]

        for record in records:
            if record["id"] in (
                REMOVE_MAIN | REMOVE_SENSITIVITY
            ):
                found_ids.add(record["id"])

        datasets["Original"][model] = [
            r["price"] for r in original
        ]

        datasets["Cleaned"][model] = [
            r["price"] for r in cleaned
        ]

        datasets["Sensitivity"][model] = [
            r["price"] for r in sensitivity
        ]

    expected_ids = REMOVE_MAIN | REMOVE_SENSITIVITY
    missing_ids = expected_ids - found_ids

    if missing_ids:
        raise ValueError(
            f"Some expected listing IDs were not found: {missing_ids}"
        )

    expected_counts = {
        "Original": {P206: 537, P207: 571},
        "Cleaned": {P206: 536, P207: 567},
        "Sensitivity": {P206: 536, P207: 566},
    }

    for dataset_name, model_counts in expected_counts.items():
        for model, expected in model_counts.items():
            actual = len(datasets[dataset_name][model])

            if actual != expected:
                raise ValueError(
                    f"{dataset_name} / {MODELS[model]}: "
                    f"expected {expected}, got {actual}"
                )

    return datasets


# --------------------------------------------------
# Plot
# --------------------------------------------------

def create_plot(datasets):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(
        1, 3,
        figsize=(16, 6),
        sharey=False
    )

    panels = [
        ("Original", "Original data", 22),
        ("Cleaned", "Cleaned data", 5),
        ("Sensitivity", "Sensitivity analysis", 5),
    ]

    for ax, (key, title, y_max) in zip(axes, panels):
        values = [
            datasets[key][P206],
            datasets[key][P207],
        ]

        labels = [
            f"Peugeot 206\n(n={len(values[0])})",
            f"Peugeot 207\n(n={len(values[1])})",
        ]

        ax.boxplot(
            values,
            tick_labels=labels,
            showmeans=True,
            meanline=False,
            patch_artist=False,
            whis=1.5,
            flierprops={
                "marker": "o",
                "markersize": 3,
                "markerfacecolor": "none",
            },
        )

        ax.set_title(title, fontsize=12, pad=12)
        ax.set_ylabel("Price (billion Toman)")
        ax.set_ylim(0, y_max)
        ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.suptitle(
        "Peugeot 206 vs Peugeot 207 - Price Distribution",
        fontsize=15,
        fontweight="bold",
    )

    fig.text(
        0.5,
        0.015,
        "Boxes: IQR | Center line: Median | "
        "Triangle: Mean | Whiskers: 1.5 x IQR",
        ha="center",
        fontsize=9,
    )

    plt.tight_layout(rect=[0, 0.06, 1, 0.92])

    fig.savefig(
        OUTPUT_FILE,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(fig)


def main():
    groups = load_data()
    datasets = prepare_datasets(groups)
    create_plot(datasets)


if __name__ == "__main__":
    main()
