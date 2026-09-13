"""
BOB_BANK_STATEMENT_PARSER.py

Parses Bank of Baroda Bank statement PDFs (table format: DATE | NARRATION | CHQ.NO. |
WITHDRAWAL (DR) | DEPOSIT (CR) | BALANCE) and extracts categorized transactions.
Can be executed standalone or invoked via the unified multi-bank pipeline.

Usage:
    python BOB_BANK_STATEMENT_PARSER.py --input BANK_STATEMENT/BANK_STATEMENT_BANK_OF_BARODA.pdf --output-dir Financial_Reports
"""

import argparse
import re
from pathlib import Path
import pandas as pd
import pdfplumber

from CATEGORY_CONFIG import (
    parse_date,
    clean_amount,
    week_number_in_month,
    detect_type,
    extract_time_from_narration,
    classify_category,
    deduplicate_transactions,
)


def extract_transactions_from_bob_pdf(pdf_path: str) -> pd.DataFrame:
    """Extract transactions from a Bank of Baroda statement PDF."""
    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                for r in table:
                    if not r or len(r) < 6:
                        continue
                    date_str = str(r[0] or "").strip()
                    if not re.match(r"^\d{2}[-/]\d{2}[-/]\d{2,4}$", date_str):
                        continue

                    narration = str(r[1] or "").replace("\n", " ").strip()
                    if narration.lower().startswith("opening balance"):
                        continue

                    chq = str(r[2] or "").strip()
                    w_val = clean_amount(r[3])
                    d_val = clean_amount(r[4])
                    bal_val = clean_amount(r[5])

                    if w_val <= 0 and d_val <= 0:
                        continue

                    tx_type = detect_type(w_val, d_val)
                    amt = w_val if tx_type == "Debit" else d_val
                    if amt <= 0:
                        continue

                    try:
                        dt = parse_date(date_str)
                    except ValueError:
                        continue

                    tx_time = extract_time_from_narration(narration)

                    rows.append({
                        "Date": dt,
                        "Month": dt.strftime("%B"),
                        "MonthYear": dt.strftime("%b-%Y"),
                        "WeekNumberInMonth": week_number_in_month(dt),
                        "Bank": "Bank of Baroda",
                        "Narration": narration,
                        "Category": classify_category(narration, tx_time),
                        "Type": tx_type,
                        "Amount (₹)": amt,
                        "Closing Balance (₹)": bal_val,
                        "ChqRefNo": chq,
                    })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df[df["Amount (₹)"] > 0]
        df, _, _ = deduplicate_transactions(df)
        df.sort_values("Date", inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Parse Bank of Baroda statement PDF.")
    parser.add_argument(
        "--input", "-i", nargs="+", default=["BANK_STATEMENT"],
        help="Statement file(s) or folder(s).",
    )
    parser.add_argument(
        "--output-dir", "-o", default="Financial_Reports",
        help="Folder for report packages.",
    )
    args = parser.parse_args()

    # Import master reporting functions
    from HDFC_BANK_STATEMENT_PARSER import write_reports_by_month

    for inp in args.input:
        p = Path(inp)
        if p.is_file() and p.suffix.lower() == ".pdf":
            print(f"Reading Bank of Baroda statement: {p}")
            df = extract_transactions_from_bob_pdf(str(p))
            if not df.empty:
                print(f"Extracted {len(df)} transactions.")
                write_reports_by_month(df, args.output_dir)
            else:
                print(f"No transactions found in {p}")


if __name__ == "__main__":
    main()
