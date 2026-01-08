import argparse
import sys
from datetime import datetime

from . import analysis, fetch, output
from .utils import split_codes


PROMPT = "請輸入今日已公布自結的股票代號（用空白分隔）："


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Attention stock monitor")
    parser.add_argument("--days", type=int, default=6, help="Number of trading days to analyze (default: 6)")
    parser.add_argument("--output", type=str, default=None, help="CSV output path")
    parser.add_argument("--date", type=str, default=None, help="End date for analysis (YYYY-MM-DD), default: today")

    parser.add_argument("--add", nargs=3, metavar=("CODE", "MONTH", "DATE"), help="Add earnings record: CODE MONTH(YYYYMM) DATE(YYYY-MM-DD)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.add:
        code, month, date_str = args.add
        try:
            ann_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if len(month) != 6 or not month.isdigit():
                raise ValueError("Month must be YYYYMM")
            
            from . import storage
            record = storage.EarningsRecord(code=code, earnings_month=month, announcement_date=ann_date)
            storage.save_record(record)
            print(f"Added record: {code} {month} {ann_date}")
            return 0
        except ValueError as e:
            print(f"Error adding record: {e}", file=sys.stderr)
            return 1

    if args.days <= 0:
        print("--days must be a positive integer", file=sys.stderr)
        return 2

    # raw = input(PROMPT)
    # announced = set(split_codes(raw))
    # No longer asking for manual input of today's announced, relying on storage (or we can keep it as optional fallback?)
    # For now, let's keep the prompt but optional? Or remove it as per user "record system" request?
    # User said "Add organizing feature", implying we should likely use the stored data.
    # But usually today's announcement won't be in storage yet unless they added it.
    # Let's keep the prompt for "TODAY's" announcements that aren't in DB yet? 
    # Actually user said "Program can read these files to exclude..."
    # I will modify the prompt to be optional or just rely on DB + Argument to add.
    
    # For backward compatibility and immediate usage, I'll keep the input but make it clear it's for temporary.
    # actually, let's load from storage.
    
    from . import storage
    records = storage.load_records()
    
    print(f"Loaded {len(records)} earnings records.")

    # Handle end date
    end_date = None
    if args.date:
        try:
            end_date = datetime.strptime(args.date, "%Y-%m-%d").date()
            print(f"Analyzing up to specified date: {end_date}")
        except ValueError:
            print(f"Invalid date format: {args.date}. Use YYYY-MM-DD.", file=sys.stderr)
            return 1

    result = fetch.fetch_all(end_date)
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    if not result.rows:
        print("No data fetched from either market.", file=sys.stderr)
        return 1

    filtered_rows, latest_dates = analysis.filter_by_latest_dates(result.rows, args.days)
    if not filtered_rows:
        print("No rows found within the requested date window.", file=sys.stderr)
        return 1

    report_rows = analysis.build_report(filtered_rows, records, end_date)
    
    # Filter to only show stocks where the last attention date is the latest available date
    if report_rows:
        max_date = max(row.last_date for row in report_rows)
        report_rows = [row for row in report_rows if row.last_date == max_date]
        print(f"Showing report for latest date: {max_date}")

    output.print_table(report_rows)
    csv_path = output.write_csv(report_rows, args.output, latest_dates)
    print(f"CSV saved to {csv_path}")
    return 0
