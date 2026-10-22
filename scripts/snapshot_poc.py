#!/usr/bin/env python3
"""L2 snapshot extraction POC — reads a forecast workbook (never writes to it)
and emits a tidy observation file.

Row shape: (source_file, sheet, row_label, col_header, value, cell_ref)
Keying is semantic (sheet + label path + column header), not cell address,
so diffs survive layout shifts.

Usage:
  python snapshot_poc.py <workbook.xlsx> [--sheet NAME ...] [--out observations.csv]

This POC captures the visible sheets' header/label/value grid as a first pass;
productionizing it = applying the dependency map to split input vs calc cells.
"""
import argparse, csv, os, re, sys

def norm(v):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s if s else None
    return v

def col_header(ws, header_rows, max_col):
    """Find the row that looks like month headers (202601-style / dates), return mapping."""
    from openpyxl.utils import get_column_letter
    for r in header_rows:
        hdr = {}
        for c in range(1, max_col + 1):
            v = ws.cell(row=r, column=c).value
            if isinstance(v, str) and re.fullmatch(r"20\d{4}", v.strip()):
                hdr[get_column_letter(c)] = v.strip()
        if len(hdr) >= 3:
            return r, hdr
    return None, {}

def snapshot(path, only_sheets=None, out="observations.csv"):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=False, data_only=True)  # data_only = values, not formulas
    rows_written = 0
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_file", "sheet", "row_label", "col_header", "value", "cell_ref"])
        for ws in wb.worksheets:
            if ws.sheet_state != "visible":
                continue
            if only_sheets and ws.title not in only_sheets:
                continue
            max_col = min(ws.max_column, 60)
            hrow, hmap = None, {}
            for r in range(1, min(ws.max_row, 20)):  # look in first 20 rows
                hrow, hmap = col_header(ws, [r], max_col)
                if hrow:
                    break
            if not hmap:
                continue
            for r in range(1, ws.max_row + 1):
                if r == hrow:
                    continue
                # row label = LAST (most specific) non-empty text in cols A..F
                label = None
                for c in range(1, 7):
                    v = norm(ws.cell(row=r, column=c).value)
                    if isinstance(v, str):
                        label = v
                if not label:
                    continue
                for col_letter, header in hmap.items():
                    cell = ws[f"{col_letter}{r}"]
                    v = norm(cell.value)
                    if isinstance(v, (int, float)):
                        w.writerow([os.path.basename(path), ws.title, label, header, v, cell.coordinate])
                        rows_written += 1
            print(f"  {ws.title}: up to row {r} scanned", file=sys.stderr)
    print(f"wrote {rows_written} observations -> {out}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("workbook")
    ap.add_argument("--sheet", action="append", dest="sheets")
    ap.add_argument("--out", default="observations.csv")
    a = ap.parse_args()
    snapshot(a.workbook, a.sheets, a.out)
