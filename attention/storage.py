
import csv
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

# Use absolute path relative to this module's location
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_MODULE_DIR)  # Go up one level from 'attention' to project root
DATA_DIR = os.path.join(_PROJECT_DIR, "data")
EARNINGS_FILE = os.path.join(DATA_DIR, "earnings_records.csv")

@dataclass
class EarningsRecord:
    code: str
    earnings_month: str  # YYYYMM
    announcement_date: date

def _ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def load_records() -> List[EarningsRecord]:
    if not os.path.exists(EARNINGS_FILE):
        return []
    
    records = []
    with open(EARNINGS_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                dt = datetime.strptime(row["announcement_date"], "%Y%m%d").date()
                records.append(EarningsRecord(
                    code=row["code"],
                    earnings_month=row["earnings_month"],
                    announcement_date=dt
                ))
            except (ValueError, KeyError):
                continue
    return records

def save_record(record: EarningsRecord):
    _ensure_data_dir()
    file_exists = os.path.exists(EARNINGS_FILE)
    
    # Check if file exists and doesn't end with a newline
    needs_newline = False
    if file_exists:
        with open(EARNINGS_FILE, "rb") as f:
            f.seek(0, 2)  # Go to end
            if f.tell() > 0:
                f.seek(-1, 2)  # Go to last byte
                if f.read(1) != b'\n':
                    needs_newline = True
    
    with open(EARNINGS_FILE, mode="a", encoding="utf-8-sig", newline="") as f:
        if needs_newline:
            f.write('\n')
        
        writer = csv.DictWriter(f, fieldnames=["code", "earnings_month", "announcement_date"])
        if not file_exists:
            writer.writeheader()
        
        writer.writerow({
            "code": record.code,
            "earnings_month": record.earnings_month,
            "announcement_date": record.announcement_date.strftime("%Y%m%d")
        })

def get_record(code: str, earnings_month: str) -> Optional[EarningsRecord]:
    # Deprecated or used for simple lookup. Returns the first match.
    records = load_records()
    for r in records:
        if r.code == code and r.earnings_month == earnings_month:
            return r
    return None

def record_exists(code: str, earnings_month: str, announcement_date: date) -> bool:
    records = load_records()
    for r in records:
        if r.code == code and r.earnings_month == earnings_month and r.announcement_date == announcement_date:
            return True
    return False
