"""
CONSOLIDATED_BANK_STATEMENT_PARSER.py

Master multi-account bank statement parser and financial aggregation engine.
Automatically scans the BANK_STATEMENT/ directory for any statement files
(HDFC Bank, Bank of Baroda, and extensible to future banks), extracts and
categorizes transactions, merges them across all accounts with an Account/Bank label,
and generates unified consolidated & month-wise reports (Excel, HTML, TXT, Logs).

Usage:
    python CONSOLIDATED_BANK_STATEMENT_PARSER.py
    python CONSOLIDATED_BANK_STATEMENT_PARSER.py --input BANK_STATEMENT --output-dir Financial_Reports
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
import pandas as pd
import pdfplumber

from CATEGORY_CONFIG import (
    CATEGORY_RULES,
    TRANSPORT_NARRATION_PATTERNS,
    parse_date,
    clean_amount,
    week_number_in_month,
    detect_type,
    extract_time_from_narration,
    classify_category,
    apply_daily_transport_heuristic,
    deduplicate_transactions,
    extract_merchant_key,
)
from HDFC_BANK_STATEMENT_PARSER import (
    extract_transactions_from_pdf as extract_hdfc_pdf,
    extract_transactions_from_txt as extract_hdfc_txt,
    write_monthly_report,
    write_monthly_processing_log,
    write_all_processing_log,
    write_execution_log,
    month_sort_key,
)
from BOB_BANK_STATEMENT_PARSER import extract_transactions_from_bob_pdf
from HTML_REPORT_GENERATOR import generate_html_dashboard


# -----------------------------
# 1. Bank Type Detection & Dispatcher
# -----------------------------

def detect_bank_from_file(file_path: Path) -> str:
    """Detect whether a statement PDF belongs to HDFC, Bank of Baroda, etc."""
    suffix = file_path.suffix.lower()
    if suffix == ".txt":
        return "HDFC"

    if suffix == ".pdf":
        try:
            with pdfplumber.open(str(file_path)) as pdf:
                if not pdf.pages:
                    return "HDFC"
                # Check first page text content
                page_text = (pdf.pages[0].extract_text() or "").upper()
                if "BANK OF BARODA" in page_text or "BARODA" in page_text or "SAVINGS ACCOUNT - 7393" in page_text or "WITHDRAWAL (DR)" in page_text:
                    return "BOB"
                if "HDFC BANK" in page_text or "HDFC" in page_text or "DOMLUR LAYOUT" in page_text:
                    return "HDFC"
        except Exception as e:
            print(f"Warning reading {file_path.name}: {e}")

        # Fallback check on file name
        fname = file_path.stem.upper()
        if "BARODA" in fname or "BOB" in fname:
            return "BOB"
        return "HDFC"

    return "HDFC"


def parse_statement_file(file_path: Path) -> pd.DataFrame:
    """Route statement file to appropriate bank extractor."""
    bank_type = detect_bank_from_file(file_path)
    suffix = file_path.suffix.lower()

    if bank_type == "BOB":
        df = extract_transactions_from_bob_pdf(str(file_path))
        if not df.empty and "Bank" not in df.columns:
            df["Bank"] = "Bank of Baroda"
        return df
    else:
        if suffix == ".pdf":
            df = extract_hdfc_pdf(str(file_path))
        elif suffix == ".txt":
            df = extract_hdfc_txt(str(file_path))
        else:
            raise ValueError(f"Unsupported format: {file_path.suffix}")

        if not df.empty and "Bank" not in df.columns:
            df["Bank"] = "HDFC Bank"
        return df


def collect_statement_files(input_paths: str | list[str]) -> list[Path]:
    """Scan and collect all PDF and TXT statement files from directories or paths."""
    if isinstance(input_paths, str):
        input_paths = [input_paths]

    files = []
    for inp in input_paths:
        p = Path(inp)
        if p.is_dir():
            files.extend(
                f for f in sorted(p.iterdir())
                if f.is_file() and f.suffix.lower() in {".pdf", ".txt"}
            )
        elif p.is_file() and p.suffix.lower() in {".pdf", ".txt"}:
            files.append(p)
        else:
            print(f"Skipping unavailable or unsupported input: {p}")
    return files


# -----------------------------
# 2. Consolidated Report Generation
# -----------------------------

def generate_all_consolidated_reports(df: pd.DataFrame, output_dir: str) -> list[Path]:
    """Generate consolidated master reports and month-by-month reports for all bank accounts."""
    generated_reports = []
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Helper function to generate clean bank abbreviations for filenames
    def get_bank_code(bname: str) -> str:
        b = str(bname).upper()
        if "BARODA" in b or "BOB" in b:
            return "BoB"
        if "HDFC" in b:
            return "HDFC"
        return re.sub(r"[^A-Za-z0-9]", "", str(bname))

    # 1. Consolidated master processing log (All Accounts, All Months)
    all_months_log = output_path / "Processing_Log.txt"
    write_all_processing_log(df.copy(), all_months_log)
    generated_reports.append(all_months_log)
    print(f"Created (All Accounts Master Log): {all_months_log}")

    # 1b. Per-bank consolidated processing logs across all months
    if "Bank" in df.columns and df["Bank"].nunique() > 1:
        for bank_name, bank_df in df.groupby("Bank", sort=False):
            b_str = str(bank_name)
            bank_code = get_bank_code(b_str)
            bank_log_path = output_path / f"Processing_Log_{bank_code}.txt"
            write_all_processing_log(bank_df.copy(), bank_log_path, bank_name=b_str)
            generated_reports.append(bank_log_path)
            print(f"Created (All Months Log - {b_str}): {bank_log_path}")

    # 2. Consolidated interactive HTML dashboard (All Accounts, All Months)
    all_months_html = output_path / "Financial_Dashboard_All_Months.html"
    accounts_str = ", ".join(sorted(df["Bank"].unique())) if "Bank" in df.columns else "All Accounts"
    generate_html_dashboard(
        df=df.copy(),
        output_html_path=all_months_html,
        title="Consolidated Bank Statements - Financial & Spending Dashboard",
        subtitle=f"Aggregated Overview for {accounts_str} ({df['MonthYear'].nunique()} Months)",
    )
    generated_reports.append(all_months_html)
    print(f"Created (All Accounts HTML Dashboard): {all_months_html}")

    # 3. Month-wise folder packages (Excel + HTML + TXT + Combined Log + Per-Bank Logs)
    for month_year, month_df in df.groupby("MonthYear", sort=False):
        report_date = month_sort_key(str(month_year))
        folder = output_path / str(report_date.year) / report_date.strftime("%m-%B")
        folder.mkdir(parents=True, exist_ok=True)
        base_name = f"{report_date:%Y-%m}_Financial_Summary"
        excel_path = folder / f"{base_name}.xlsx"
        text_path = folder / f"{base_name}.txt"
        log_path = folder / f"{report_date:%Y-%m}_Processing_Log.txt"
        html_path = folder / f"{base_name}.html"

        # Excel & Text summary
        write_monthly_report(month_df.copy(), excel_path, text_path)

        # Combined Processing log
        write_monthly_processing_log(month_df.copy(), log_path)
        generated_reports.extend([excel_path, text_path, log_path, html_path])

        # Per-Bank separate processing logs for this month
        if "Bank" in month_df.columns:
            for bank_name, b_df in month_df.groupby("Bank", sort=False):
                b_str = str(bank_name)
                bank_code = get_bank_code(b_str)
                b_log_path = folder / f"{report_date:%Y-%m}_Processing_Log_{bank_code}.txt"
                write_monthly_processing_log(b_df.copy(), b_log_path, bank_name=b_str)
                generated_reports.append(b_log_path)
                print(f"  -> Created separate bank log: {b_log_path.name}")

        # Monthly interactive HTML dashboard
        generate_html_dashboard(
            df=month_df.copy(),
            output_html_path=html_path,
            title=f"Financial Summary - {report_date.strftime('%B %Y')}",
            subtitle=f"Aggregated Spending Breakdown & Transactions for {report_date.strftime('%B %Y')}",
        )

        print(f"Created Month Package: {folder.name} (Excel, HTML, TXT, Combined Log & Per-Bank Logs)")

    return generated_reports


# -----------------------------
# 3. Main Master Runner
# -----------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Consolidated Multi-Bank Statement Parser & Financial Aggregator."
    )
    parser.add_argument(
        "--input", "-i", nargs="+", default=["BANK_STATEMENT"],
        help="Statement file(s) or folder(s); default: BANK_STATEMENT.",
    )
    parser.add_argument(
        "--output-dir", "-o", default="Financial_Reports",
        help="Folder for consolidated and monthly reports (default: Financial_Reports).",
    )
    parser.add_argument(
        "--log-file", "-l", default="HDFC_BANK_STATEMENT_PARSER.log",
        help="Path to execution log file (default: HDFC_BANK_STATEMENT_PARSER.log).",
    )
    args = parser.parse_args()

    log_path = Path(args.log_file).resolve()
    input_files = collect_statement_files(args.input)
    if not input_files:
        print("No .pdf or .txt statement files found in BANK_STATEMENT directory.")
        return

    print("=" * 70)
    print("CONSOLIDATED MULTI-BANK STATEMENT PARSER")
    print("=" * 70)
    print(f"Scanning input sources ({len(input_files)} file(s) found):")

    extracted_dfs = []
    for f in input_files:
        bank_type = detect_bank_from_file(f)
        bank_label = "Bank of Baroda" if bank_type == "BOB" else "HDFC Bank"
        print(f"  • Reading [{bank_label}]: {f.name}")
        df_single = parse_statement_file(f)
        if df_single.empty:
            print(f"    -> Warning: 0 transactions found in {f.name}")
            continue
        print(f"    -> Extracted {len(df_single)} transaction(s)")
        extracted_dfs.append(df_single)

    if not extracted_dfs:
        print("No transactions extracted from statement files.")
        return

    # Combine all transactions across all accounts
    df_raw = pd.concat(extracted_dfs, ignore_index=True).sort_values("Date").reset_index(drop=True)
    df_raw = df_raw[df_raw["Amount (₹)"] > 0].reset_index(drop=True)

    # Intelligent Deduplication Algorithm using visited-hash fingerprinting
    df_master, dup_count = deduplicate_transactions(df_raw)
    if dup_count > 0:
        print(f"  • Deduplication Engine : Detected and removed {dup_count} duplicate/overlapping transaction(s).")
    else:
        print("  • Deduplication Engine : 0 duplicates found (all transactions unique).")

    # Apply daily transport heuristic
    transport_count_before = (df_master["Category"] == "Transport").sum()
    df_master = apply_daily_transport_heuristic(df_master)
    heuristic_count = (df_master["Category"] == "Transport").sum() - transport_count_before

    unique_months = df_master["MonthYear"].nunique()
    unique_accounts = df_master["Bank"].nunique() if "Bank" in df_master.columns else 1
    total_debits = df_master.loc[df_master["Type"] == "Debit", "Amount (₹)"].sum()
    total_credits = df_master.loc[df_master["Type"] == "Credit", "Amount (₹)"].sum()

    print("\n" + "-" * 70)
    print("AGGREGATION SUMMARY:")
    print(f"  • Total Transactions : {len(df_master)}")
    print(f"  • Accounts Included  : {unique_accounts} ({', '.join(sorted(df_master['Bank'].unique()))})")
    print(f"  • Date Span Covered  : {df_master['Date'].min().strftime('%d-%m-%Y')} to {df_master['Date'].max().strftime('%d-%m-%Y')} ({unique_months} month(s))")
    print(f"  • Total Credits      : ₹{total_credits:,.2f}")
    print(f"  • Total Debits       : ₹{total_debits:,.2f}")
    print(f"  • Net Cashflow       : ₹{(total_credits - total_debits):,.2f}")
    print(f"  • Transport Matches  : {heuristic_count} transactions reclassified")
    print("-" * 70 + "\n")

    print("Building consolidated Excel, interactive HTML dashboards, and processing logs...")
    reports = generate_all_consolidated_reports(df_master, args.output_dir)

    # Dump master execution log
    write_execution_log(
        log_path=log_path,
        input_files=input_files,
        df=df_master,
        heuristic_count=heuristic_count,
        generated_files=reports,
        status="SUCCESS",
    )
    print("\n✓ Consolidated processing and reporting complete!")


if __name__ == "__main__":
    main()
