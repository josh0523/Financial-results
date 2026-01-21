from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

import requests

from .parse import (
    AttentionRow,
    parse_otc_csv,
    parse_otc_html,
    parse_tse_csv,
    parse_tse_html,
)


@dataclass
class FetchResult:
    rows: list[AttentionRow]
    warnings: list[str]


_TSE_URL = "https://www.twse.com.tw/rwd/zh/announcement/notice"
_OTC_URL = "https://www.tpex.org.tw/www/zh-tw/bulletin/attention"


def build_date_range(end_date: date | None = None) -> tuple[date, date]:
    end = end_date or date.today()
    # 增加到 30 天以確保有足夠的交易日
    start = end - timedelta(days=30) 
    return start, end


import urllib3

# Suppress InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _get_text(url: str, params: dict[str, str], encoding: str | None) -> str:
    response = requests.get(url, params=params, timeout=15, verify=False)
    response.raise_for_status()
    if encoding:
        response.encoding = encoding
    return response.text


def _fetch_market(
    name: str,
    csv_fetch: Callable[[], list[AttentionRow]],
    html_fetch: Callable[[], list[AttentionRow]],
) -> tuple[list[AttentionRow], list[str]]:
    warnings: list[str] = []
    try:
        return csv_fetch(), warnings
    except Exception as exc:
        warnings.append(f"{name} CSV fetch failed: {exc}")
    try:
        return html_fetch(), warnings
    except Exception as exc:
        warnings.append(f"{name} HTML fetch failed: {exc}")
    return [], warnings


def fetch_tse(start: date, end: date) -> FetchResult:
    def csv_fetch() -> list[AttentionRow]:
        params = {
            "querytype": "1",
            "stockNo": "",
            "selectType": "",
            "startDate": start.strftime("%Y%m%d"),
            "endDate": end.strftime("%Y%m%d"),
            "sortKind": "STKNO",
            "response": "csv",
        }
        text = _get_text(_TSE_URL, params=params, encoding="cp950")
        return parse_tse_csv(text)

    def html_fetch() -> list[AttentionRow]:
        params = {
            "querytype": "1",
            "stockNo": "",
            "selectType": "",
            "startDate": start.strftime("%Y%m%d"),
            "endDate": end.strftime("%Y%m%d"),
            "sortKind": "STKNO",
            "response": "html",
        }
        text = _get_text(_TSE_URL, params=params, encoding="utf-8")
        return parse_tse_html(text)

    rows, warnings = _fetch_market("TSE", csv_fetch, html_fetch)
    return FetchResult(rows=rows, warnings=warnings)


def fetch_otc(start: date, end: date) -> FetchResult:
    def csv_fetch() -> list[AttentionRow]:
        params = {
            "startDate": start.strftime("%Y/%m/%d"),
            "endDate": end.strftime("%Y/%m/%d"),
            "code": "",
            "cate": "",
            "type": "all",
            "order": "date",
            "id": "",
            "response": "csv",
        }
        text = _get_text(_OTC_URL, params=params, encoding="cp950")
        return parse_otc_csv(text)

    def html_fetch() -> list[AttentionRow]:
        params = {
            "startDate": start.strftime("%Y/%m/%d"),
            "endDate": end.strftime("%Y/%m/%d"),
            "code": "",
            "cate": "",
            "type": "all",
            "order": "date",
            "id": "",
            "response": "html",
        }
        text = _get_text(_OTC_URL, params=params, encoding="utf-8")
        return parse_otc_html(text)

    rows, warnings = _fetch_market("OTC", csv_fetch, html_fetch)
    return FetchResult(rows=rows, warnings=warnings)


def fetch_all(end_date: date | None = None) -> FetchResult:
    start, end = build_date_range(end_date)
    tse_result = fetch_tse(start, end)
    otc_result = fetch_otc(start, end)
    rows = tse_result.rows + otc_result.rows
    warnings = tse_result.warnings + otc_result.warnings
    return FetchResult(rows=rows, warnings=warnings)


@dataclass
class StockWardenRow:
    code: str
    name: str
    price: str
    change_percent: str
    volume: str
    status_text: str
    announcement_date: date | None
    earnings_month: str | None  # YYYYMM


