
import csv
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

DATA_DIR = "data"
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
    
    with open(EARNINGS_FILE, mode="a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "earnings_month", "announcement_date"])
        if not file_exists:
            writer.writeheader()
        
        writer.writerow({
            "code": record.code,
            "earnings_month": record.earnings_month,
            "announcement_date": record.announcement_date.strftime("%Y%m%d")
        })

def get_record(code: str, earnings_month: str) -> Optional[EarningsRecord]:
    records = load_records()
    for r in records:
        if r.code == code and r.earnings_month == earnings_month:
            return r
    return None
