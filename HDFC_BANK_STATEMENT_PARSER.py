"""
HDFC_BANK_STATEMENT_PARSER.py

Parses an HDFC Bank statement PDF (table format: Date | Narration | Chq./Ref.No. |
Value Dt | Withdrawal Amt. | Deposit Amt. | Closing Balance) and produces a single
Excel workbooks with categorised transactions, monthly summaries, category
breakdowns, weekly spending, recurring-payment detection and charts. Reports are
placed in simple year/month folders, alongside a plain-text summary.

Usage:
    pip install pandas openpyxl xlsxwriter pdfplumber
    python HDFC_BANK_STATEMENT_PARSER.py
    python HDFC_BANK_STATEMENT_PARSER.py --input BANK_STATEMENT.pdf BANK_STATEMENT.txt --output-dir Financial_Reports
"""

import argparse
import re
from datetime import datetime, time
from pathlib import Path

import pandas as pd
import pdfplumber

from HTML_REPORT_GENERATOR import generate_html_dashboard

# -----------------------------
# 1. Category rules (ordered by priority - first match wins)
# -----------------------------

CATEGORY_RULES = [
    ("Salary / Income", [
        "IBMINDIAPRIVATELI", "IBM INDIA PRIVATE", "IBMINDIAPRIVATE", "IBM INDIA", "SALARY", "PAYROLL",
    ]),
    ("Rent", [
        "UPI-ASHOKA", "ASHOKA KOTRESHA", "SADHANA AK", " RENT ",
    ]),
    ("House Maintenance", [
        "KOTRESHA", "HOUSE_MAINT", "MAINTENANCE", "ICIC0000106-VAASTUDEW", "VAASTUDEW",
        "VAASTUDEW FLOWER", "DEW FLOWER",
    ]),
    ("Self / Family Transfer", [
        "SHREYAS S BAGI", "SHREYASSBAGI", "SHANTESH B BAGI", "SHANTESHBBAGI", "SHANTESH BAGI", "SHANTESH",
        "SAVITHA SHANTESH", "SAVITHA", "SAHANA SHANTESH", "SAHANA",
        "NAGARATHNAV MUNDASA", "NAGARATHNAV", "MUNDASA",
    ]),
    ("Parents / Grandparents / Siblings Spending", [
        "LAKSHMIPATHIG", "UPI-LAKSHMIPATHIG",
    ]),
    ("Tax Refund / Tax Payment", [
        "ITDTAX REFUND", "TAX REFUND", "DIRECTTAX", "DTAX-DIRECTTAX",
    ]),
    ("Investments", [
        "GROWW", "GROWW INVEST", "GROWW.BRK", "UTKARSH SMALL FINANC", "MUTUAL FUND",
    ]),
    ("Donations / Religious", [
        "SARVEDYNABASAYYA", "VEERANJANEYARELIGIO", "VEERANJANEYA", "RELIGIO", "SEVA",
    ]),
    ("Bank Charges / Interest", [
        "INTEREST PAID", "IB BILLPAY", "HDFC BANK LIMITED", "CHARGES", " FEE ", "NEFT CHARGES",
    ]),
    ("Groceries", [
        "SANNARANGEGOWDA", "APOORVAFRUITS",
    ]),
    ("Tea and Snacks", [
        "OMKARNANDINIMILKP", "UPI-MRSRINIVAS", "MRSRINIVAS",
    ]),
    ("Food & Snacks", [
        "HUNGERBOX", "MOULA", "UPI-MOULA", "UDUPI", "NEWUDUPI", "UDUPI GARDEN", "GARDEN", "EATGOOD",
        "GURUPRASAD", "VEG-PAYTM", "PAAKASHALA", "RAMESHWARAM", "THERAMESHWARAM",
        "COFFEENIVASA", "MADRASCOFFEE", "DAALCHINI", "NALABHIMAPAKAM", "CHICKEN WONDER",
        "SOMASHEKHAR", "UPI-SOMASHEKHAR",
        "KABULI", "MUDULI-BHARATPE90727093430", "MUDULI-BHARATPE", "MUDULI",
        "VIHAANFAMILY", "RESTAU",
        "FAMILYKITCHEN", "KAPOORSCHAAT", "BHANDA",
        "SHREEENTERPRISES",
        "RESTAURANT", "HOTEL", "ZOMATO",
        "SWIGGY", "MCDONALDS", "DOMINOS", "KITCHEN", "BAKERY", "MAYURABAKERYAND",
        "SWEET", "BIGMISHRASWEET",
        "BIRIYANI", "BIRYANI", "COFFEE", "CAFE", "TIFFIN", "MESS", "CATERERS",
        "FOOD", "DHABA", "BHAVAN", "MART", "HYPER MART", "VEGETABLE",
        "FRUITS", "VEG-", "PALACE", "SRISAIPALACE", "HOTELASHRAYA", "UPACHA",
        "APOLLO PHARMAC",
    ]),
    ("Petrol / Fuel", [
        "THEFUELHUB", "BABULALKGUPTA", "SATHYASAIFILLINGS", "FILLINGS", "PETROL", "FUEL",
    ]),
    ("Transport", [
        "BMTC", "UPI-BMTCBUS", "BMRCL", "NCMC", "METRO", "NWKRTC", "UBER", "RAPIDO", "OLA",
        "BAGMANE",
    ]),
    ("General UPI / Shopping", [
        "AMAZON", "FLIPKART", "BLINKIT", "MYNTRA", "DECATHLON", "RELIANCE RETAIL",
        "JIOFIBER",
    ]),
    ("Copilot AI", [
        "AUTOPAY-GOOGLEPLAY-PLAYSTORE", "AUTOPAY-GOOGLE",
    ]),
    ("Credit Bill Payment", [
        "CRED",
    ]),
    ("Entertainment / Subscriptions", [
        "GOOGLE PLAY", "PLAYSTORE", "PVR", "BIGTREE", "BOOKMYSHOW",
        "PRIME VIDEO", "PRIMEVIDEO", "AUTOPAY-PRIMEVIDEO", "NETFLIX", "SPOTIFY",
        "TAGMANGO", "GEEKSFORGEEKS",
        "HABUILD",
    ]),
    ("Utilities / Recharge", [
        "AIRTEL", "JIO", "VODAFONE", "RECHARGE", "ELECTRICITY", "GAS",
    ]),
    ("Health / Medical", [
        "PHARMACY", "MEDICAL", "HOSPITAL", "CLINIC", "APOLLO", "APOLLOPHARMACY",
    ]),
    ("Swimming", [
        "ZEESWIMACADEMY", "SWIM ACADEMY", "SWIMMING FEES",
    ]),
    ("Education / Fees", [
        "SCHOOL", "TUITION", "COURSE", "IITMADRAS", "IIT MADRAS", "NPTEL",
    ]),
]

