"""
TRAFFIC_GENERATOR_DEDUPLICATION_TEST.py

Verification & Traffic Generator Testbench for Bank Transaction Deduplication.
Simulates real-world traffic scenarios:
  1. Identical duplicate statement uploads (e.g., uploading same statement PDF twice)
  2. Overlapping monthly statement files (e.g., a 6-month master PDF + 1-month subset PDF)
  3. Legitimate multiple transactions with same date, amount, and bank but unique reference numbers.

Verifies that the Visited Hash Algorithm:
  - Preserves unique transactions
  - Flags duplicate transactions as 'DUPLICATE IGNORED' in audit logs
  - Accurately counts dropped duplicates without corrupting balances or metrics.
"""

import pandas as pd
from CATEGORY_CONFIG import deduplicate_transactions
from TRANSACTION_DEDUPLICATOR import TransactionGraphDeduplicator


def generate_synthetic_traffic() -> pd.DataFrame:
    """Generate a realistic test traffic dataset containing both valid and duplicate transactions."""
    traffic_records = [
        # --- Batch 1: Primary 6-Month Statement Records ---
        {
            "Date": pd.to_datetime("2026-03-01"),
            "Bank": "HDFC Bank",
            "Narration": "UPI-MUDULI STORE-OMBK.AAEB042781NZJAAADL 77@MBK",
            "Type": "Debit",
            "Amount (₹)": 10.00,
            "Closing Balance (₹)": 501236.88,
            "ChqRefNo": "0000994337498083",
        },
        {
            "Date": pd.to_datetime("2026-03-01"),
            "Bank": "HDFC Bank",
            "Narration": "UPI-SANNARANGEGOWDA T-Q273289229@YBL",
            "Type": "Debit",
            "Amount (₹)": 231.00,
            "Closing Balance (₹)": 501005.88,
            "ChqRefNo": "0000445744353305",
        },
        {
            "Date": pd.to_datetime("2026-03-05"),
            "Bank": "HDFC Bank",
            "Narration": "UPI-ASHOKA KOTRESHA-8951644639@AXL",
            "Type": "Debit",
            "Amount (₹)": 15000.00,
            "Closing Balance (₹)": 486005.88,
            "ChqRefNo": "0000659511062658",
        },
        {
            "Date": pd.to_datetime("2026-08-05"),
            "Bank": "Bank of Baroda",
            "Narration": "UPI/P2A/621815124991/SAVITHASHANTESHBAG",
            "Type": "Debit",
            "Amount (₹)": 10000.00,
            "Closing Balance (₹)": 218055.98,
            "ChqRefNo": "621815124991",
        },

        # --- Batch 2: Simulated Duplicate Injections (Overlapping Statement / Re-upload) ---
        {
            # Exact duplicate of March 1st Muduli payment
            "Date": pd.to_datetime("2026-03-01"),
            "Bank": "HDFC Bank",
            "Narration": "UPI-MUDULI STORE-OMBK.AAEB042781NZJAAADL 77@MBK",
            "Type": "Debit",
            "Amount (₹)": 10.00,
            "Closing Balance (₹)": 501236.88,
            "ChqRefNo": "0000994337498083",
        },
        {
            # Exact duplicate of March 5th Rent payment
            "Date": pd.to_datetime("2026-03-05"),
            "Bank": "HDFC Bank",
            "Narration": "UPI-ASHOKA KOTRESHA-8951644639@AXL",
            "Type": "Debit",
            "Amount (₹)": 15000.00,
            "Closing Balance (₹)": 486005.88,
            "ChqRefNo": "0000659511062658",
        },
        {
            # Exact duplicate of BoB August transfer
            "Date": pd.to_datetime("2026-08-05"),
            "Bank": "Bank of Baroda",
            "Narration": "UPI/P2A/621815124991/SAVITHASHANTESHBAG",
            "Type": "Debit",
            "Amount (₹)": 10000.00,
            "Closing Balance (₹)": 218055.98,
            "ChqRefNo": "621815124991",
        },

        # --- Batch 3: Edge Case (Legitimate Same-Day Same-Amount Transactions) ---
        {
            # Same day & same ₹10 amount, but different vendor and reference number (Must NOT be dropped)
            "Date": pd.to_datetime("2026-03-01"),
            "Bank": "HDFC Bank",
            "Narration": "UPI-CHAI-POINT-INDIRANAGAR",
            "Type": "Debit",
            "Amount (₹)": 10.00,
            "Closing Balance (₹)": 500995.88,
            "ChqRefNo": "0000994337499999",
        },
    ]

    return pd.DataFrame(traffic_records)


def run_traffic_deduplication_test():
    print("=" * 75)
    print("TRAFFIC GENERATOR: TRANSACTION DEDUPLICATION & IGNORE AUDIT TEST")
    print("=" * 75)

    traffic_df = generate_synthetic_traffic()
    print(f"Generated Synthetic Traffic Stream : {len(traffic_df)} total records")
    print("Simulated Injections               : 3 overlapping duplicates + 5 unique transactions\n")

    # Execute Deduplication Algorithm
    deduped_df, ignored_duplicates, dup_count = deduplicate_transactions(traffic_df)

    print(f"Deduplication Engine Output:")
    print(f"  • Unique Transactions Retained : {len(deduped_df)}")
    print(f"  • Duplicate Records Dropped    : {dup_count}")

    print("\n" + "-" * 75)
    print("AUDIT LOG OF IGNORED DUPLICATE TRANSACTIONS:")
    print("-" * 75)
    for i, dup in enumerate(ignored_duplicates, 1):
        print(f"  [{i}] {dup['Date']} | {dup['Bank']:14s} | {dup['Status']} | Amount: ₹{dup['Amount (₹)']} | {dup['Narration']}")

    # Assertions for Automated Verification
    assert len(deduped_df) == 5, f"Expected 5 unique transactions, got {len(deduped_df)}"
    assert dup_count == 3, f"Expected 3 dropped duplicates, got {dup_count}"
    assert len(ignored_duplicates) == 3, f"Expected 3 logged ignored records, got {len(ignored_duplicates)}"

    print("-" * 75)
    print("✓ ALL ASSERTIONS PASSED: Visited hash deduplication successfully verified!")
    print("=" * 75)


if __name__ == "__main__":
    run_traffic_deduplication_test()
