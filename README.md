# 💳 Spending Analysis & Personal Financial Intelligence Platform

> **Author**: Shreyas S Bagi  
> **Target Audience**: Personal Financial Budgeting, House Loan EMI Planning & Family Reporting  
> **Supported Banks**: HDFC Bank (Salary Account), Bank of Baroda (Savings Account), and easily extensible to any bank.

---

## 🎯 Problem Statement & Goal
As an engineer navigating personal finances, budgeting for a **House Loan EMI**, and sharing clear monthly summaries with parents, this tool automates the ingestion of raw bank statement PDFs and text exports. 

It provides:
1. **Automated Multi-Bank Statement Ingestion & Classification**: Drops all PDF statements into `BANK_STATEMENT/`, automatically identifies the bank format, and categorizes every single transaction.
2. **Deterministic Deduplication Engine (Visited Hash Algorithm)**: Safely handles overlapping statements (e.g., uploading a 6-month consolidated statement and single-month statements simultaneously) without duplicating transactions.
3. **Interactive Visual Dashboard for Family Review**: Generates a self-contained, offline-ready HTML dashboard with interactive monthly tabs, category spending breakdowns, weekly spending trends, recurring payment trackers, and instant search.
4. **Audit Trail & High-Value Transaction Isolation**: Flags uncategorized transactions (> ₹500) for budget tuning and provides separate per-bank (`_HDFC.txt`, `_BoB.txt`) and unified processing logs.

---

## ⚠️ Important Note & Duplicate Prevention Algorithm

### **The Overlap / Duplicate Problem**
When uploading bank statements over time, statement periods frequently overlap:
- Example: Uploading `BANK_STATEMENT_HDFC_FEB_TO_JUL.pdf` (6 months) and later adding `BANK_STATEMENT_HDFC_MARCH.pdf` (1 month).
- Without deduplication, March transactions would be counted twice, artificially inflating income and expense metrics.

### **Our Solution: Visited Hash-Set Fingerprinting (Graph-Style Traversal)**
Instead of relying on fragile table heuristics, `CATEGORY_CONFIG.py` runs a generic **deterministic fingerprinting algorithm**:
```
Transaction Fingerprint = Date | Bank | Type | Amount | Ref_No (or Closing_Balance + Normalized_Narration)
```
- Each incoming transaction generates an immutable hash key.
- The engine checks a `visited_fingerprints` set in $O(1)$ time complexity:
  - If **Not Visited**: Adds the transaction to the unified master dataset and marks the key as visited.
  - If **Already Visited**: Drops the duplicate entry and increments the duplicate audit counter.

---

## 🏗️ Project Architecture & Clean Directory Structure

```
BANK/
├── category_rules.json                # Centralized category rules & keywords (JSON format)
├── CATEGORY_CONFIG.py                 # Core classification & deduplication engine
├── TRANSACTION_DEDUPLICATOR.py        # Generic visited-set graph transaction deduplication engine
├── CONSOLIDATED_BANK_STATEMENT_PARSER.py  # Master runner (Scans all banks & aggregates)
├── HDFC_BANK_STATEMENT_PARSER.py      # HDFC Bank specific parser
├── BOB_BANK_STATEMENT_PARSER.py       # Bank of Baroda specific parser
├── HTML_REPORT_GENERATOR.py           # Interactive HTML dashboard generator (Chart.js)
├── .gitignore                         # Protects statements and reports from GitHub
├── BANK_STATEMENT/                    # [LOCAL ONLY] Drop your bank PDFs here
│   ├── BANK_STATEMENT_HDFC_ACC_1990.pdf
│   └── BANK_STATEMENT_BANK_OF_BARODA.pdf
└── Financial_Reports/                 # [LOCAL ONLY] Generated reports & dashboards
    ├── Financial_Dashboard_All_Months.html   # 🌟 Master 6-7 Month Interactive Dashboard
    ├── Processing_Log.txt                    # Consolidated Master Audit Log
    ├── Processing_Log_HDFC.txt               # HDFC Consolidated Audit Log
    ├── Processing_Log_BoB.txt                # Bank of Baroda Consolidated Audit Log
    └── 2026/
        ├── 02-February/
        ├── 03-March/
        ├── 04-April/
        ├── 05-May/
        ├── 06-June/
        ├── 07-July/
        └── 08-August/
            ├── 2026-08_Financial_Summary.html # Interactive Monthly Dashboard
            ├── 2026-08_Financial_Summary.xlsx # 6-Sheet Excel Workbook with Charts
            ├── 2026-08_Financial_Summary.txt  # Plain Text Summary
            ├── 2026-08_Processing_Log.txt     # Combined Month Log
            └── 2026-08_Processing_Log_BoB.txt # Bank-Specific Log
```

---

## 🚀 How to Run

### **1. Install Dependencies**
```powershell
pip install pandas openpyxl xlsxwriter pdfplumber
```

### **2. Run Consolidated Parser (Recommended)**
Scans `BANK_STATEMENT/`, deduplicates overlapping data, and generates all consolidated & month-wise reports:
```powershell
python CONSOLIDATED_BANK_STATEMENT_PARSER.py
```

### **3. Open the Interactive Family Dashboard**
Simply double click or open in browser:
- `Financial_Reports/Financial_Dashboard_All_Months.html`

---

## 🏷️ Category Rules & Customization

You can easily customize or add merchant keywords directly in **`category_rules.json`**:
```json
{
  "categories": [
    {
      "name": "House Maintenance",
      "keywords": ["VAASTUDEW", "MAINTENANCE", "KOTRESHA"]
    },
    {
      "name": "Parents / Grandparents / Siblings Spending",
      "keywords": ["LAKSHMIPATHIG", "UPI-LAKSHMIPATHIG"]
    },
    {
      "name": "Food & Snacks",
      "keywords": ["HUNGERBOX", "MOULA", "UDUPI", "ZOMATO", "SWIGGY"]
    }
  ]
}
```

---

## 🛡️ Privacy & Git Safeguards
All raw statements (`BANK_STATEMENT/`) and personal financial reports (`Financial_Reports/`, `*.pdf`, `*.xlsx`) are excluded in `.gitignore` and kept strictly local on your machine.

