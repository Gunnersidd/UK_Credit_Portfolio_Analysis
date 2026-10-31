#!/usr/bin/env python3
"""Build a transparent .xlsx review workbook using only Python's stdlib."""

from __future__ import annotations

import argparse
import csv
import zipfile
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
MONEY_FIELDS = {
    "credit_limit_gbp", "opening_balance_gbp", "purchase_amount_gbp",
    "interest_fee_amount_gbp", "payment_due_gbp", "payment_received_gbp",
    "other_adjustment_gbp", "closing_balance_gbp",
}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def gbp(pence: str | int) -> float:
    return float(Decimal(str(pence)) / Decimal(100))


def ratio(numerator: Decimal | int, denominator: Decimal | int) -> float | None:
    return float(Decimal(numerator) / Decimal(denominator)) if Decimal(denominator) else None


def formula(expression: str, cached: float | None, style: int) -> tuple[str, str, float | None, int]:
    return ("formula", expression, cached, style)


def col_name(number: int) -> str:
    value = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        value = chr(65 + remainder) + value
    return value


def xml_cell(ref: str, value: object, default_style: int = 0) -> str:
    if isinstance(value, tuple) and value and value[0] == "formula":
        _, expression, cached, style = value
        style_attr = f' s="{style}"' if style else ""
        if cached is None:
            return f'<c r="{ref}"{style_attr} t="str"><f>{escape(expression)}</f><v></v></c>'
        return f'<c r="{ref}"{style_attr}><f>{escape(expression)}</f><v>{cached:.12g}</v></c>'
    style_attr = f' s="{default_style}"' if default_style else ""
    if value is None:
        return f'<c r="{ref}"{style_attr}/>'
    if isinstance(value, bool):
        return f'<c r="{ref}"{style_attr} t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float, Decimal)):
        return f'<c r="{ref}"{style_attr}><v>{format(float(value), ".12g")}</v></c>'
    return f'<c r="{ref}"{style_attr} t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'


def write_sheet(zf: zipfile.ZipFile, index: int, name: str, headers: list[str], rows, widths: list[float], count: int) -> None:
    path = f"xl/worksheets/sheet{index}.xml"
    with zf.open(path, "w") as output:
        output.write(b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
        output.write(b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">')
        output.write(b'<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>')
        output.write(b'<sheetFormatPr defaultRowHeight="15"/>')
        if widths:
            output.write(b'<cols>')
            for i, width in enumerate(widths, start=1):
                output.write(f'<col min="{i}" max="{i}" width="{width:g}" customWidth="1"/>'.encode())
            output.write(b'</cols>')
        output.write(b'<sheetData>')
        output.write(b'<row r="1">')
        for col, header in enumerate(headers, start=1):
            output.write(xml_cell(f"{col_name(col)}1", header, 1).encode("utf-8"))
        output.write(b'</row>')
        for row_number, row in enumerate(rows, start=2):
            output.write(f'<row r="{row_number}">'.encode())
            for col, value in enumerate(row, start=1):
                style = 0
                if isinstance(value, tuple) and value and value[0] == "formula":
                    style = value[3]
                output.write(xml_cell(f"{col_name(col)}{row_number}", value, style).encode("utf-8"))
            output.write(b'</row>')
        output.write(b'</sheetData>')
        if count:
            end = f"{col_name(len(headers))}{count + 1}"
            output.write(f'<autoFilter ref="A1:{end}"/>'.encode())
        output.write(b'</worksheet>')


def workbook_parts(names: list[str]) -> dict[str, bytes]:
    escaped_names = [escape(name) for name in names]
    content_overrides = ''.join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(names) + 1)
    )
    sheets = ''.join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(escaped_names, start=1))
    relationships = ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(names) + 1))
    style_id = len(names) + 1
    relationships += f'<Relationship Id="rId{style_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    return {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            f'{content_overrides}</Types>'
        ).encode(),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'
        ).encode(),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{sheets}</sheets><calcPr calcMode="auto" fullCalcOnLoad="1" forceFullCalc="1"/></workbook>'
        ).encode(),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{relationships}</Relationships>'
        ).encode(),
        "xl/styles.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<numFmts count="2"><numFmt numFmtId="164" formatCode="&quot;£&quot;#,##0.00"/><numFmt numFmtId="165" formatCode="0.0%"/></numFmts>'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF17365D"/><bgColor indexed="64"/></patternFill></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
        ).encode(),
    }