TRANSPORT_NARRATION_PATTERNS = [
    r"\bKA\d{2}[A-Z]{1,2}\d{4}\b",
]
MORNING_TRANSPORT_START = time(8, 0)
MORNING_TRANSPORT_END = time(11, 0)
DAILY_UPI_TRANSPORT_MIN_AMOUNT = 40.0
DAILY_UPI_TRANSPORT_MAX_AMOUNT = 120.0


# -----------------------------
# 2. Helpers
# -----------------------------

def parse_date(date_str: str) -> datetime:
    """Accept HDFC statement dates in DD/MM/YY or DD/MM/YYYY format."""
    value = date_str.strip()
    for date_format in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    raise ValueError(f"Unsupported statement date: {value}")


def clean_amount(val) -> float:
    if val is None:
        return 0.0
    val = str(val).strip().replace(",", "")
    if val == "":
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0


def week_number_in_month(dt: datetime) -> int:
    # Week 1: days 1-7, Week 2: 8-14, Week 3: 15-21, Week 4: 22-28, Week 5: 29-31
    return (dt.day - 1) // 7 + 1


def detect_type(withdrawal: float, deposit: float) -> str:
    if withdrawal > 0 and deposit == 0:
        return "Debit"
    if deposit > 0 and withdrawal == 0:
        return "Credit"
    return "Debit" if withdrawal >= deposit else "Credit"


def extract_time_from_narration(narration: str) -> time | None:
    """Extract a transaction time when the statement includes one in narration."""
    value = narration.upper()
    match = re.search(r"\b(0?[1-9]|1[0-2])(?::([0-5]\d))?\s*(AM|PM)\b", value)
    if match:
        hour = int(match.group(1)) % 12
        if match.group(3) == "PM":
            hour += 12
        return time(hour, int(match.group(2) or 0))

    match = re.search(r"\b([01]\d|2[0-3]):([0-5]\d)\b", value)
    if match:
        return time(int(match.group(1)), int(match.group(2)))
    return None


def classify_category(narration: str, transaction_time: time | None = None) -> str:
    n = narration.upper()
    if any(re.search(pattern, n) for pattern in TRANSPORT_NARRATION_PATTERNS):
        return "Transport"
    if (
        re.search(r"(?:^|[\s:/-])UPI-", n)
        and transaction_time is not None
        and MORNING_TRANSPORT_START <= transaction_time < MORNING_TRANSPORT_END
    ):
        return "Transport"
    for category, keywords in CATEGORY_RULES:
        if any(kw in n for kw in keywords):
            return category
    if "NEFT CR" in n or "CREDIT" in n or " CR " in n:
        return "Salary / Income"
    if "NEFT DR" in n:
        return "General UPI / Shopping"
    return "Uncategorized"


def apply_daily_transport_heuristic(df: pd.DataFrame) -> pd.DataFrame:
    """Classify the first unknown UPI debit in the daily transport fare range."""
    if df.empty:
        return df

    result = df.copy()
    daily_candidates = result[
        (result["Category"] == "Uncategorized")
        & (result["Type"] == "Debit")
        & result["Narration"].str.contains(r"\bUPI(?:-|/|$)", case=False, na=False, regex=True)
        & result["Amount (₹)"].between(
            DAILY_UPI_TRANSPORT_MIN_AMOUNT,
            DAILY_UPI_TRANSPORT_MAX_AMOUNT,
            inclusive="both",
        )
    ]
    first_candidate_indices = daily_candidates.groupby(
        result.loc[daily_candidates.index, "Date"], sort=False
    ).head(1).index
    result.loc[first_candidate_indices, "Category"] = "Transport"
    return result


