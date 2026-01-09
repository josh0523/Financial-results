from __future__ import annotations

import csv
import os
from datetime import date
from typing import Iterable

from tabulate import tabulate

from .analysis import AggregatedRow
from .utils import format_date


COLUMNS = [
    "市場",
    "代號",
    "名稱",
    "風險評級",
    "觸發原因",
    "最後注意日",
    "狀態",
]



def _format_number(value: float | None, missing: str) -> str:
    if value is None:
        return missing
    text = f"{value:.2f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text



def _status_and_risk(row: AggregatedRow) -> tuple[str, str]:
    if row.is_excluded:
        # Low Risk - (已)[...]
        msg = "(已)"
        if row.announced_date and row.announced_month:
            msg += f"[{row.announced_month}月自結於{format_date(row.announced_date)}公布]"
        else:
            msg += " 已公告 (排除)"  # 回退方案（如果資料缺失）
        return msg, "低風險"
    elif row.is_tagged:
        # Uncertain Risk - (?) 不確定 [...]
        msg = "(?) 不確定"
        if row.announced_date and row.announced_month:
            msg += f" [{row.announced_month}月自結於{format_date(row.announced_date)}公布]"
        return msg, "不確定公布"
    else:
        # High Risk - (未) 未公告 (高風險)
        return "(未) 未公告 (高風險)", "高風險"


def _sort_key(row: AggregatedRow) -> tuple[int, date, int, str]:
    # Sort order: High Risk (0) > Uncertain (1) > Low Risk (2)
    if row.is_excluded:
        risk_order = 2  # Low risk - bottom
    elif row.is_tagged:
        risk_order = 1  # Uncertain - middle
    else:
        risk_order = 0  # High risk - top
    
    # Sort by announced_date within groups (oldest first = furthest from today)
    # High risk doesn't have an announced_date, so use date.min
    sort_date = row.announced_date or date.min
    
    market_order = {"TSE": 0, "OTC": 1}
    return (risk_order, sort_date, market_order.get(row.market, 99), row.code)


def build_rows(rows: Iterable[AggregatedRow], missing: str) -> list[list[str]]:
    data: list[list[str]] = []
    for row in sorted(rows, key=_sort_key):
        status, risk = _status_and_risk(row)
        data.append(
            [
                row.market,
                row.code,
                row.name,
                risk,
                row.reason,
                format_date(row.last_date),
                status,
            ]
        )
    return data



def print_table(rows: Iterable[AggregatedRow]) -> None:
    data = build_rows(rows, "-")
    print(tabulate(data, headers=COLUMNS, tablefmt="github"))


def _default_filename(dates: list[date]) -> str:
    start = min(dates)
    end = max(dates)
    filename = f"attention_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.csv"
    return os.path.join("output", filename)


def write_csv(rows: Iterable[AggregatedRow], output_path: str | None, dates: list[date]) -> str:
    if output_path is None:
        output_path = _default_filename(dates)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    data = build_rows(rows, "")
    with open(output_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        writer.writerows(data)
    return output_path
