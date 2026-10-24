"""Run the car-market pipeline.

    python run.py scrape    # download listings from Bama (needs internet)
    python run.py build     # raw CSV -> analysis-ready CSV
    python run.py report    # tables + charts
    python run.py all       # build + report (scrape is opt-in)
"""
import runpy
import sys

STEPS = {
    "scrape": ["scraper.bama_api_scraper"],
    "build": ["processing.build_dataset"],
    "report": ["analysis.charts_overview", "analysis.charts_detailed"],
    "all": ["processing.build_dataset",
            "analysis.charts_overview", "analysis.charts_detailed"],
}


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    if step not in STEPS:
        sys.exit(__doc__)
    for module in STEPS[step]:
        print(f"\n>>> {module}")
        runpy.run_module(module, run_name="__main__")


if __name__ == "__main__":
    main()
