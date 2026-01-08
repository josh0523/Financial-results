import csv
import io
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from .utils import clean_cell, clean_text, normalize_header, parse_roc_date


@dataclass
class AttentionRow:
    market: str
    code: str
    name: str
    date: Any
    info: str


class _HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[dict[str, Any]]]] = []
        self._table_depth = 0
        self._current_table: list[list[dict[str, Any]]] | None = None
        self._current_row: list[dict[str, Any]] | None = None
        self._current_cell: dict[str, Any] | None = None
        self._cell_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._current_table = []
        if self._table_depth != 1:
            return
        if tag == "tr":
            self._current_row = []
            return
        if tag in ("td", "th"):
            attrs_map = {k: v for k, v in attrs}
            self._current_cell = {
                "text": "",
                "rowspan": int(attrs_map.get("rowspan") or 1),
                "colspan": int(attrs_map.get("colspan") or 1),
                "is_header": tag == "th",
            }
            self._cell_text = []
            return
        if tag == "br" and self._current_cell is not None:
            self._cell_text.append("\n")

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._table_depth != 1:
            if tag == "table":
                self._table_depth = max(0, self._table_depth - 1)
            return
        if tag in ("td", "th") and self._current_cell is not None:
            text = "".join(self._cell_text)
            self._current_cell["text"] = clean_text(text)
            if self._current_row is not None:
                self._current_row.append(self._current_cell)
            self._current_cell = None
            self._cell_text = []
            return
        if tag == "tr":
            if self._current_row is not None and self._current_table is not None:
                self._current_table.append(self._current_row)
            self._current_row = None
            return
        if tag == "table":
            if self._current_table:
                self.tables.append(self._current_table)
            self._current_table = None
            self._table_depth = max(0, self._table_depth - 1)


def _expand_table(rows: list[list[dict[str, Any]]]) -> list[list[str]]:
    expanded: list[list[str]] = []
    rowspans: list[dict[str, Any] | None] = []
    for row in rows:
        out: list[str] = []
        col_idx = 0

        def fill_rowspans() -> None:
            nonlocal col_idx
            while col_idx < len(rowspans) and rowspans[col_idx] is not None:
                span = rowspans[col_idx]
                out.append(span["text"])
                span["rowspan"] -= 1
                if span["rowspan"] <= 0:
                    rowspans[col_idx] = None
                col_idx += 1

        for cell in row:
            fill_rowspans()
            text = clean_text(cell.get("text", ""))
            colspan = int(cell.get("colspan", 1) or 1)
            rowspan = int(cell.get("rowspan", 1) or 1)
            for span_index in range(colspan):
                out.append(text if span_index == 0 else "")
                if rowspan > 1:
                    if col_idx >= len(rowspans):
                        rowspans.extend([None] * (col_idx - len(rowspans) + 1))
                    rowspans[col_idx] = {"text": text, "rowspan": rowspan - 1}
                col_idx += 1
        fill_rowspans()
        expanded.append(out)
    return expanded


def _find_header_row(rows: list[list[str]]) -> int | None:
    required = {"證券代號", "證券名稱", "注意交易資訊"}
    for idx, row in enumerate(rows):
        normalized = {normalize_header(cell) for cell in row}
        if required.issubset(normalized):
            return idx
    return None


def _parse_table_rows(rows: list[list[str]], market: str) -> list[AttentionRow]:
    header_idx = _find_header_row(rows)
    if header_idx is None:
        raise ValueError("Unable to locate header row")
    headers = [normalize_header(h) for h in rows[header_idx]]

    def index_of(name: str) -> int | None:
        try:
            return headers.index(name)
        except ValueError:
            return None

    code_idx = index_of("證券代號")
    name_idx = index_of("證券名稱")
    info_idx = index_of("注意交易資訊")
    date_idx = index_of("日期") or index_of("公告日期")
    if None in (code_idx, name_idx, info_idx, date_idx):
        raise ValueError("Missing required columns")

    parsed: list[AttentionRow] = []
    for row in rows[header_idx + 1 :]:
        if len(row) <= max(code_idx, name_idx, info_idx, date_idx):
            continue
        code = clean_cell(row[code_idx])
        if not code:
            continue
        name = clean_cell(row[name_idx])
        info = clean_text(row[info_idx])
        date_value = clean_cell(row[date_idx])
        try:
            parsed_date = parse_roc_date(date_value)
        except ValueError:
            continue
        parsed.append(AttentionRow(market=market, code=code, name=name, date=parsed_date, info=info))
    return parsed


def parse_html(html_text: str, market: str) -> list[AttentionRow]:
    parser = _HTMLTableParser()
    parser.feed(html_text)
    for table in parser.tables:
        expanded = _expand_table(table)
        try:
            return _parse_table_rows(expanded, market)
        except ValueError:
            continue
    raise ValueError("No suitable HTML table found")


def _parse_csv(text: str, market: str) -> list[AttentionRow]:
    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    header_idx = None
    for idx, row in enumerate(rows):
        normalized = {normalize_header(cell) for cell in row}
        if {"證券代號", "證券名稱", "注意交易資訊"}.issubset(normalized):
            header_idx = idx
            break
    if header_idx is None:
        raise ValueError("Unable to locate CSV header row")
    headers = [normalize_header(cell) for cell in rows[header_idx]]

    def index_of(name: str) -> int | None:
        try:
            return headers.index(name)
        except ValueError:
            return None

    code_idx = index_of("證券代號")
    name_idx = index_of("證券名稱")
    info_idx = index_of("注意交易資訊")
    date_idx = index_of("日期") or index_of("公告日期")
    if None in (code_idx, name_idx, info_idx, date_idx):
        raise ValueError("Missing required CSV columns")

    parsed: list[AttentionRow] = []
    for row in rows[header_idx + 1 :]:
        if len(row) <= max(code_idx, name_idx, info_idx, date_idx):
            continue
        code = clean_cell(row[code_idx])
        if not code:
            continue
        name = clean_cell(row[name_idx])
        info = clean_text(row[info_idx])
        date_value = clean_cell(row[date_idx])
        try:
            parsed_date = parse_roc_date(date_value)
        except ValueError:
            continue
        parsed.append(AttentionRow(market=market, code=code, name=name, date=parsed_date, info=info))
    return parsed


def parse_tse_csv(text: str) -> list[AttentionRow]:
    return _parse_csv(text, "TSE")


def parse_otc_csv(text: str) -> list[AttentionRow]:
    return _parse_csv(text, "OTC")


def parse_tse_html(html_text: str) -> list[AttentionRow]:
    return parse_html(html_text, "TSE")


def parse_otc_html(html_text: str) -> list[AttentionRow]:
    return parse_html(html_text, "OTC")
