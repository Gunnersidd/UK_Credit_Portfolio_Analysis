#!/usr/bin/env python3
"""Check workbook structure and reconcile Excel formulas to SQL result CSVs."""

from __future__ import annotations

import argparse
import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN_NS, "r": REL_NS, "p": PKG_REL_NS}
EXPECTED_SHEETS = ["Metric Notes", "Start Here", "Monthly Portfolio", "Risk Segment", "Vintage MOB", "Delinquency State", "Roll Rates", "Account Month Data"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def cell_map(sheet_root: ET.Element) -> tuple[list[str], list[dict[str, tuple[str | None, str | None, str | None]]]]:
    rows = []
    for row in sheet_root.findall(".//m:sheetData/m:row", NS):
        cells = {}
        for cell in row.findall("m:c", NS):
            ref = cell.attrib["r"]
            formula_node = cell.find("m:f", NS)
            value_node = cell.find("m:v", NS)
            text_node = cell.find("m:is/m:t", NS)
            value = value_node.text if value_node is not None else (text_node.text if text_node is not None else None)
            cells[ref] = (value, formula_node.text if formula_node is not None else None, cell.attrib.get("t"))
        rows.append(cells)
    headers = []
    if rows:
        for i in range(1, len(rows[0]) + 1):
            ref = f"{column_name(i)}1"
            headers.append(rows[0].get(ref, (None, None, None))[0] or "")
    return headers, rows


def column_name(number: int) -> str:
    out = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        out = chr(65 + remainder) + out
    return out


def as_decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value not in (None, "") else None


def check_formula(sheet_rows, row_index: int, column: str, expected: Decimal | None, failures: list[str], label: str) -> None:
    ref = f"{column}{row_index}"
    value, formula, cell_type = sheet_rows[row_index - 1].get(ref, (None, None, None))
    if not formula:
        failures.append(f"{label}: missing formula in {ref}")
        return
    actual = as_decimal(value)
    if expected is None:
        if actual is not None:
            failures.append(f"{label}: expected blank cached value in {ref}, found {actual}")
    elif actual is None or abs(actual - expected) > Decimal("0.0000000001"):
        failures.append(f"{label}: cached formula value mismatch in {ref}; got {actual}, expected {expected}")


def expected_ratio(numerator: str, denominator: str) -> Decimal | None:
    den = Decimal(denominator)
    return Decimal(numerator) / den if den else None


def validate(workbook: Path, sql_dir: Path, source: Path) -> dict[str, object]:
    failures: list[str] = []
    with zipfile.ZipFile(workbook) as archive:
        corrupt = archive.testzip()
        if corrupt:
            failures.append(f"Corrupt ZIP member: {corrupt}")
        names = set(archive.namelist())
        workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = workbook_root.findall("m:sheets/m:sheet", NS)
        sheet_names = [sheet.attrib["name"] for sheet in sheets]
        if sheet_names != EXPECTED_SHEETS:
            failures.append(f"Sheet names/order mismatch: {sheet_names}")
        rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels_root.findall("p:Relationship", NS)}
        paths = {}
        for sheet in sheets:
            target = rel_targets.get(sheet.attrib[f"{{{REL_NS}}}id"])
            if not target:
                failures.append(f"Missing relationship for {sheet.attrib['name']}")
                continue
            paths[sheet.attrib["name"]] = "xl/" + target
        for path in names:
            if path.endswith(".xml") or path.endswith(".rels"):
                try:
                    ET.fromstring(archive.read(path))
                except ET.ParseError as exc:
                    failures.append(f"Invalid XML in {path}: {exc}")

        parsed = {}
        for sheet_name in EXPECTED_SHEETS[:-1]:
            root = ET.fromstring(archive.read(paths[sheet_name]))
            parsed[sheet_name] = cell_map(root)
        data_path = paths.get("Account Month Data")
        data_rows = 0
        if data_path:
            with archive.open(data_path) as stream:
                for _, element in ET.iterparse(stream, events=("end",)):
                    if element.tag == f"{{{MAIN_NS}}}row":
                        data_rows += 1
                        element.clear()

        with source.open(encoding="utf-8") as handle:
            source_rows = sum(1 for _ in handle) - 1
        if data_rows != source_rows + 1:
            failures.append(f"Account Month Data has {data_rows - 1} rows; source CSV has {source_rows}")

        formula_specs = {
            "Monthly Portfolio": ("monthly_portfolio.csv", [("G", "active_balance_pence", "active_limit_pence", "portfolio_utilisation"), ("J", "simulated_30plus_accounts", "active_accounts", "simulated_30plus_account_rate"), ("K", "simulated_30plus_balance_pence", "active_balance_pence", "simulated_30plus_balance_rate"), ("O", "active_payment_received_pence", "active_payment_due_pence", "payment_rate")]),
            "Risk Segment": ("risk_segment.csv", [("F", "active_balance_pence", "active_limit_pence", "portfolio_utilisation"), ("H", "simulated_30plus_accounts", "active_accounts", "simulated_30plus_account_rate"), ("J", "simulated_30plus_balance_pence", "active_balance_pence", "simulated_30plus_balance_rate"), ("M", "active_payment_received_pence", "active_payment_due_pence", "payment_rate")]),
            "Vintage MOB": ("vintage_mob.csv", [("H", "active_balance_pence", "active_limit_pence", "portfolio_utilisation"), ("J", "simulated_30plus_accounts", "active_accounts", "simulated_30plus_account_rate"), ("L", "simulated_30plus_balance_pence", "active_balance_pence", "simulated_30plus_balance_rate"), ("O", "active_payment_received_pence", "active_payment_due_pence", "payment_rate")]),
            "Delinquency State": ("delinquency_state.csv", [("G", "active_accounts", "monthly_active_accounts", "account_share"), ("H", "active_balance_pence", "monthly_active_balance_pence", "balance_share")]),
            "Roll Rates": ("roll_rates.csv", [("F", "transitioned_accounts", "opening_accounts_with_outcome", "roll_rate")]),
        }
        row_count_checks = {}
        for sheet_name, (csv_name, ratios) in formula_specs.items():
            source_rows_sql = read_csv(sql_dir / csv_name)
            headers, sheet_rows = parsed[sheet_name]
            row_count_checks[sheet_name] = len(sheet_rows) - 1
            if len(sheet_rows) - 1 != len(source_rows_sql):
                failures.append(f"{sheet_name} row count differs from {csv_name}: {len(sheet_rows)-1} vs {len(source_rows_sql)}")
            for data_index, record in enumerate(source_rows_sql, start=2):
                for col, numerator, denominator, sql_rate in ratios:
                    expected = expected_ratio(record[numerator], record[denominator])
                    sql_value = as_decimal(record[sql_rate])
                    if (expected is None) != (sql_value is None) or (expected is not None and sql_value is not None and abs(expected - sql_value) > Decimal("0.0000000001")):
                        failures.append(f"{sheet_name}: SQL rate {sql_rate} does not reconcile to its numerator/denominator on row {data_index}")
                    check_formula(sheet_rows, data_index, col, expected, failures, sheet_name)
        for sheet_name in EXPECTED_SHEETS[:-1]:
            if not parsed.get(sheet_name, ([], []))[1]:
                failures.append(f"Sheet has no rows: {sheet_name}")
        return {"failures": failures, "source_rows": source_rows, "workbook_data_rows": data_rows - 1, "summary_rows": row_count_checks, "sheet_names": sheet_names}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=ROOT / "reports/credit_portfolio_review.xlsx")
    parser.add_argument("--sql-dir", type=Path, default=ROOT / "reports/t03/sql")
    parser.add_argument("--source", type=Path, default=ROOT / "data/synthetic_portfolio.csv")
    args = parser.parse_args()
    result = validate(args.workbook, args.sql_dir, args.source)
    print(f"Workbook sheets: {len(result['sheet_names'])}; source rows: {result['source_rows']:,}; workbook data rows: {result['workbook_data_rows']:,}")
    print(f"Summary rows: {result['summary_rows']}")
    if result["failures"]:
        print("FAILURES:")
        for failure in result["failures"]:
            print(f"- {failure}")
        raise SystemExit(1)
    print("PASS: workbook XML, row counts, formulas, and cached ratios reconcile to SQL exports")


if __name__ == "__main__":
    main()