def build(args) -> None:
    sql_dir = args.sql_dir
    monthly_headers, monthly_rows = read_csv(sql_dir / "monthly_portfolio.csv")
    risk_headers, risk_rows = read_csv(sql_dir / "risk_segment.csv")
    vintage_headers, vintage_rows = read_csv(sql_dir / "vintage_mob.csv")
    delinquency_headers, delinquency_rows = read_csv(sql_dir / "delinquency_state.csv")
    roll_headers, roll_rows = read_csv(sql_dir / "roll_rates.csv")
    raw_headers = []
    with args.source.open(newline="", encoding="utf-8") as handle:
        raw_reader = csv.DictReader(handle)
        raw_headers = raw_reader.fieldnames or []

    sheets = [
        ("Start Here", ["Topic", "Details"], [
            ["Project", "Synthetic UK credit-card portfolio review"],
            ["Synthetic status", "All account-level observations and behavior are artificial; no real customer or lender data is present."],
            ["Data window", "2022-01-31 through 2026-09-30; fixed at the latest complete month on 2026-10-30."],
            ["Source", "Account Month Data sheet; generated from data/synthetic_portfolio.csv using seed 20261030."],
            ["SQL source", "SQLite queries under sql/; monetary fields are stored as integer pence to reconcile exactly."],
            ["Monthly Portfolio", "Monthly stock and flow measures. Active payment rates exclude closed rows; final closure receipts are shown separately. Rates are Excel formulas from displayed numerators and denominators; cached values come from SQL."],
            ["Risk Segment", "Month and synthetic origination risk-band cuts; the segment is not a real score or lending policy grade."],
            ["Vintage MOB", "Origination-month cohorts by months on book; observed counts include final closed rows, while active measures exclude them."],
            ["Delinquency State", "Generated delinquency proxy-state distribution. Representative days are not aged from contractual bills."],
            ["Roll Rates", "Account-count transition rates. Closed is an explicit destination; accounts without a next-month observation are excluded."],
            ["Exposure", "Closing balance is an exposure proxy only; it is not EAD or expected loss."],
            ["Utilisation", "Sum of active balances divided by sum of active limits; limit-weighted and can exceed 100%."],
            ["Payment rate", "Active payment receipts divided by active payment due; due-weighted and undefined when total due is zero."],
            ["Limitations", "All generation and transition assumptions are illustrative. Do not infer real arrears, causal macro effects, underwriting policy, or lender outcomes."],
            ["Reproduction", "Run python3 scripts/run_sql_analysis.py then python3 scripts/build_review_workbook.py from the project root."],
        ], [24, 110]),
    ]

    monthly_data = []
    monthly_headers_out = ["Month End", "Active Accounts", "Closed Accounts", "Originations", "Active Balance (GBP)", "Active Limits (GBP)", "Utilisation", "Simulated 30+ State Accounts", "Simulated 30+ State Balance (GBP)", "Simulated 30+ Account Rate", "Simulated 30+ Balance Rate", "Active Payment Due (GBP)", "Active Payment Received (GBP)", "Closed Final Payment Received (GBP)", "Active Payment Rate"]
    for row in monthly_rows:
        n = len(monthly_data) + 2
        bal = Decimal(row["active_balance_pence"])
        lim = Decimal(row["active_limit_pence"])
        cnt = int(row["active_accounts"])
        dpd_cnt = int(row["simulated_30plus_accounts"])
        dpd_bal = Decimal(row["simulated_30plus_balance_pence"])
        due = Decimal(row["active_payment_due_pence"])
        received = Decimal(row["active_payment_received_pence"])
        closed_received = Decimal(row["closed_final_payment_received_pence"])
        monthly_data.append([
            row["snapshot_month"], cnt, int(row["closed_accounts"]), int(row["originations"]),
            float(bal / 100), float(lim / 100), formula(f"IF(F{n}=0,\"\",E{n}/F{n})", ratio(bal, lim), 3),
            dpd_cnt, float(dpd_bal / 100), formula(f"IF(B{n}=0,\"\",H{n}/B{n})", ratio(dpd_cnt, cnt), 3),
            formula(f"IF(E{n}=0,\"\",I{n}/E{n})", ratio(dpd_bal, bal), 3),
            float(due / 100), float(received / 100), float(closed_received / 100), formula(f"IF(L{n}=0,\"\",M{n}/L{n})", ratio(received, due), 3),
        ])
    sheets.append(("Monthly Portfolio", monthly_headers_out, monthly_data, [14, 15, 15, 13, 20, 19, 14, 24, 28, 25, 25, 23, 28, 32, 16]))

    risk_data = []
    risk_headers_out = ["Month End", "Risk Segment", "Active Accounts", "Active Balance (GBP)", "Active Limits (GBP)", "Utilisation", "Simulated 30+ State Accounts", "Simulated 30+ Account Rate", "Simulated 30+ State Balance (GBP)", "Simulated 30+ Balance Rate", "Active Payment Due (GBP)", "Active Payment Received (GBP)", "Payment Rate"]
    for row in risk_rows:
        n = len(risk_data) + 2
        bal, lim = Decimal(row["active_balance_pence"]), Decimal(row["active_limit_pence"])
        cnt, dpd_cnt = int(row["active_accounts"]), int(row["simulated_30plus_accounts"])
        dpd_bal = Decimal(row["simulated_30plus_balance_pence"])
        due, received = Decimal(row["active_payment_due_pence"]), Decimal(row["active_payment_received_pence"])
        risk_data.append([
            row["snapshot_month"], row["risk_segment"], cnt, float(bal / 100), float(lim / 100),
            formula(f"IF(E{n}=0,\"\",D{n}/E{n})", ratio(bal, lim), 3), dpd_cnt,
            formula(f"IF(C{n}=0,\"\",G{n}/C{n})", ratio(dpd_cnt, cnt), 3), float(dpd_bal / 100),
            formula(f"IF(D{n}=0,\"\",I{n}/D{n})", ratio(dpd_bal, bal), 3),
            float(due / 100), float(received / 100), formula(f"IF(K{n}=0,\"\",L{n}/K{n})", ratio(received, due), 3),
        ])
    sheets.append(("Risk Segment", risk_headers_out, risk_data, [14, 14, 16, 20, 18, 14, 25, 25, 29, 25, 23, 28, 14]))

    vintage_data = []
    vintage_headers_out = ["Origination Month", "MOB", "Observed Accounts", "Active Accounts", "Closed Accounts", "Active Balance (GBP)", "Active Limits (GBP)", "Utilisation", "Simulated 30+ State Accounts", "Simulated 30+ Account Rate", "Simulated 30+ State Balance (GBP)", "Simulated 30+ Balance Rate", "Active Payment Due (GBP)", "Active Payment Received (GBP)", "Payment Rate"]
    for row in vintage_rows:
        n = len(vintage_data) + 2
        obs, active, closed = int(row["observed_accounts"]), int(row["active_accounts"]), int(row["closed_accounts"])
        bal, lim = Decimal(row["active_balance_pence"]), Decimal(row["active_limit_pence"])
        dpd_cnt, dpd_bal = int(row["simulated_30plus_accounts"]), Decimal(row["simulated_30plus_balance_pence"])
        due, received = Decimal(row["active_payment_due_pence"]), Decimal(row["active_payment_received_pence"])
        vintage_data.append([
            row["origination_month"], int(row["mob"]), obs, active, closed, float(bal / 100), float(lim / 100),
            formula(f"IF(G{n}=0,\"\",F{n}/G{n})", ratio(bal, lim), 3), dpd_cnt,
            formula(f"IF(D{n}=0,\"\",I{n}/D{n})", ratio(dpd_cnt, active), 3), float(dpd_bal / 100),
            formula(f"IF(F{n}=0,\"\",K{n}/F{n})", ratio(dpd_bal, bal), 3), float(due / 100), float(received / 100),
            formula(f"IF(M{n}=0,\"\",N{n}/M{n})", ratio(received, due), 3),
        ])
    sheets.append(("Vintage MOB", vintage_headers_out, vintage_data, [16, 9, 18, 16, 16, 22, 20, 14, 27, 27, 29, 25, 24, 29, 14]))

    delinquency_data = []
    delinquency_headers_out = ["Month End", "Generated State", "Active Accounts", "Active Balance (GBP)", "Monthly Active Accounts", "Monthly Active Balance (GBP)", "Account Share", "Balance Share"]
    for row in delinquency_rows:
        n = len(delinquency_data) + 2
        active, monthly_active = int(row["active_accounts"]), int(row["monthly_active_accounts"])
        bal, monthly_bal = Decimal(row["active_balance_pence"]), Decimal(row["monthly_active_balance_pence"])
        delinquency_data.append([
            row["snapshot_month"], row["delinquency_status"], active, float(bal / 100), monthly_active,
            float(monthly_bal / 100), formula(f"IF(E{n}=0,\"\",C{n}/E{n})", ratio(active, monthly_active), 3),
            formula(f"IF(F{n}=0,\"\",D{n}/F{n})", ratio(bal, monthly_bal), 3),
        ])
    sheets.append(("Delinquency State", delinquency_headers_out, delinquency_data, [14, 18, 17, 22, 23, 28, 16, 16]))

    roll_data = []
    roll_headers_out = ["Opening Month", "Opening State", "Destination State", "Transitioned Accounts", "Opening Accounts with Outcome", "Roll Rate"]
    for row in roll_rows:
        n = len(roll_data) + 2
        count, denom = int(row["transitioned_accounts"]), int(row["opening_accounts_with_outcome"])
        roll_data.append([
            row["opening_month"], row["opening_state"], row["destination_state"], count, denom,
            formula(f"IF(E{n}=0,\"\",D{n}/E{n})", ratio(count, denom), 3),
        ])
    sheets.append(("Roll Rates", roll_headers_out, roll_data, [16, 18, 20, 23, 32, 14]))

    notes_headers = ["Field", "Source / definition"]
    notes_data = [
        ["Metric source", "Every displayed numerator and denominator is exported from the T03 SQLite queries; ratio formulas are visible in Excel."],
        ["Money precision", "SQL stores source money in integer pence. Workbook displays GBP; formatting/rounding is for presentation only."],
        ["Portfolio utilisation", "Active closing balance / active credit limits. Limit weighted, not a mean of account ratios."],
        ["30+ state measures", "Generated delinquency-state proxy using representative days. Not actual arrears aged from billing dates."],
        ["Roll rates", "Account-count transitions from an opening state to next-month destination; CLOSED is explicit; right-censored accounts excluded."],
        ["Vintage", "Origination-month cohort; MOB 0 is the origination month. Observed count includes closed final rows; active rates use active accounts."],
        ["Payment rate", "Active receipts / active due. Due-weighted and undefined when due is zero."],
        ["Exposure", "Closing balance is a synthetic exposure proxy, not EAD or expected loss."],
        ["Source lineage", "CSV → SQLite tables via scripts/run_sql_analysis.py → SQL result CSVs → this workbook."],
    ]
    sheets.insert(0, ("Metric Notes", notes_headers, notes_data, [24, 115]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    names = [sheet[0] for sheet in sheets] + ["Account Month Data"]
    parts = workbook_parts(names)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path, content in parts.items():
            zf.writestr(path, content)
        for i, (name, headers, rows, *rest) in enumerate(sheets, start=1):
            widths = rest[0] if rest else [18] * len(headers)
            write_sheet(zf, i, name, headers, rows, widths, len(rows))
        data_sheet_index = len(sheets) + 1
        def source_rows():
            with args.source.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for raw in reader:
                    values = []
                    for field in raw_headers:
                        value = raw[field]
                        if field in MONEY_FIELDS:
                            values.append(float(Decimal(value)))
                        elif field == "days_past_due":
                            values.append(int(value))
                        else:
                            values.append(value)
                    yield values
        with args.source.open(encoding="utf-8") as count_handle:
            source_row_count = sum(1 for _ in count_handle) - 1
        write_sheet(zf, data_sheet_index, "Account Month Data", raw_headers, source_rows(), [15] * len(raw_headers), source_row_count)
    print(f"Created {args.output} with {len(names)} sheets and {source_row_count:,} synthetic source rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data/synthetic_portfolio.csv")
    parser.add_argument("--sql-dir", type=Path, default=ROOT / "reports/t03/sql")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/credit_portfolio_review.xlsx")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
