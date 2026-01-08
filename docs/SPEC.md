# Attention Stock Monitor - Specification

## 1. Summary
Build a Python CLI tool that pulls TWSE (TSE) and TPEx (OTC) "注意交易資訊" data, normalizes it, applies rule-based screening, and outputs a daily risk table plus a CSV report. The tool is intended for a risk/compliance analyst to compile a daily report.

## 2. Scope and Goals
- Fetch official TSE/OTC attention stock data for a recent date range.
- Normalize fields across markets to a unified schema.
- Extract key numeric signals via regex.
- Apply the 6-day cumulative attention rule and the TSE "yesterday clauses 1-3" rule.
- Collect a user-provided exclusion list and mark status accordingly.
- Output a formatted console table and a UTF-8 BOM CSV report.

Non-goals:
- Web UI, API service, or persistent storage.
- Real-time streaming or intraday refresh.
- Advanced ranking beyond rule-based triggers.

## 3. Data Sources
Primary sources (CSV preferred, HTML fallback):
- TSE: https://www.twse.com.tw/zh/announcement/notice.html
- OTC: https://www.tpex.org.tw/zh-tw/announce/market/attention.html

Notes from example data:
- TSE CSV uses Big5/CP950 encoding; HTML is UTF-8.
- OTC HTML uses rowspans and `<br>` to separate multiple clauses.

## 4. Data Fetching
- CLI flag `--days N` (default 10) controls the analysis window size.
- Fetch a broad date range that covers at least the last N trading days:
  - End date = local "today".
  - Start date = today - 30 calendar days (to reliably cover N trading days).
- After fetch, compute the latest N distinct trading dates across combined TSE+OTC data and restrict analysis to those dates.
- If CSV fetch fails, fallback to HTML for that market.
- If one market fails entirely, proceed with the other and emit a warning.

## 5. Normalized Schema
Unified fields (base columns):
- 市場: "TSE" or "OTC"
- 代號: stock code (string)
- 名稱: stock name (string)
- 日期: normalized date
- 注意交易資訊: raw attention text

Output base columns:
- 市場 | 代號 | 名稱 | 風險評級 | 觸發原因 | 最後注意日 | 狀態

## 6. Date Normalization
- Input dates are ROC format (e.g., 115/01/07 or 115.01.07).
- Convert ROC year to Gregorian year: `year + 1911`.
- Output format: `YYYY-MM-DD`.
- Latest date for TSE "yesterday clauses 1-3" rule is the maximum date in TSE data only.

## 7. Regex Extraction (CSV extra columns)
Extract from "注意交易資訊":
- 成交量放大倍數: match patterns like "放大 x 倍 / 為 x 倍 / 之 x 倍"
  - Regex example: `(?:放大|為|之)\\s*([0-9]+(?:\\.[0-9]+)?)\\s*倍`
- 漲幅%: match patterns like "漲幅達 x% / 漲幅 x%"
  - Regex example: `漲幅(?:達)?\\s*([0-9]+(?:\\.[0-9]+)?)%`
- TSE第一款: 1 if text contains any of:
  - "第一款" or "第1款"
  - "累積收盤價漲幅"
  - Else 0

If multiple numeric values are found in one field, keep the **max** value.
Missing values:
- CSV: empty string
- Console: "-"

## 8. Clause Detection
Supported clause markers:
- Chinese numerals: 第一款/第二款/第三款/第十款
- Arabic numerals: 第1款/第2款/第3款/第10款

Clause detection is used for:
- Excluding 第十款 from 6-day occurrence counting.
- Identifying 第一到第三款 for the TSE "昨日公布" rule.

## 9. Analysis Logic
### 9.1 Window Definition
- Compute the latest 6 distinct trading dates across combined TSE+OTC data.
- A row contributes to 6-day counts only if its 日期 is in those 6 dates.

### 9.2 Counting Occurrences
- Each row counts as one occurrence, even if multiple rows share the same date.
- For 6-day counts, exclude any row that contains 第十款 anywhere.

### 9.3 Trigger Rules
TSE stock is flagged if:
- 6-day count (excluding 第十款) >= 3, OR
- Latest TSE date contains any 第一/第二/第三款 (Chinese or Arabic),
  even if 第十款 is also present.

OTC stock is flagged if:
- 6-day count (excluding 第十款) >= 3.

### 9.4 Aggregation
Output is one row per (市場, 代號), aggregated across dates.
- 最後注意日: latest date for that stock in fetched data.
- 觸發原因:
  - "近六日三次注意" if 6-day rule fires.
  - "昨日第一到第三款" if TSE latest-date clause rule fires.
  - If both, join with "；".

## 10. User Interaction
Prompt (always):
```
請輸入今日已公布自結的股票代號（用空白分隔）：
```
Input handling:
- Split on whitespace and commas.
- Trim tokens; keep codes as strings.
- Empty input => empty list.

## 11. Risk Rating and Status
- 狀態:
  - If code is in user input list: "✅ 已公告 (排除)"
  - Else: "⚠️ 未公告 (高風險)"
- 風險評級:
  - "低風險" for 已公告
  - "高風險" for 未公告

## 12. Output
### 12.1 Console
Use `tabulate` to print a table with columns:
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

Sorting:
- Market then code (TSE first, then OTC).

### 12.2 CSV
- UTF-8 with BOM.
- Columns in the same order as console.
- Filename pattern when `--output` not provided:
  - `output/attention_{start}_{end}.csv`
  - `{start}` and `{end}` are the earliest and latest dates of the latest N trading days,
    formatted as `YYYYMMDD`.
- If `--output PATH` is provided, write exactly to that path.

## 13. CLI Interface
Required:
- `--days N` (default 10): number of trading days to include in the analysis window.

Optional:
- `--output PATH`: CSV output path (overrides auto filename).

## 14. Error Handling and Warnings
- If a market fetch fails: warn and proceed with the other market.
- If both markets fail: exit with a clear error.
- If no rows match trigger rules: output headers with no data rows.

## 15. Implementation Notes
- Use `requests` or `pandas.read_csv`/`read_html`.
- Ensure proper decoding: CP950 for CSV, UTF-8 for HTML.
- For OTC HTML rowspans, propagate missing cell values to align row data.
- Always normalize dates before window calculations and comparisons.
