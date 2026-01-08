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
