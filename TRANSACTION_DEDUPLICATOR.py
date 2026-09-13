"""
TRANSACTION_DEDUPLICATOR.py

Generic, reusable transaction deduplication engine.
Uses a 'Visited Hash Set' (graph node traversal / fingerprinting pattern)
to eliminate duplicate or overlapping bank statement records.

Concept:
  Like BFS/DFS graph node traversal tracking `visited = set()`, each transaction
  is mapped to a deterministic SHA-256 / composite hash signature:
    Fingerprint = Date | Bank | Type | Amount | RefNo / Balance | Normalized Narration
  If a fingerprint is already in `visited`, the duplicate is dropped.
"""

import re
import hashlib
from typing import Tuple, List, Dict, Any
import pandas as pd


def compute_transaction_fingerprint(row: Dict[str, Any] | pd.Series) -> str:
    """
    Generate a deterministic fingerprint hash for a bank transaction record.

    Components:
      1. Transaction Date (Standardized YYYY-MM-DD)
      2. Bank Account Identifier (e.g. HDFC Bank, Bank of Baroda)
      3. Transaction Type (DEBIT vs CREDIT)
      4. Exact Amount (Normalized to 2 decimal places)
      5. Reference / Cheque / UTR Number (if available and valid)
      6. Closing Balance + Normalized Narration (fallback when Ref No is missing)
    """
    # 1. Date normalization
    date_raw = row.get("Date", "")
    if hasattr(date_raw, "strftime"):
        date_str = date_raw.strftime("%Y-%m-%d")
    else:
        date_str = str(date_raw).strip()[:10]

    # 2. Bank identification
    bank_str = str(row.get("Bank", "DEFAULT")).strip().upper()

    # 3. Transaction Type
    tx_type = str(row.get("Type", "")).strip().upper()

    # 4. Amount formatting
    try:
        amount_val = f"{float(str(row.get('Amount (₹)', 0)).replace(',', '')):.2f}"
    except Exception:
        amount_val = "0.00"

    # 5. Reference / Cheque number check
    chq_ref = str(row.get("ChqRefNo", "")).strip().upper()
    valid_chq = chq_ref not in ("", "NONE", "0", "NAN", "NULL")

    # 6. Normalized Narration (strip punctuation/timestamps/whitespace variations)
    raw_narr = str(row.get("Narration", "")).upper()
    norm_narr = re.sub(r"[^A-Z0-9]", " ", raw_narr)
    norm_narr = " ".join(norm_narr.split())[:60]

    if valid_chq:
        # High-confidence fingerprint using bank reference number
        composite_key = f"{date_str}|{bank_str}|{tx_type}|{amount_val}|{chq_ref}"
    else:
        # Fallback composite key using closing balance and normalized narration
        try:
            closing_val = f"{float(str(row.get('Closing Balance (₹)', 0)).replace(',', '')):.2f}"
        except Exception:
            closing_val = "0.00"
        composite_key = f"{date_str}|{bank_str}|{tx_type}|{amount_val}|{closing_val}|{norm_narr}"

    # Return hashed signature (or raw composite key)
    return hashlib.sha256(composite_key.encode("utf-8")).hexdigest()


class TransactionGraphDeduplicator:
    """
    Visited-Set Tracker for stream-based or batch-based transaction deduplication.
    Mirrors graph node visitation:
      - node = Transaction
      - visited_set = Set of seen transaction hashes
    """

    def __init__(self):
        self.visited_fingerprints: set[str] = set()
        self.duplicate_records: List[Dict[str, Any]] = []

    def is_visited(self, row: Dict[str, Any] | pd.Series) -> bool:
        """Check if a transaction has already been visited/processed."""
        fp = compute_transaction_fingerprint(row)
        return fp in self.visited_fingerprints

    def mark_visited(self, row: Dict[str, Any] | pd.Series) -> bool:
        """
        Attempt to mark a transaction as visited.
        Returns:
          True  -> New unique transaction (successfully visited)
          False -> Duplicate transaction (already visited)
        """
        fp = compute_transaction_fingerprint(row)
        if fp in self.visited_fingerprints:
            self.duplicate_records.append(dict(row))
            return False
        self.visited_fingerprints.add(fp)
        return True

    def deduplicate_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        """
        Filter a pandas DataFrame, keeping only first occurrences of unique transactions.

        Returns:
            Tuple[pd.DataFrame, int]: (deduplicated_dataframe, duplicate_count)
        """
        if df.empty:
            return df, 0

        initial_count = len(df)
        unique_indices = []

        for idx, row in df.iterrows():
            if self.mark_visited(row):
                unique_indices.append(idx)

        deduped_df = df.loc[unique_indices].reset_index(drop=True)
        duplicates_removed = initial_count - len(deduped_df)
        return deduped_df, duplicates_removed


# Standalone Helper Function
def deduplicate_transactions_generic(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Single-call convenience function for transaction DataFrame deduplication."""
    tracker = TransactionGraphDeduplicator()
    return tracker.deduplicate_dataframe(df)


# -----------------------------
# Demonstration / Unit Test
# -----------------------------
if __name__ == "__main__":
    print("=" * 65)
    print("TRANSACTION DEDUPLICATOR - VISITED HASH ALGORITHM TEST")
    print("=" * 65)

    # Simulated overlapping upload scenario:
    # PDF 1: Jan-Feb-Mar
    # PDF 2: Mar-Apr (March 1st transaction appears in both PDFs)
    sample_transactions = pd.DataFrame([
        {
            "Date": "01-03-2026",
            "Bank": "HDFC Bank",
            "Narration": "UPI-MUDULI STORE-OMBK... 77@MBK-PPIW0881822",
            "Type": "Debit",
            "Amount (₹)": 10.00,
            "Closing Balance (₹)": 501236.88,
            "ChqRefNo": "0000994337498083"
        },
        {
            # Exact duplicate from overlapping statement
            "Date": "01-03-2026",
            "Bank": "HDFC Bank",
            "Narration": "UPI-MUDULI STORE-OMBK... 77@MBK-PPIW0881822",
            "Type": "Debit",
            "Amount (₹)": 10.00,
            "Closing Balance (₹)": 501236.88,
            "ChqRefNo": "0000994337498083"
        },
        {
            "Date": "01-03-2026",
            "Bank": "HDFC Bank",
            "Narration": "UPI-SANNARANGEGOWDA T-Q273289229@YBL",
            "Type": "Debit",
            "Amount (₹)": 231.00,
            "Closing Balance (₹)": 501005.88,
            "ChqRefNo": "0000445744353305"
        },
        {
            # Legitimate separate transaction on same day with same amount but different Ref No
            "Date": "01-03-2026",
            "Bank": "HDFC Bank",
            "Narration": "UPI-TEA-STALL-PAYMENT",
            "Type": "Debit",
            "Amount (₹)": 10.00,
            "Closing Balance (₹)": 500995.88,
            "ChqRefNo": "0000994337499999"
        }
    ])

    deduped_df, removed_count = deduplicate_transactions_generic(sample_transactions)

    print(f"Total Input Records      : {len(sample_transactions)}")
    print(f"Duplicates Detected & Cut: {removed_count}")
    print(f"Unique Records Preserved : {len(deduped_df)}")
    print("\nResulting Clean Records:")
    for _, r in deduped_df.iterrows():
        print(f"  ✓ {r['Date']} | Ref: {r['ChqRefNo']} | ₹{r['Amount (₹)']:6.2f} | {r['Narration'][:40]}")
    print("=" * 65)
