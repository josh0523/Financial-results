# Attention Stock Monitor

CLI tool that fetches TWSE (TSE) and TPEx (OTC) attention stock data, applies rule-based screening, and outputs a risk table plus a CSV report.

## Requirements
- Python 3.10+
- Dependencies in `requirements.txt`

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage
```bash
# 預設看最近 6 個交易日的最新統計
python main.py

# 指定查看最近 10 個交易日的最新統計
python main.py --days 10

# 指定結束日期（例如查看 2026-01-05 那天的注意股狀態）
python main.py --date 2026-01-05

# 同時指定天數與日期
python main.py --days 10 --date 2026-01-05
```


You will be prompted:
```
請輸入今日已公布自結的股票代號（用空白分隔）：
```
Enter codes separated by spaces (or leave blank to mark all as unannounced).

Optional CSV output path:
```bash
python main.py --days 10 --output /path/to/report.csv
```

## Output
- Console: table with columns
  - 市場, 代號, 名稱, 風險評級, 觸發原因, 最後注意日, 狀態, 成交量放大倍數, 漲幅%, TSE第一款
- CSV: UTF-8 with BOM
  - Default path: `output/attention_{start}_{end}.csv`
  - `{start}` and `{end}` are the earliest and latest dates in the latest N trading days, formatted as `YYYYMMDD`

## Notes
- CSV is fetched first; HTML is used as fallback if CSV parsing fails.
- CSV source encoding is Big5/CP950; HTML is UTF-8.
- **Warrants (权证) are automatically filtered out**: Securities with 5 or more digits (e.g., 30061) are excluded from the analysis, as they do not publish self-disclosed earnings announcements.
- Rule summary:
  - TSE: 6-day count >= 3 (excluding 第十款) OR latest TSE date contains 第一/第二/第三款
  - OTC: 6-day count >= 3 (excluding 第十款)

## Files
- `main.py`: entry point
- `attention/`: core logic (fetch, parse, analysis, output)
- `SPEC.md`: detailed specification
- `PLAN.md`: implementation plan
