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


def _find_all_strings(obj: object, path: str = "") -> list[tuple[str, str]]:
    """遞迴掃描 JSON 物件，找出所有字串值及其路徑"""
    results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = f"{path}.{k}" if path else k
            results.extend(_find_all_strings(v, new_path))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            results.extend(_find_all_strings(v, f"{path}[{i}]"))
    elif isinstance(obj, str):
        results.append((path, obj))
    return results


def _dynamic_parse_item(item: dict, today: date) -> StockWardenRow | None:
    """
    動態解析 StockWarden API 項目，不依賴硬編碼欄位名稱。
    使用特徵匹配來識別：
    - 股票代碼：4 位數字
    - 股票名稱：短中文字串
    - 自結資料：包含「MM/DD自結」模式的字串
    """
    import re

    all_strings = _find_all_strings(item)

    # 1. 找股票代碼 (4位數字，且在頂層欄位)
    code = ""
    code_pattern = re.compile(r"^\d{4}$")
    for path, value in all_strings:
        # 優先選擇頂層欄位 (不含 '.')
        if "." not in path and code_pattern.match(value):
            code = value
            break
    # 如果頂層沒找到，再找任意位置
    if not code:
        for path, value in all_strings:
            if code_pattern.match(value):
                code = value
                break

    if not code:
        return None  # 沒有股票代碼，跳過

    # 2. 找股票名稱
    # 策略：優先找中文名稱，若無則找頂層短字串（排除代碼和特殊標記）
    name = ""
    name_pattern = re.compile(r"[\u4e00-\u9fff]")

    # 2a. 優先找含中文的短字串
    for path, value in all_strings:
        if (name_pattern.search(value) and
            2 <= len(value) <= 10 and
            "自結" not in value and
            "EPS" not in value):
            name = value
            break

    # 2b. 若無中文名稱，找頂層短字串（可能是英文名稱如 IET-KY）
    if not name:
        code_pattern = re.compile(r"^\d+$")  # 純數字
        skip_values = {"A", "B", "C", "D", "E", "F"}  # 常見分類標記
        for path, value in all_strings:
            # 頂層欄位、2-15 字元、非純數字、非分類標記
            if ("." not in path and
                2 <= len(value) <= 15 and
                not code_pattern.match(value) and
                value not in skip_values and
                value != code):
                name = value
                break

    # 3. 找自結資料 (包含「自結」的字串)
    earnings_texts = []
    for path, value in all_strings:
        if "自結" in value:
            earnings_texts.append(value)

    full_text = " ".join(earnings_texts)

    if not full_text:
        return None  # 沒有自結資料，跳過

    # 4. 解析日期和月份
    ann_date = None
    ear_month_str = None

    # 找日期: MM/DD自結
    date_match = re.search(r"(\d{1,2})/(\d{1,2})自結", full_text)
    if date_match:
        m_str, d_str = date_match.groups()
        try:
            m, d = int(m_str), int(d_str)
            yr = today.year
            # 如果解析的月份是 12 且現在是 1 月，則為去年
            if m == 12 and today.month == 1:
                yr -= 1
            ann_date = date(yr, m, d)
        except ValueError:
            pass

    # 找月份: X月EPS 或 XX月EPS
    month_match = re.search(r"(\d{1,2})月EPS", full_text)
    if month_match:
        em_str = month_match.group(1)
        try:
            em = int(em_str)
            if ann_date:
                base_year = ann_date.year
                # 如果公告月份是 1 月，而營收月份是 11 或 12，則為前一年
                if ann_date.month == 1 and em > 10:
                    ey = base_year - 1
                else:
                    ey = base_year
                ear_month_str = f"{ey}{em:02d}"
            else:
                base_year = today.year
                if today.month == 1 and em > 10:
                    ey = base_year - 1
                else:
                    ey = base_year
                ear_month_str = f"{ey}{em:02d}"
        except ValueError:
            pass

    return StockWardenRow(
        code=code,
        name=name,
        price="",  # 動態解析不保證能找到價格
        change_percent="",
        volume="",
        status_text=full_text,
        announcement_date=ann_date,
        earnings_month=ear_month_str
    )


def fetch_stockwarden_weps() -> list[StockWardenRow]:
    """
    從 StockWarden API 抓取自結資料。
    使用動態解析，不依賴硬編碼欄位名稱，可適應 API 結構變化。
    """
    url = "https://storage.googleapis.com/stockwarden-prod-public/api/boards.json"
    rows = []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        weps_list = data.get("data", {}).get("weps_list", [])

        today = date.today()

        for item in weps_list:
            row = _dynamic_parse_item(item, today)
            if row:
                rows.append(row)

    except Exception as e:
        print(f"Error fetching StockWarden: {e}")
        return []

    return rows
