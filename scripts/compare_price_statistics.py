
import csv
import re
from pathlib import Path

from scipy.stats import mannwhitneyu, ttest_ind


ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "processed" / "cars_bama_prepared.csv"

P206 = "\u067e\u0698\u0648\u060c 206"
P207 = "\u067e\u0698\u0648\u060c 207"

REMOVE_MAIN = {
    "3lyqzepy",
    "uofpnmo4",
    "dgn4fnwu",
    "5xgiwbyw",
    "yyzkl74m",
}

REMOVE_SENSITIVITY = {"vi1cl4g7"}


def number(value):
    try:
        return float(value) if value else None
    except (ValueError, TypeError):
        return None


def extract_id(url):
    match = re.search(r"/detail-([^-]+)-", url or "")
    return match.group(1) if match else None


def load_data():
    groups = {P206: [], P207: []}

    with open(DATA_FILE, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            title = (row.get("title") or "").strip()

            if title not in groups:
                continue

            if row.get("analysis_price_status") != (
                "candidate_unverified_lumpsum"
            ):
                continue

            price = number(row.get("price_value"))

            if price is None or price <= 0:
                continue

            groups[title].append({
                "id": extract_id(row.get("url")),
                "price": price / 1_000_000_000,
            })

    return groups


def describe(values):
    ordered = sorted(values)
    n = len(ordered)

    return {
        "n": n,
        "mean": sum(ordered) / n,
        "median": (
            ordered[n // 2]
            if n % 2
            else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
        ),
    }


def run_tests(name, data_206, data_207):
    result_206 = describe(data_206)
    result_207 = describe(data_207)

    mw = mannwhitneyu(
        data_207,
        data_206,
        alternative="two-sided",
        method="asymptotic",
    )

    welch = ttest_ind(
        data_207,
        data_206,
        equal_var=False,
        alternative="two-sided",
    )

    # Positive value means prices in 207 tend to be higher.
    cliffs_delta = (
        2 * mw.statistic / (len(data_207) * len(data_206)) - 1
    )

    print("\n" + "=" * 70)
    print(name)
    print("=" * 70)

    print("\nDescriptive statistics (billion Toman)")
    print(
        f"Peugeot 206: n={result_206['n']}, "
        f"mean={result_206['mean']:.3f}, "
        f"median={result_206['median']:.3f}"
    )
    print(
        f"Peugeot 207: n={result_207['n']}, "
        f"mean={result_207['mean']:.3f}, "
        f"median={result_207['median']:.3f}"
    )

    print("\nMann-Whitney U test")
    print(f"U statistic: {mw.statistic:.3f}")
    print(f"P-value: {mw.pvalue:.8g}")
    print(f"Cliff's delta: {cliffs_delta:.4f}")

    print("\nWelch independent t-test")
    print(f"t statistic: {welch.statistic:.3f}")
    print(f"P-value: {welch.pvalue:.8g}")

    print("\nDecision (alpha = 0.05)")
    if mw.pvalue < 0.05:
        print("Reject H0: evidence of a difference in distributions.")
    else:
        print("Fail to reject H0: insufficient evidence of a difference.")


def main():
    groups = load_data()

    original_206 = [r["price"] for r in groups[P206]]
    original_207 = [r["price"] for r in groups[P207]]

    cleaned_206 = [
        r["price"] for r in groups[P206]
        if r["id"] not in REMOVE_MAIN
    ]
    cleaned_207 = [
        r["price"] for r in groups[P207]
        if r["id"] not in REMOVE_MAIN
    ]

    sensitivity_206 = [
        r["price"] for r in groups[P206]
        if r["id"] not in (REMOVE_MAIN | REMOVE_SENSITIVITY)
    ]
    sensitivity_207 = [
        r["price"] for r in groups[P207]
        if r["id"] not in (REMOVE_MAIN | REMOVE_SENSITIVITY)
    ]

    run_tests("Original data", original_206, original_207)
    run_tests("Cleaned data", cleaned_206, cleaned_207)
    run_tests("Sensitivity analysis", sensitivity_206, sensitivity_207)


if __name__ == "__main__":
    main()