def extract_merchant_key(narration: str) -> str:
    """Collapse a narration into a recurring-merchant key for detecting repeats."""
    n = narration.upper()
    n = re.sub(r"^UPI-", "", n)
    n = re.sub(r"^NEFT (CR|DR)-", "", n)
    n = re.sub(r"^REV-UPI-", "", n)
    token = re.split(r"[@\-]", n)[0]
    token = re.sub(r"\s+", " ", token).strip()
    return token or n[:30]


# -----------------------------
# 3. Extract transactions from the PDF
# -----------------------------

def extract_transactions_from_pdf(pdf_path: str) -> pd.DataFrame:
    """Extract transactions from HDFC statement PDF with precise coordinate alignment."""
    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Extract words in transaction table area (top >= 235 and top <= 760)
            words = [w for w in page.extract_words() if 235 <= w["top"] <= 760]
            if not words:
                continue

            # Filter out footer artifacts
            words = [
                w for w in words
                if not any(k in w["text"] for k in ("GeneratedBy:", "DrCount", "CrCount"))
            ]

            # Anchor: Date words in column 0 (x < 63.5)
            date_words = [
                w for w in words
                if w["x0"] < 63.5 and re.match(r"^\d{2}/\d{2}/\d{2}$", w["text"])
            ]
            date_words.sort(key=lambda w: w["top"])

            narration_words = [w for w in words if 60.0 <= w["x0"] < 237.5]
            narration_words.sort(key=lambda w: (w["top"], w["x0"]))

            chq_words = [w for w in words if 237.5 <= w["x0"] < 333.0]
            val_words = [
                w for w in words
                if 333.0 <= w["x0"] < 370.0 and re.match(r"^\d{2}/\d{2}/\d{2}$", w["text"])
            ]
            wth_words = [w for w in words if 370.0 <= w["x0"] < 442.5]
            dep_words = [w for w in words if 442.5 <= w["x0"] < 515.6]
            cls_words = [w for w in words if 515.6 <= w["x0"]]

            # Carryover narration before the first date on this page belongs to the previous transaction
            if date_words:
                first_date_top = date_words[0]["top"]
                pre_words = [w for w in narration_words if w["top"] < first_date_top - 3]
                if pre_words and rows:
                    rows[-1]["Narration"] += " " + " ".join(w["text"] for w in pre_words)
            elif narration_words and rows:
                rows[-1]["Narration"] += " " + " ".join(w["text"] for w in narration_words)

            for i, dw in enumerate(date_words):
                top_min = dw["top"] - 3
                top_max = date_words[i + 1]["top"] - 3 if i + 1 < len(date_words) else 9999.0

                tx_nar_words = [w for w in narration_words if top_min <= w["top"] < top_max]
                tx_nar = " ".join(w["text"] for w in tx_nar_words).strip()

                tx_chq_words = [w for w in chq_words if top_min <= w["top"] < top_max]
                tx_chq = " ".join(w["text"] for w in tx_chq_words).strip()

                tx_val_words = [w for w in val_words if abs(w["top"] - dw["top"]) < 6]
                tx_val = tx_val_words[0]["text"] if tx_val_words else ""

                tx_wth_words = [w for w in wth_words if abs(w["top"] - dw["top"]) < 6]
                tx_wth = tx_wth_words[0]["text"] if tx_wth_words else "0.00"

                tx_dep_words = [w for w in dep_words if abs(w["top"] - dw["top"]) < 6]
                tx_dep = tx_dep_words[0]["text"] if tx_dep_words else "0.00"

                tx_cls_words = [w for w in cls_words if abs(w["top"] - dw["top"]) < 6]
                tx_cls = tx_cls_words[0]["text"] if tx_cls_words else "0.00"

                amount_debit = clean_amount(tx_wth)
                amount_credit = clean_amount(tx_dep)
                if amount_debit <= 0 and amount_credit <= 0:
                    continue

                tx_type = detect_type(amount_debit, amount_credit)
                amount = amount_debit if tx_type == "Debit" else amount_credit
                if amount <= 0:
                    continue

                try:
                    dt = parse_date(dw["text"])
                except ValueError:
                    continue

                rows.append({
                    "Date": dt,
                    "Month": dt.strftime("%B"),
                    "MonthYear": dt.strftime("%b-%Y"),
                    "WeekNumberInMonth": week_number_in_month(dt),
                    "Narration": tx_nar,
                    "Category": classify_category(
                        tx_nar, extract_time_from_narration(tx_nar)
                    ),
                    "Type": tx_type,
                    "Amount (₹)": amount,
                    "Closing Balance (₹)": clean_amount(tx_cls),
                    "ChqRefNo": tx_chq,
                })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df[df["Amount (₹)"] > 0]
        df.sort_values("Date", inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


def extract_transactions_from_txt(txt_path: str) -> pd.DataFrame:
    """Extract common HDFC text exports with pipe/tab-separated transaction rows."""
    rows = []
    for raw_line in Path(txt_path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not re.match(r"\d{2}/\d{2}/\d{2}", line):
            continue
        columns = re.split(r"\s*(?:\||\t)\s*", line)
        if len(columns) < 7:
            continue

        date_str, narration, chq_ref, _, withdrawal, deposit, closing = columns[:7]
        try:
            dt = parse_date(date_str)
        except ValueError:
            continue

        debit = clean_amount(withdrawal)
        credit = clean_amount(deposit)
        if debit <= 0 and credit <= 0:
            continue
        tx_type = detect_type(debit, credit)
        amount = debit if tx_type == "Debit" else credit
        if amount <= 0:
            continue

        rows.append({
            "Date": dt,
            "Month": dt.strftime("%B"),
            "MonthYear": dt.strftime("%b-%Y"),
            "WeekNumberInMonth": week_number_in_month(dt),
            "Narration": narration.strip(),
            "Category": classify_category(
                narration, extract_time_from_narration(narration)
            ),
            "Type": tx_type,
            "Amount (₹)": amount,
            "Closing Balance (₹)": clean_amount(closing),
            "ChqRefNo": chq_ref.strip(),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df[df["Amount (₹)"] > 0]
        df.sort_values("Date", inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


def extract_transactions(input_path: str) -> pd.DataFrame:
    """Read an HDFC statement from a PDF or a pipe/tab-separated text export."""
    suffix = Path(input_path).suffix.lower()
    if suffix == ".pdf":
        return extract_transactions_from_pdf(input_path)
    if suffix == ".txt":
        return extract_transactions_from_txt(input_path)
    raise ValueError(f"Unsupported input format '{suffix}'. Use .pdf or .txt files.")


def collect_statement_files(input_paths: str | list[str]) -> list[Path]:
    """Expand statement folders into sorted PDF and text statement files."""
    if isinstance(input_paths, str):
        input_paths = [input_paths]

    statement_files = []
    for input_path in input_paths:
        path = Path(input_path)
        if path.is_dir():
            statement_files.extend(
                candidate for candidate in sorted(path.iterdir())
                if candidate.is_file() and candidate.suffix.lower() in {".pdf", ".txt"}
            )
        elif path.is_file() and path.suffix.lower() in {".pdf", ".txt"}:
            statement_files.append(path)
        else:
            print(f"Skipping unavailable or unsupported input: {path}")
    return statement_files


# -----------------------------
# 4. Summary builders
# -----------------------------

def month_sort_key(my: str) -> datetime:
    return datetime.strptime(my, "%b-%Y")


def build_monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    debits = df[df["Type"] == "Debit"].groupby("MonthYear")["Amount (₹)"].sum()
    credits = df[df["Type"] == "Credit"].groupby("MonthYear")["Amount (₹)"].sum()
    months = sorted(set(df["MonthYear"]), key=month_sort_key)

    data = []
    for m in months:
        d = round(float(debits.get(m, 0.0)), 2)
        c = round(float(credits.get(m, 0.0)), 2)
        data.append({
            "Month": m,
            "Total Debits (₹)": d,
            "Total Credits (₹)": c,
            "Net Change (₹)": round(c - d, 2),
        })
    return pd.DataFrame(data)


def build_category_by_month(df: pd.DataFrame) -> pd.DataFrame:
    months = sorted(set(df["MonthYear"]), key=month_sort_key)
    categories = sorted(set(df["Category"]))
    rows = []
    for m in months:
        for cat in categories:
            sub = df[(df["MonthYear"] == m) & (df["Category"] == cat)]
            debit_total = sub[sub["Type"] == "Debit"]["Amount (₹)"].sum()
            credit_total = sub[sub["Type"] == "Credit"]["Amount (₹)"].sum()
            if debit_total == 0 and credit_total == 0:
                continue
            rows.append({
                "Month": m,
                "Category": cat,
                "Debit Total (₹)": round(float(debit_total), 2),
                "Credit Total (₹)": round(float(credit_total), 2),
            })
    return pd.DataFrame(rows)


def build_weekly_spending(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["Type"] == "Debit"]
    grp = sub.groupby(["MonthYear", "WeekNumberInMonth"])["Amount (₹)"].sum().reset_index()
    grp.rename(columns={"Amount (₹)": "Weekly Debit Total (₹)"}, inplace=True)
    grp["_sort"] = grp["MonthYear"].apply(month_sort_key)
    grp.sort_values(["_sort", "WeekNumberInMonth"], inplace=True)
    return grp.drop(columns="_sort").reset_index(drop=True)


def build_recurring_payments(df: pd.DataFrame, min_count: int = 4) -> pd.DataFrame:
    tmp = df[df["Type"] == "Debit"].copy()
    tmp["MerchantKey"] = tmp["Narration"].apply(extract_merchant_key)
    counts = tmp.groupby("MerchantKey")["Amount (₹)"].agg(["count", "sum"]).reset_index()
    counts = counts[counts["count"] >= min_count].copy()
    counts.rename(columns={
        "MerchantKey": "NarrationKey",
        "count": "Count",
        "sum": "Total Debit Amount (₹)",
    }, inplace=True)
    counts["Total Debit Amount (₹)"] = counts["Total Debit Amount (₹)"].round(2)
    return counts.sort_values("Total Debit Amount (₹)", ascending=False).reset_index(drop=True)


def build_overview_sheet(df: pd.DataFrame, monthly_summary: pd.DataFrame) -> pd.DataFrame:
    categories = sorted(df["Category"].unique())
    rows = []
    for category in categories:
        category_rows = df[df["Category"] == category]
        debit = float(category_rows.loc[category_rows["Type"] == "Debit", "Amount (₹)"].sum())
        credit = float(category_rows.loc[category_rows["Type"] == "Credit", "Amount (₹)"].sum())
        rows.append({
            "Category": category,
            "Debit Total (Rs.)": round(debit, 2),
            "Credit Total (Rs.)": round(credit, 2),
            "Net Change (Rs.)": round(credit - debit, 2),
        })

    overview = pd.DataFrame(rows)
    total_debit = round(float(overview["Debit Total (Rs.)"].sum()), 2)
    total_credit = round(float(overview["Credit Total (Rs.)"].sum()), 2)
    overview.loc[len(overview)] = {
        "Category": "Total",
        "Debit Total (Rs.)": total_debit,
        "Credit Total (Rs.)": total_credit,
        "Net Change (Rs.)": round(total_credit - total_debit, 2),
    }
    return overview


# -----------------------------
# 5. Write month-wise reports with charts
# -----------------------------

def write_monthly_report(df: pd.DataFrame, output_path: Path, summary_path: Path) -> None:
    monthly_summary = build_monthly_summary(df)
    category_by_month = build_category_by_month(df)
    weekly_spending = build_weekly_spending(df)
    recurring = build_recurring_payments(df)
    overview = build_overview_sheet(df, monthly_summary)

    df_out = df.copy()
    df_out["Date"] = df_out["Date"].dt.strftime("%d-%m-%Y")

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        overview.to_excel(writer, sheet_name="Overview", index=False)
        df_out.to_excel(writer, sheet_name="Transactions", index=False)
        monthly_summary.to_excel(writer, sheet_name="Monthly_Summary", index=False)
        category_by_month.to_excel(writer, sheet_name="Category_By_Month", index=False)
        weekly_spending.to_excel(writer, sheet_name="Weekly_Spending", index=False)
        recurring.to_excel(writer, sheet_name="Recurring_Payments", index=False)

        workbook = writer.book

        # Pie chart: category-wise debit spending for this month.
        overall_cat = df[df["Type"] == "Debit"].groupby("Category")["Amount (₹)"].sum().reset_index()
        overall_cat.to_excel(writer, sheet_name="Category_Pie_Data", index=False)
        pie_sheet = writer.sheets["Category_Pie_Data"]
        if len(overall_cat) > 0:
            chart_pie = workbook.add_chart({"type": "pie"})
            chart_pie.add_series({
                "name": "Spending by Category",
                "categories": ["Category_Pie_Data", 1, 0, len(overall_cat), 0],
                "values": ["Category_Pie_Data", 1, 1, len(overall_cat), 1],
            })
            chart_pie.set_title({"name": "Spending by Category (Debits)"})
            pie_sheet.insert_chart("D2", chart_pie)

        # Combined columns and line: monthly debits, credits, and net change.
        if len(monthly_summary) > 0:
            ms_sheet = writer.sheets["Monthly_Summary"]
            chart_col = workbook.add_chart({"type": "column"})
            chart_col.add_series({
                "name": "Total Debits (₹)",
                "categories": ["Monthly_Summary", 1, 0, len(monthly_summary), 0],
                "values": ["Monthly_Summary", 1, 1, len(monthly_summary), 1],
            })
            chart_col.add_series({
                "name": "Total Credits (₹)",
                "categories": ["Monthly_Summary", 1, 0, len(monthly_summary), 0],
                "values": ["Monthly_Summary", 1, 2, len(monthly_summary), 2],
            })
            chart_line = workbook.add_chart({"type": "line"})
            chart_line.add_series({
                "name": "Net Change (₹)",
                "categories": ["Monthly_Summary", 1, 0, len(monthly_summary), 0],
                "values": ["Monthly_Summary", 1, 3, len(monthly_summary), 3],
            })
            chart_col.combine(chart_line)
            chart_col.set_title({"name": "Monthly Debits, Credits, and Net Change"})
            chart_col.set_x_axis({"name": "Month"})
            chart_col.set_y_axis({"name": "Rs."})
            ms_sheet.insert_chart("G2", chart_col)

        # Line chart: weekly spending pattern
        if len(weekly_spending) > 0:
            ws_sheet = writer.sheets["Weekly_Spending"]
            chart_line = workbook.add_chart({"type": "line"})
            chart_line.add_series({
                "name": "Weekly Debit Total (₹)",
                "values": ["Weekly_Spending", 1, 2, len(weekly_spending), 2],
            })
            chart_line.set_title({"name": "Weekly Spending Pattern (Debits)"})
            chart_line.set_y_axis({"name": "Rs."})
            ws_sheet.insert_chart("F2", chart_line)

    summary_path.write_text(
        "HDFC Bank Statement - Category-wise Financial Summary\n" + ("=" * 55) + "\n" +
        overview.to_csv(index=False, sep="\t"),
        encoding="utf-8",
    )


def format_ascii_table(df: pd.DataFrame, align_map: dict[str, str] | None = None) -> str:
    """Format DataFrame as a clean, properly-aligned text table with left-aligned text."""
    if df.empty:
        return "None"
    align_map = align_map or {}
    str_df = df.copy()
    for col in str_df.columns:
        str_df[col] = str_df[col].astype(str)

    cols = list(str_df.columns)
    widths = {c: max(len(c), str_df[c].map(len).max()) for c in cols}

    header_parts = [
        c.ljust(widths[c]) if align_map.get(c, "left") == "left" else c.rjust(widths[c])
        for c in cols
    ]
    sep_parts = ["-" * widths[c] for c in cols]
    header = "  ".join(header_parts)
    sep = "  ".join(sep_parts)

    lines = [header, sep]
    for _, row in str_df.iterrows():
        row_parts = [
            row[c].ljust(widths[c]) if align_map.get(c, "left") == "left" else row[c].rjust(widths[c])
            for c in cols
        ]
        lines.append("  ".join(row_parts))
    return "\n".join(lines)


def build_category_breakdown_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build a formatted category summary table with transaction count and amounts."""
    rows = []
    categories = sorted(df["Category"].unique())
    for cat in categories:
        sub = df[df["Category"] == cat]
        debit = sub[sub["Type"] == "Debit"]["Amount (₹)"].sum()
        credit = sub[sub["Type"] == "Credit"]["Amount (₹)"].sum()
        rows.append({
            "Category": cat,
            "Count": len(sub),
            "Debit Amount (₹)": f"{debit:,.2f}",
            "Credit Amount (₹)": f"{credit:,.2f}",
            "Net (₹)": f"{(credit - debit):,.2f}",
        })
    total_debit = df[df["Type"] == "Debit"]["Amount (₹)"].sum()
    total_credit = df[df["Type"] == "Credit"]["Amount (₹)"].sum()
    rows.append({
        "Category": "TOTAL",
        "Count": len(df),
        "Debit Amount (₹)": f"{total_debit:,.2f}",
        "Credit Amount (₹)": f"{total_credit:,.2f}",
        "Net (₹)": f"{(total_credit - total_debit):,.2f}",
    })
    return pd.DataFrame(rows)


def write_monthly_processing_log(df: pd.DataFrame, log_path: Path) -> None:
    """Write a readable audit log for every transaction processed in one month."""
    log_df = df[["Date", "Narration", "Type", "Amount (₹)", "Category"]].copy()
    log_df["Date"] = log_df["Date"].dt.strftime("%d-%m-%Y")
    log_df["Amount (₹)"] = log_df["Amount (₹)"].map(lambda v: f"{v:,.2f}")
    transport_df = log_df[log_df["Category"] == "Transport"]

    # Uncategorized transactions with amount > 500
    uncategorized_high_mask = (df["Category"] == "Uncategorized") & (df["Amount (₹)"] > 500)
    uncategorized_high_df = log_df[uncategorized_high_mask]

    category_summary = build_category_breakdown_table(df)

    cat_align = {
        "Category": "left",
        "Count": "right",
        "Debit Amount (₹)": "right",
        "Credit Amount (₹)": "right",
        "Net (₹)": "right",
    }
    tx_align = {
        "Date": "left",
        "Narration": "left",
        "Type": "left",
        "Amount (₹)": "right",
        "Category": "left",
    }

    sections = [
        f"HDFC BANK STATEMENT PROCESSING LOG - {df['MonthYear'].iloc[0]}",
        "=" * 70,
        f"Transactions processed: {len(df)}",
        f"Transport transactions categorized: {len(transport_df)}",
        f"Uncategorized transactions (> ₹500 - Needs Classification): {len(uncategorized_high_df)}",
        "",
        "Category totals (count and amount breakdown):",
        format_ascii_table(category_summary, cat_align),
        "",
        "Uncategorized transactions (> ₹500 - Needs Classification):",
        format_ascii_table(uncategorized_high_df, tx_align),
        "",
        "Transport transactions:",
        format_ascii_table(transport_df, tx_align),
        "",
        "All processed transactions:",
        format_ascii_table(log_df, tx_align),
    ]
    log_path.write_text("\n".join(sections) + "\n", encoding="utf-8")


def write_all_processing_log(df: pd.DataFrame, log_path: Path) -> None:
    """Write a consolidated audit log for all transactions across all months/uploads."""
    log_df = df[["Date", "Narration", "Type", "Amount (₹)", "Category"]].copy()
    log_df["Date"] = log_df["Date"].dt.strftime("%d-%m-%Y")
    log_df["Amount (₹)"] = log_df["Amount (₹)"].map(lambda v: f"{v:,.2f}")
    transport_df = log_df[log_df["Category"] == "Transport"]

    # Uncategorized transactions with amount > 500 across all months
    uncategorized_high_mask = (df["Category"] == "Uncategorized") & (df["Amount (₹)"] > 500)
    uncategorized_high_df = log_df[uncategorized_high_mask]

    category_summary = build_category_breakdown_table(df)

    cat_align = {
        "Category": "left",
        "Count": "right",
        "Debit Amount (₹)": "right",
        "Credit Amount (₹)": "right",
        "Net (₹)": "right",
    }
    tx_align = {
        "Date": "left",
        "Narration": "left",
        "Type": "left",
        "Amount (₹)": "right",
        "Category": "left",
    }

    min_date = df["Date"].min().strftime("%d-%m-%Y") if not df.empty else "N/A"
    max_date = df["Date"].max().strftime("%d-%m-%Y") if not df.empty else "N/A"
    months_list = ", ".join(sorted(set(df["MonthYear"]), key=month_sort_key))

    # Month-wise breakdown table
    month_summary = []
    for my, mdf in df.groupby("MonthYear", sort=False):
        debits = mdf[mdf["Type"] == "Debit"]["Amount (₹)"].sum()
        credits = mdf[mdf["Type"] == "Credit"]["Amount (₹)"].sum()
        month_summary.append(f"  • {my:10s}: {len(mdf):4d} transactions | Debits: Rs. {debits:12,.2f} | Credits: Rs. {credits:12,.2f}")

    sections = [
        "======================================================================",
        "HDFC BANK STATEMENT CONSOLIDATED PROCESSING LOG (ALL MONTHS)",
        "======================================================================",
        f"Date Range: {min_date} to {max_date}",
        f"Months Included: {months_list}",
        f"Total Transactions Processed: {len(df)}",
        f"Total Transport Transactions: {len(transport_df)}",
        f"Total Uncategorized (> ₹500 - Needs Classification): {len(uncategorized_high_df)}",
        "",
        "Month-by-Month Summary:",
        "\n".join(month_summary),
        "",
        "Overall Category Totals (Count and Amount Breakdown):",
        format_ascii_table(category_summary, cat_align),
        "",
        "Uncategorized Transactions (> ₹500 - Needs Classification) (All Months):",
        format_ascii_table(uncategorized_high_df, tx_align),
        "",
        "Transport Transactions Audit (All Months):",
        format_ascii_table(transport_df, tx_align),
        "",
        "All Processed Transactions (All Months):",
        format_ascii_table(log_df, tx_align),
        "",
        "======================================================================",
        "End of Consolidated Processing Log",
        "======================================================================",
    ]
    log_path.write_text("\n".join(sections) + "\n", encoding="utf-8")


def write_execution_log(
    log_path: Path,
    input_files: list[Path],
    df: pd.DataFrame,
    heuristic_count: int,
    generated_files: list[Path],
    status: str = "SUCCESS",
) -> None:
    """Dump a comprehensive timestamped execution log to HDFC_BANK_STATEMENT_PARSER.log."""
    timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    min_date = df["Date"].min().strftime("%d-%m-%Y") if not df.empty else "N/A"
    max_date = df["Date"].max().strftime("%d-%m-%Y") if not df.empty else "N/A"
    months_list = ", ".join(sorted(set(df["MonthYear"]), key=month_sort_key)) if not df.empty else "N/A"
    category_counts = df["Category"].value_counts().sort_index() if not df.empty else pd.Series(dtype=int)

    file_list_str = "\n".join(f"  ✓ {p}" for p in generated_files)
    inputs_str = "\n".join(f"  • {p}" for p in input_files)

    category_lines = []
    for cat, count in category_counts.items():
        sub = df[df["Category"] == cat]
        debit_sum = sub[sub["Type"] == "Debit"]["Amount (₹)"].sum()
        credit_sum = sub[sub["Type"] == "Credit"]["Amount (₹)"].sum()
        category_lines.append(f"  - {cat:30s}: {count:4d} txns | Debit: Rs. {debit_sum:10,.2f} | Credit: Rs. {credit_sum:10,.2f}")

    log_entry = [
        "=" * 80,
        "HDFC BANK STATEMENT PARSER - EXECUTION RUN LOG",
        "=" * 80,
        f"Timestamp         : {timestamp}",
        f"Status            : {status}",
        f"Script File       : HDFC_BANK_STATEMENT_PARSER.py",
        f"Working Directory : {Path.cwd()}",
        "",
        "INPUT STATEMENT(S):",
        inputs_str,
        "",
        "PROCESSING SUMMARY:",
        f"  • Date Span                     : {min_date} to {max_date}",
        f"  • Months Covered ({df['MonthYear'].nunique()} months)     : {months_list}",
        f"  • Total Transactions Extracted  : {len(df)}",
        f"  • Total Debits Sum (Rs.)        : {df[df['Type'] == 'Debit']['Amount (₹)'].sum():,.2f}",
        f"  • Total Credits Sum (Rs.)       : {df[df['Type'] == 'Credit']['Amount (₹)'].sum():,.2f}",
        f"  • Transport Heuristic Matches   : {heuristic_count} transactions reclassified",
        "",
        "CATEGORY BREAKDOWN (Transaction Count & Amount):",
        "\n".join(category_lines),
        "",
        "GENERATED REPORT FILES:",
        file_list_str,
        "",
        "=" * 80,
        f"Execution completed at {timestamp}",
        "=" * 80,
        "\n",
    ]

    # Append to existing log or create new
    content = "\n".join(log_entry)
    if log_path.exists():
        existing_text = log_path.read_text(encoding="utf-8", errors="replace")
        log_path.write_text(existing_text + "\n" + content, encoding="utf-8")
    else:
        log_path.write_text(content, encoding="utf-8")
    print(f"Logged execution to: {log_path}")


def write_reports_by_month(df: pd.DataFrame, output_dir: str) -> list[Path]:
    """Create YYYY/MM-Month folders containing an Excel workbook, text summary, and HTML dashboard."""
    generated_reports = []
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Consolidated processing log for all months
    all_months_log = output_path / "Processing_Log.txt"
    write_all_processing_log(df.copy(), all_months_log)
    generated_reports.append(all_months_log)
    print(f"Created (All Months): {all_months_log}")

    # Consolidated interactive HTML dashboard for all months (Master Family Dashboard)
    all_months_html = output_path / "Financial_Dashboard_All_Months.html"
    generate_html_dashboard(
        df=df.copy(),
        output_html_path=all_months_html,
        title="HDFC Bank Statement - Comprehensive Financial Dashboard (Feb - Jul 2026)",
        subtitle="Consolidated 6-Month Interactive Spending & Income Overview",
    )
    generated_reports.append(all_months_html)
    print(f"Created (All Months HTML Dashboard): {all_months_html}")

    for month_year, month_df in df.groupby("MonthYear", sort=False):
        report_date = month_sort_key(str(month_year))
        folder = output_path / str(report_date.year) / report_date.strftime("%m-%B")
        folder.mkdir(parents=True, exist_ok=True)
        base_name = f"{report_date:%Y-%m}_Financial_Summary"
        excel_path = folder / f"{base_name}.xlsx"
        text_path = folder / f"{base_name}.txt"
        log_path = folder / f"{report_date:%Y-%m}_Processing_Log.txt"
        html_path = folder / f"{base_name}.html"

        write_monthly_report(month_df.copy(), excel_path, text_path)
        write_monthly_processing_log(month_df.copy(), log_path)

        # Monthly interactive HTML dashboard
        generate_html_dashboard(
            df=month_df.copy(),
            output_html_path=html_path,
            title=f"Financial Summary - {report_date.strftime('%B %Y')}",
            subtitle=f"Monthly Spending Breakdown & Transactions for {report_date.strftime('%B %Y')}",
        )

        generated_reports.extend([excel_path, text_path, log_path, html_path])
        print(f"Created: {log_path}")
        print(f"Created: {excel_path}")
        print(f"Created: {html_path}")
    return generated_reports


# -----------------------------
# 6. Main
# -----------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Turn HDFC statement PDFs or text exports into easy-to-read month-wise reports."
    )
    parser.add_argument(
        "--input", "-i", nargs="+", default=["BANK_STATEMENT"],
        help="Statement file(s) or folder(s); default: BANK_STATEMENT.",
    )
    parser.add_argument(
        "--output-dir", "-o", default="Financial_Reports",
        help="Folder for YYYY/MM-Month report packages (default: Financial_Reports).",
    )
    parser.add_argument(
        "--log-file", "-l", default="HDFC_BANK_STATEMENT_PARSER.log",
        help="Path to execution log file (default: HDFC_BANK_STATEMENT_PARSER.log).",
    )
    args = parser.parse_args()

    log_path = Path(args.log_file).resolve()
    input_files = collect_statement_files(args.input)
    if not input_files:
        print("No .pdf or .txt statements found. Put statement files in BANK_STATEMENT or use --input.")
        return

    transactions = []
    for input_path in input_files:
        print(f"Reading statement: {input_path}")
        extracted = extract_transactions(str(input_path))
        if extracted.empty:
            print(f"No transactions found in: {input_path}")
            continue
        transactions.append(extracted)

    if not transactions:
        print("No transactions found. Check the input file paths and statement structure.")
        return

    df = pd.concat(transactions, ignore_index=True).drop_duplicates().sort_values("Date").reset_index(drop=True)
    df = df[df["Amount (₹)"] > 0].reset_index(drop=True)
    transport_count_before_heuristic = (df["Category"] == "Transport").sum()
    df = apply_daily_transport_heuristic(df)
    heuristic_count = (df["Category"] == "Transport").sum() - transport_count_before_heuristic
    print(f"Extracted {len(df)} transactions spanning {df['MonthYear'].nunique()} month(s).")
    print(f"Daily UPI fare heuristic reclassified {heuristic_count} transaction(s) as Transport.")
    print("Building month-wise Excel and text reports...")
    reports = write_reports_by_month(df, args.output_dir)
    for report in reports:
        print(f"Created: {report}")

    # Automatically write / dump timestamped run details to HDFC_BANK_STATEMENT_PARSER.log
    write_execution_log(
        log_path=log_path,
        input_files=input_files,
        df=df,
        heuristic_count=heuristic_count,
        generated_files=reports,
        status="SUCCESS",
    )


if __name__ == "__main__":
    main()
