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
        # Start default message
        msg_prefix = "(?) 不確定"
        risk_label = "不確定公布"

        # Check for TSE clause 9-13 first (special case)
        if row.uncertain_type == "tse-clause-9-13":
            msg_prefix = "(?) 不一定公布"
            risk_label = "不一定公布"
            return msg_prefix + " (TSE第九-第十三項)", risk_label
        
        if row.announced_date:
            days_diff = (date.today() - row.announced_date).days
            if days_diff > 30:
                msg_prefix = "(!) 可能公布"
                risk_label = "可能公布"
        
        msg = msg_prefix
        if row.announced_date and row.announced_month:
            msg += f" [{row.announced_month}月自結於{format_date(row.announced_date)}公布]"
        return msg, risk_label
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


def build_rows(rows: Iterable[AggregatedRow], missing: str, for_excel: bool = False) -> list[list[str]]:
    data: list[list[str]] = []
    for row in sorted(rows, key=_sort_key):
        status, risk = _status_and_risk(row)
        
        code_val = row.code
        if for_excel:
            code_val = f'="{row.code}"'

        data.append(
            [
                row.market,
                code_val,
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
    data = build_rows(rows, "", for_excel=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        writer.writerows(data)
    return output_path


def print_stockwarden_table(rows: Iterable['attention.fetch.StockWardenRow']) -> None:
    headers = ["代號", "名稱", "價格", "漲跌幅", "成交量", "狀態(自結/注意)", "公告日(推測)", "月份"]
    data = []
    for r in rows:
        ann_date = r.announcement_date.strftime("%Y-%m-%d") if r.announcement_date else "-"
        e_month = r.earnings_month if r.earnings_month else "-"
        
        # Truncate status text if too long
        status = r.status_text
        if len(status) > 40:
            status = status[:37] + "..."
            
        data.append([
            r.code,
            r.name,
            r.price,
            r.change_percent,
            r.volume,
            status,
            ann_date,
            e_month
        ])
    
    print(tabulate(data, headers=headers, tablefmt="github"))