def fetch_stockwarden_weps() -> list[StockWardenRow]:
    url = "https://storage.googleapis.com/stockwarden-prod-public/api/boards.json"
    rows = []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        weps_list = data.get("data", {}).get("weps_list", [])
        
        today = date.today()
        import re

        for item in weps_list:
            # Stock code field: was 'w', now 'v' (fallback to both)
            code = item.get("v", "") or item.get("w", "")
            # Stock name field: was 'bl', now 'bk' (fallback to both)
            name = item.get("bk", "") or item.get("bl", "")
            price = str(item.get("az", {}).get("bn", ""))
            change = str(item.get("az", {}).get("s", ""))
            volume = str(item.get("az", {}).get("ck", ""))
            
            # aw.bv is a list of strings like ["01/13自結 11月EPS..."]
            # API field has changed multiple times: az.ca -> ay.bx -> ay.bz
            # Try multiple known fields and auto-detect if API changes again
            KNOWN_FIELDS = ["bz", "bx", "bv", "ca"]  # Known field names (newest first)
            
            bv_list = []
            used_field = None
            ay_data = item.get("ay", {})
            
            # Try known fields first
            for field in KNOWN_FIELDS:
                candidate = ay_data.get(field, [])
                if isinstance(candidate, list) and any("自結" in str(x) for x in candidate):
                    bv_list = candidate
                    used_field = field
                    break
            
            # If no known field worked, scan all fields in 'ay' for "自結" pattern
            if not bv_list:
                for key, value in ay_data.items():
                    if isinstance(value, list) and any("自結" in str(x) for x in value):
                        bv_list = value
                        used_field = key
                        print(f"⚠️ StockWarden API field changed! Found '自結' data in new field: ay.{key}")
                        print(f"   Please update KNOWN_FIELDS in fetch.py to include '{key}'")
                        break
            
            full_text = " ".join(str(x) for x in bv_list)
            
            # Parse date and month
            # Pattern: "MM/DD自結" ... "M月EPS" or "MM月EPS"
            # Example: "01/13自結 11月EPS ▼46.67%"
            # Regex needs to be flexible
            ann_date = None
            ear_month_str = None
            
            # Find date: MM/DD自結
            date_match = re.search(r"(\d{1,2})/(\d{1,2})自結", full_text)
            if date_match:
                m_str, d_str = date_match.groups()
                try:
                    # Naive year assumption: start with today's year
                    # If the date is in the future (e.g. today is Dec, parsed is Jan), it might be next year? 
                    #Unlikely for "Self-disclosed". 
                    # More likely: today is Jan 2026, parsed is "12/30" -> 2025.
                    
                    m, d = int(m_str), int(d_str)
                    yr = today.year
                    # Simple heuristic: if parsed month is 12 and current month is 1, it's last year
                    if m == 12 and today.month == 1:
                        yr -= 1
                    
                    ann_date = date(yr, m, d)
                except ValueError:
                    pass

            # Find month: "X月EPS" or "XX月EPS"
            # Usually follows the date, but regex search whole string is safer
            month_match = re.search(r"(\d{1,2})月EPS", full_text)
            if month_match:
                em_str = month_match.group(1)
                try:
                    em = int(em_str)
                    # Infer year for earnings month
                    # Usually earnings month is 1-2 months behind announcement date
                    # if announcement is Jan 2026, earnings month 11 is Nov 2025.
                    # if announcement is Dec 2025, earnings month 10 is Oct 2025.
                    
                    if ann_date:
                        base_year = ann_date.year
                        # if ann_month is 1, and earn_month is 11 or 12 -> prev year
                        if ann_date.month == 1 and em > 10:
                            ey = base_year - 1
                        else:
                            ey = base_year
                        ear_month_str = f"{ey}{em:02d}"
                    else:
                        # Fallback to today logic if no date found (unlikely but possible)
                        base_year = today.year
                        if today.month == 1 and em > 10:
                            ey = base_year - 1
                        else:
                            ey = base_year
                        ear_month_str = f"{ey}{em:02d}"

                except ValueError:
                    pass

            rows.append(StockWardenRow(
                code=code,
                name=name,
                price=price,
                change_percent=change,
                volume=volume,
                status_text=full_text,
                announcement_date=ann_date,
                earnings_month=ear_month_str
            ))

    except Exception as e:
        print(f"Error fetching StockWarden: {e}")
        return []

    return rows
