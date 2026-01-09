from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from .storage import EarningsRecord

from .parse import AttentionRow
from .utils import is_warrant


_VOLUME_MULT_RE = re.compile(r"(?:放大|為|之)\s*([0-9]+(?:\.[0-9]+)?)\s*倍")
_PCT_CHANGE_RE = re.compile(r"漲幅(?:達)?\s*([0-9]+(?:\.[0-9]+)?)%")
_CLAUSE_1_3_5_RE = re.compile(r"第(?:一|二|三|五|1|2|3|5)款")
_CLAUSE_10_RE = re.compile(r"第(?:十|10)款")
_TSE_FIRST_RE = re.compile(r"(第一款|第1款|累積收盤價漲幅)")


@dataclass
class AggregatedRow:
    market: str
    code: str
    name: str
    last_date: date
    reason: str
    volume_multiplier: float | None
    pct_change: float | None
    tse_clause1: int
    is_excluded: bool
    is_tagged: bool
    uncertain_type: str | None = None  # "month-3" or "month-2"
    announced_date: date | None = None
    announced_month: str | None = None


def _extract_max(pattern: re.Pattern[str], text: str) -> float | None:
    matches = pattern.findall(text or "")
    if not matches:
        return None
    values = [float(value) for value in matches]
    return max(values) if values else None


def _has_clause_1_3_5(text: str) -> bool:
    return bool(_CLAUSE_1_3_5_RE.search(text or ""))


def _has_clause_10(text: str) -> bool:
    return bool(_CLAUSE_10_RE.search(text or ""))


def _tse_first_clause(text: str) -> int:
    return 1 if _TSE_FIRST_RE.search(text or "") else 0


def get_latest_dates(rows: Iterable[AttentionRow], count: int) -> list[date]:
    dates = sorted({row.date for row in rows})
    if not dates:
        return []
    if count <= 0:
        return []
    return dates[-count:]


def filter_by_latest_dates(rows: list[AttentionRow], count: int) -> tuple[list[AttentionRow], list[date]]:
    latest_dates = get_latest_dates(rows, count)
    if not latest_dates:
        return [], []
    date_set = set(latest_dates)
    filtered = [row for row in rows if row.date in date_set]
    return filtered, latest_dates


