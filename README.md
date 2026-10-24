# Iran Car Market (Bama)

Collects used/new car listings from Bama's public search API, flags
questionable prices, and produces summary tables and charts.

## Layout

```
config.py                    all paths in one place
run.py                       pipeline runner
scraper/bama_api_scraper.py  Bama API  -> data/raw/cars_bama_api.csv
processing/build_dataset.py  raw       -> data/processed/cars_bama_prepared.csv
analysis/charts_overview.py  basic charts + tables
analysis/charts_detailed.py  detailed charts + tables
data/raw, data/processed     datasets
reports/                     summary CSVs and figures/{overview,detailed}
```

## Usage

```bash
pip install -r requirements.txt
python run.py scrape    # optional, needs internet (~500 pages, ~15k ads)
python run.py all       # build dataset + all reports
```

## Price handling

Rows are never deleted. `analysis_price_status` records why a price is or
is not trusted (first matching rule wins):

| Status | Rule |
|---|---|
| review_extreme_high_price | price > 100,000,000,000 |
| review_suspicious_low_price | 0 < price < 100,000,000 |
| review_non_lumpsum | price type is not lumpsum/negotiable (e.g. installment) |
| review_payment_terms | description mentions instalments, cheques, leasing… |
| missing_price | no positive price (negotiable) |
| candidate_unverified_lumpsum | everything else |

Only `candidate_unverified_lumpsum` rows
(`eligible_for_initial_price_analysis`) are used in price charts. These are
listing prices, not verified cash prices, and the data is a sample of the
site (the API stops at 500 pages), not the full catalogue.
