# Implementation Plan

This plan implements the CLI tool described in `SPEC.md` end-to-end, including data fetching, parsing, analysis, and outputs.

## 1. Project Setup
1. Create a top-level entry script (e.g., `main.py`).
2. Add a minimal package layout if desired:
   - `attention/` for core logic
   - `attention/__init__.py`
   - `attention/fetch.py`
   - `attention/parse.py`
   - `attention/analysis.py`
   - `attention/output.py`
   - `attention/cli.py`
3. Add a requirements file with dependencies:
   - `requests`
   - `pandas`
   - `tabulate`
   - `python-dateutil` (optional if parsing dates manually)

## 2. CLI Interface
1. Implement argument parsing:
   - `--days N` (default 10)
   - `--output PATH` (optional)
2. At runtime, prompt for user input with:
   - `請輸入今日已公布自結的股票代號（用空白分隔）：`
3. Normalize user input:
   - Split on whitespace and commas
   - Trim tokens
   - Keep as strings
   - Empty input -> empty list

## 3. Date Helpers
1. Implement ROC-to-Gregorian conversion:
   - Accept `YYY/MM/DD` and `YYY.MM.DD`
   - Convert `year + 1911`
2. Implement output format:
   - `YYYY-MM-DD` for all printed and stored dates
3. Implement date ordering and range helpers:
   - Sort distinct trading dates
   - Slice latest N distinct dates

## 4. Fetching Data
1. Build date range:
   - End date = today
   - Start date = today - 30 calendar days
2. TSE fetch:
   - Try CSV endpoint first; decode as CP950
   - If CSV fails, fetch HTML and parse
3. OTC fetch:
   - Try CSV endpoint first; decode as CP950
   - If CSV fails, fetch HTML and parse
4. Failure handling:
   - If one market fails, warn and proceed with the other
   - If both fail, exit with clear error

## 5. Parsing and Normalization
1. Normalize column names to:
   - `市場`, `代號`, `名稱`, `日期`, `注意交易資訊`
2. For CSV parsing:
   - Skip title/header rows as needed
   - Map source columns to the normalized schema
3. For HTML parsing:
   - Use `pandas.read_html` or BeautifulSoup
   - For OTC, handle rowspans and `<br>`-separated clauses
4. Normalize date values immediately upon ingestion

## 6. Regex Extraction
1. Compile regex patterns:
   - `成交量放大倍數`: `(?:放大|為|之)\s*([0-9]+(?:\.[0-9]+)?)\s*倍`
   - `漲幅%`: `漲幅(?:達)?\s*([0-9]+(?:\.[0-9]+)?)%`
2. Extract all matches per row; keep the max value
3. Set missing values to empty string for CSV
4. Compute `TSE第一款`:
   - 1 if text contains `第一款`, `第1款`, or `累積收盤價漲幅`
   - else 0

## 7. Clause Detection
1. Detect clause markers for:
   - 第一/第二/第三/第十款
   - 第1/第2/第3/第10款
2. Implement helpers:
   - `has_clause(text, clause_set)`
   - `has_clause_1_3(text)`
   - `has_clause_10(text)`

## 8. Analysis Logic
1. Build combined dataset from both markets
2. Compute latest N distinct trading dates globally
3. Restrict data to the latest 6 distinct trading dates for counting
4. For each (市場, 代號):
   - Count occurrences within last 6 dates, excluding rows with 第十款
   - Determine if the 6-day rule fires
   - For TSE only: check if the latest TSE date rows contain clause 1-3
5. Aggregate output rows per (市場, 代號):
   - `最後注意日`: max date for the stock in fetched data
   - `觸發原因`:
     - `近六日三次注意` if count >= 3
     - `昨日第一到第三款` if TSE clause rule fires
     - Join with `；` if both

## 9. Status and Risk Rating
1. Build user input set from prompt
2. For each output row:
   - If code in set: `狀態 = ✅ 已公告 (排除)`, `風險評級 = 低風險`
   - Else: `狀態 = ⚠️ 未公告 (高風險)`, `風險評級 = 高風險`

## 10. Output Formatting
1. Sort rows by market then code (TSE then OTC)
2. Console output:
   - Use `tabulate`
   - Columns in order:
     1) 市場
     2) 代號
     3) 名稱
     4) 風險評級
     5) 觸發原因
     6) 最後注意日
     7) 狀態
     8) 成交量放大倍數
     9) 漲幅%
     10) TSE第一款
3. CSV output:
   - UTF-8 with BOM
   - Same column order as console
   - If `--output` is not provided, filename:
     - `attention_{start}_{end}.csv`
     - `start/end` from the latest N trading days, formatted `YYYYMMDD`

## 11. Testing and Validation (Local)
1. Use `example_data/` as fixtures:
   - Verify CP950 CSV decoding
   - Verify HTML parsing on saved pages
2. Validate date conversion:
   - ROC to Gregorian
   - Sorting and window selection
3. Validate logic:
   - 6-day counts excluding 第十款
   - TSE clause 1-3 detection on latest TSE date
4. Smoke test output:
   - Console rendering
   - CSV file contents and encoding

## 12. Documentation
1. Add a short `README.md` (optional):
   - Usage examples
   - Expected outputs
   - Notes on encoding and data sources
