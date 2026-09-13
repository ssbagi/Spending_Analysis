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


def _extract_bob_transactions_from_text(page_text: str) -> list[dict]:
    """Extract savings-account rows from BoB's wrapped text layout."""
    if "Statement of transactions in Savings Account" not in page_text:
        return []

    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    date_pattern = re.compile(r"^(\d{2}-\d{2}-\d{4})\s*(.*)$")
    transaction_rows = []
    previous_balance = None

    for index, line in enumerate(lines):
        match = date_pattern.match(line)
        if not match:
            continue

        date_str, date_body = match.groups()
        balance_match = re.search(r"(\d[\d,]*\.\d{2})\s+(?:Cr|Dr)\s*$", date_body)
        if not balance_match:
            continue

        balance = clean_amount(balance_match.group(1))
        body_without_balance = date_body[:balance_match.start()].strip()
        if "opening balance" in body_without_balance.lower():
            previous_balance = balance
            continue
        if "closing balance" in body_without_balance.lower():
            continue

        amount_matches = list(re.finditer(r"\b\d[\d,]*\.\d{2}\b", body_without_balance))
        if not amount_matches:
            continue

        amount = clean_amount(amount_matches[-1].group(0))
        body_narration = body_without_balance[:amount_matches[-1].start()].strip()

        # For wrapped UPI rows, the narration is printed before the date.
        narration = body_narration
        if not narration or narration.replace(" ", "").isdigit():
            narration = ""
            for prior_line in reversed(lines[:index]):
                if re.search(r"\b(?:UPI|UDIR)/", prior_line, re.IGNORECASE):
                    narration = prior_line
                    break
                if re.match(r"^\d{2}-\d{2}-\d{4}", prior_line):
                    break

        # A wrapped continuation such as "ollect" follows the dated row.
        continuation = []
        for following_line in lines[index + 1:]:
            if date_pattern.match(following_line):
                break
            if re.search(r"\b(?:UPI|UDIR)/", following_line, re.IGNORECASE):
                break
            if following_line.lower().startswith("page "):
                break
            continuation.append(following_line)
        narration = " ".join(part for part in [narration, *continuation] if part).strip()

        if previous_balance is None or amount <= 0:
            previous_balance = balance
            continue

        tx_type = "Debit" if balance < previous_balance else "Credit"
        transaction_rows.append({
            "date_str": date_str,
            "narration": narration,
            "amount": amount,
            "balance": balance,
            "type": tx_type,
        })
        previous_balance = balance

    return transaction_rows


def extract_transactions_from_bob_pdf(pdf_path: str) -> pd.DataFrame:
    """Extract transactions from a Bank of Baroda statement PDF."""
    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        text_rows = []
        for page in pdf.pages:
            text_rows.extend(_extract_bob_transactions_from_text(page.extract_text() or ""))

        if text_rows:
            for item in text_rows:
                try:
                    dt = parse_date(item["date_str"])
                except ValueError:
                    continue
                tx_time = extract_time_from_narration(item["narration"])
                rows.append({
                    "Date": dt,
                    "Month": dt.strftime("%B"),
                    "MonthYear": dt.strftime("%b-%Y"),
                    "WeekNumberInMonth": week_number_in_month(dt),
                    "Bank": "Bank of Baroda",
                    "Narration": item["narration"],
                    "Category": classify_category(item["narration"], tx_time),
                    "Type": item["type"],
                    "Amount (₹)": item["amount"],
                    "Closing Balance (₹)": item["balance"],
                    "ChqRefNo": "",
                })

        if rows:
            df = pd.DataFrame(rows)
            df = df[df["Amount (₹)"] > 0]
            df, _, _ = deduplicate_transactions(df)
            df.sort_values("Date", inplace=True)
            df.reset_index(drop=True, inplace=True)
            return df

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