def build_report(rows: list[AttentionRow], records: list['EarningsRecord'], ref_date: date | None = None) -> list[AggregatedRow]:
    if not rows:
        return []

    six_dates = get_latest_dates(rows, 6)
    six_set = set(six_dates)
    tse_dates = [row.date for row in rows if row.market == "TSE"]
    tse_latest_date = max(tse_dates) if tse_dates else None

    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        key = (row.market, row.code)
        grouped.setdefault(key, []).append(
            {
                "row": row,
                "volume_multiplier": _extract_max(_VOLUME_MULT_RE, row.info),
                "pct_change": _extract_max(_PCT_CHANGE_RE, row.info),
                "tse_clause1": _tse_first_clause(row.info),
                "has_clause_10": _has_clause_10(row.info),
                "has_clause_1_3_5": _has_clause_1_3_5(row.info),
            }
        )


    results: list[AggregatedRow] = []
    
    # Logic for earnings records
    if ref_date is None:
        ref_date = date.today()
    
    this_month = ref_date.strftime("%Y%m")  # Reference month, e.g., "202601"
    
    # Calculate last month
    first_of_this_month = ref_date.replace(day=1)
    last_month_date = first_of_this_month - timedelta(days=1)
    last_month = last_month_date.strftime("%Y%m")  # e.g., "202512"
    
    # Calculate month before last (month-2)
    first_of_last_month = last_month_date.replace(day=1)
    month_before_last_date = first_of_last_month - timedelta(days=1)
    month_before_last = month_before_last_date.strftime("%Y%m")  # e.g., "202511"
    
    # Calculate month-3
    first_of_month_before_last = month_before_last_date.replace(day=1)
    month_3_date = first_of_month_before_last - timedelta(days=1)
    month_3 = month_3_date.strftime("%Y%m")  # e.g., "202510"

    # Pre-index records by code for O(1) lookup
    records_by_code: dict[str, list[EarningsRecord]] = {}
    for record in records:
        records_by_code.setdefault(record.code, []).append(record)

    for (market, code), items in grouped.items():
        # Skip warrants (权证) - they don't have self-disclosed earnings announcements
        if is_warrant(code):
            continue
            
        last_item = max(items, key=lambda item: item["row"].date)
        last_date = last_item["row"].date
        name = last_item["row"].name

        count = 0
        for item in items:
            row = item["row"]
            if row.date not in six_set:
                continue

            should_count = False
            if market == "TSE":
                # For TSE, exclude if it is Clause 10
                if not item["has_clause_10"]:
                    should_count = True
            else:
                # For OTC (and others), count everything in the 6-day window
                should_count = True

            if should_count:
                count += 1

        has_tse_clause = False
        if market == "TSE" and tse_latest_date is not None:
            for item in items:
                if item["row"].date == tse_latest_date and item["has_clause_1_3_5"]:
                    has_tse_clause = True
                    break

        reasons: list[str] = []
        if count >= 3:
            reasons.append("近六日三次注意")
        if market == "TSE" and has_tse_clause:
            reasons.append("昨日第一到第三、五款")
        
        # Check earnings records
        # Rule 1: Low Risk (Excluded) - Announced ANY earnings THIS month
        is_excluded = False
        ann_date = None
        ann_month = None
        
        code_records = records_by_code.get(code, [])
        for record in code_records:
            # IMPORTANT: Skip announcements that happened AFTER the reference date
            if record.announcement_date > ref_date:
                continue
                
            # Quick check for this month without strftime
            if record.announcement_date.year == ref_date.year and record.announcement_date.month == ref_date.month:
                # Announced this month (any earnings month) = Low Risk
                is_excluded = True
                ann_date = record.announcement_date
                ann_month = record.earnings_month
                break  # Found announcement this month
        
        # Rule 2: Uncertain Risk - Announced in LAST month
        # Type 1: Announced month-3 earnings in last month (usually first week)
        # Type 2: Announced month-2 earnings in last month (usually after first week)
        is_tagging = False
        uncertain_type = None
        
        if not is_excluded:  # Only check if not already low risk
            for record in code_records:
                # IMPORTANT: Skip announcements that happened AFTER the reference date
                if record.announcement_date > ref_date:
                    continue
                    
                # Check if announced in last month
                if record.announcement_date.year == last_month_date.year and record.announcement_date.month == last_month_date.month:
                    # Check if it was month-3 earnings
                    if record.earnings_month == month_3:
                        is_tagging = True
                        uncertain_type = "month-3"
                        ann_date = record.announcement_date
                        ann_month = record.earnings_month
                        reasons.append("上月公布上上上月自結")
                        break
                    # Check if it was month-2 earnings
                    elif record.earnings_month == month_before_last:
                        is_tagging = True
                        uncertain_type = "month-2"
                        ann_date = record.announcement_date
                        ann_month = record.earnings_month
                        reasons.append("上月公布上上月自結")
                        break

        if not reasons and not is_tagging: 
            continue
            
        # If we have reasons, we proceed.

        volume_values = [item["volume_multiplier"] for item in items if item["volume_multiplier"] is not None]
        pct_values = [item["pct_change"] for item in items if item["pct_change"] is not None]
        volume_multiplier = max(volume_values) if volume_values else None
        pct_change = max(pct_values) if pct_values else None
        tse_clause1 = 1 if any(item["tse_clause1"] for item in items) else 0

        results.append(
            AggregatedRow(
                market=market,
                code=code,
                name=name,
                last_date=last_date,
                reason="；".join(reasons),
                volume_multiplier=volume_multiplier,
                pct_change=pct_change,
                tse_clause1=tse_clause1,
                is_excluded=is_excluded,
                is_tagged=is_tagging,
                uncertain_type=uncertain_type,
                announced_date=ann_date,
                announced_month=ann_month
            )
        )

    return results
