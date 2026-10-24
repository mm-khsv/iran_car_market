"""Central paths for the car-market project.

Every script imports its paths from here, so the project works no matter
which directory it is launched from.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

RAW_FILE = RAW_DIR / "cars_bama_api.csv"
PREPARED_FILE = PROCESSED_DIR / "cars_bama_prepared.csv"
SCRAPE_SUMMARY_FILE = REPORTS_DIR / "bama_api_scrape_summary.txt"
