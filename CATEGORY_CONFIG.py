"""
CATEGORY_CONFIG.py

Centralized transaction classification engine with unified category rules.
Loads rules from category_rules.json with fallback to default in-memory rules.
"""

import json
import re
from datetime import datetime, time
from pathlib import Path
import pandas as pd

CONFIG_JSON_PATH = Path(__file__).parent / "category_rules.json"

# -----------------------------
# 1. Shared Category Rules (Strict Priority Order - First Match Wins)
# -----------------------------

DEFAULT_CATEGORY_RULES = [
    ("Salary / Income", [
        "IBMINDIAPRIVATELI", "IBM INDIA PRIVATE", "IBMINDIAPRIVATE", "IBM INDIA",
        "SALARY", "PAYROLL",
    ]),
    ("Rent", [
        "UPI-ASHOKA", "ASHOKA KOTRESHA", "SADHANA AK", " RENT ",
    ]),
    ("House Maintenance", [
        "KOTRESHA", "HOUSE_MAINT", "MAINTENANCE", "ICIC0000106-VAASTUDEW",
        "VAASTUDEW", "VAASTUDEW FLOWER", "DEW FLOWER",
    ]),
    ("Self / Family Transfer", [
        "SHREYAS S BAGI", "SHREYASSBAGI", "SHANTESH B BAGI", "SHANTESHBBAGI",
        "SHANTESH BAGI", "SHANTESH", "SAVITHA SHANTESH", "SAVITHA", "SAHANA SHANTESH",
        "SAHANA", "NAGARATHNAV MUNDASA", "NAGARATHNAV", "MUNDASA",
    ]),
    ("Parents / Grandparents / Siblings Spending", [
        "LAKSHMIPATHIG", "UPI-LAKSHMIPATHIG",
    ]),
    ("Tax Refund / Tax Payment", [
        "ITDTAX REFUND", "TAX REFUND", "DIRECTTAX", "DTAX-DIRECTTAX",
    ]),
    ("Investments", [
        "GROWW", "GROWW INVEST", "GROWW.BRK", "UTKARSH SMALL FINANC", "MUTUAL FUND",
        "ICCLMF", "ICCL", "MF COLLECT",
    ]),
    ("Donations / Religious", [
        "SARVEDYNABASAYYA", "VEERANJANEYARELIGIO", "VEERANJANEYA", "RELIGIO", "SEVA",
    ]),
    ("Bank Charges / Interest", [
        "INTEREST PAID", "IB BILLPAY", "HDFC BANK LIMITED", "CHARGES", " FEE ",
        "NEFT CHARGES", "SMS CHARGES", "INCHGS",
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
        "SOMASHEKHAR", "UPI-SOMASHEKHAR", "Q523974455",
        "KABULI", "MUDULI-BHARATPE90727093430", "MUDULI-BHARATPE", "MUDULI",
        "VIHAANFAMILY", "RESTAU", "FAMILYKITCHEN", "KAPOORSCHAAT", "BHANDA",
        "SHREEENTERPRISES", "RESTAURANT", "HOTEL", "ZOMATO", "PAYZOMATO",
        "SWIGGY", "MCDONALDS", "DOMINOS", "KITCHEN", "BAKERY", "MAYURABAKERYAND",
        "SWEET", "BIGMISHRASWEET", "BIRIYANI", "BIRYANI", "COFFEE", "CAFE",
        "TIFFIN", "MESS", "CATERERS", "FOOD", "DHABA", "BHAVAN", "MART",
        "HYPER MART", "VEGETABLE", "FRUITS", "VEG-", "PALACE", "SRISAIPALACE",
        "HOTELASHRAYA", "UPACHA", "APOLLO PHARMAC",
    ]),
    ("Petrol / Fuel", [
        "THEFUELHUB", "BABULALKGUPTA", "SATHYASAIFILLINGS", "FILLINGS", "PETROL", "FUEL",
    ]),
    ("Transport", [
        "BMTC", "UPI-BMTCBUS", "BMRCL", "NCMC", "METRO", "NWKRTC", "UBER", "RAPIDO", "OLA",
        "BAGMANE", "MYBMTCDQR",
    ]),
    ("General UPI / Shopping", [
        "AMAZON", "AMAZONUPI", "FLIPKART", "BLINKIT", "MYNTRA", "DECATHLON", "RELIANCE RETAIL",
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
        "TAGMANGO", "GEEKSFORGEEKS", "HABUILD",
    ]),
    ("Utilities / Recharge", [
        "AIRTEL", "JIO", "VODAFONE", "RECHARGE", "ELECTRICITY", "ELECTRICIT",
        "PPAUTOPAYEL", "PPAUTOPAYELECTRICIT", "GAS", "BESCOM", "WATER",
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

DEFAULT_TRANSPORT_PATTERNS = [
    r"\bKA\d{2}[A-Z]{1,2}\d{4}\b",
]


def load_category_config():
    """Load category rules and patterns from category_rules.json if present, else fallback."""
    if CONFIG_JSON_PATH.exists():
        try:
            data = json.loads(CONFIG_JSON_PATH.read_text(encoding="utf-8"))
            rules = [(cat["name"], cat["keywords"]) for cat in data.get("categories", [])]
            patterns = data.get("transport_narration_patterns", DEFAULT_TRANSPORT_PATTERNS)
            heuristics = data.get("transport_heuristics", {})
            return rules, patterns, heuristics
        except Exception as e:
            print(f"Warning: Could not read {CONFIG_JSON_PATH}: {e}. Using default rules.")
    return DEFAULT_CATEGORY_RULES, DEFAULT_TRANSPORT_PATTERNS, {
        "morning_start_hour": 8, "morning_start_minute": 0,
        "morning_end_hour": 11, "morning_end_minute": 0,
        "daily_min_amount": 40.0, "daily_max_amount": 120.0
    }


CATEGORY_RULES, TRANSPORT_NARRATION_PATTERNS, TRANSPORT_HEURISTICS = load_category_config()

MORNING_TRANSPORT_START = time(
    TRANSPORT_HEURISTICS.get("morning_start_hour", 8),
    TRANSPORT_HEURISTICS.get("morning_start_minute", 0)
)
MORNING_TRANSPORT_END = time(
    TRANSPORT_HEURISTICS.get("morning_end_hour", 11),
    TRANSPORT_HEURISTICS.get("morning_end_minute", 0)
)
DAILY_UPI_TRANSPORT_MIN_AMOUNT = float(TRANSPORT_HEURISTICS.get("daily_min_amount", 40.0))
DAILY_UPI_TRANSPORT_MAX_AMOUNT = float(TRANSPORT_HEURISTICS.get("daily_max_amount", 120.0))


# -----------------------------
# 2. Shared Helper Functions
# -----------------------------

def parse_date(date_str: str) -> datetime:
    """Accept statement dates in DD/MM/YY, DD/MM/YYYY, DD-MM-YYYY or YYYY-MM-DD."""
    value = date_str.strip()
    for date_format in ("%d/%m/%y", "%d/%m/%Y", "%d-%m-%Y", "%d-%m-%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    raise ValueError(f"Unsupported statement date format: {value}")


def clean_amount(val) -> float:
    if val is None:
        return 0.0
    val = str(val).strip().replace(",", "")
    if val == "":
        return 0.0
    try:
        return float(re.sub(r"[^\d.]", "", val))
    except ValueError:
        return 0.0


def week_number_in_month(dt: datetime) -> int:
    return (dt.day - 1) // 7 + 1


def detect_type(withdrawal: float, deposit: float) -> str:
    if withdrawal > 0 and deposit == 0:
        return "Debit"
    if deposit > 0 and withdrawal == 0:
        return "Credit"
    return "Debit" if withdrawal >= deposit else "Credit"


def extract_time_from_narration(narration: str) -> time | None:
    """Extract a transaction time when present in narration."""
    value = narration.upper()
    match = re.search(r"\b(0?[1-9]|1[0-2])(?::([0-5]\d))(?::([0-5]\d))?\s*(AM|PM)\b", value)
    if match:
        hour = int(match.group(1)) % 12
        if match.group(4) == "PM":
            hour += 12
        return time(hour, int(match.group(2) or 0))

    match = re.search(r"\b([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?\b", value)
    if match:
        return time(int(match.group(1)), int(match.group(2)))
    return None


def classify_category(narration: str, transaction_time: time | None = None) -> str:
    n = narration.upper()
    if any(re.search(pattern, n) for pattern in TRANSPORT_NARRATION_PATTERNS):
        return "Transport"
    if (
        re.search(r"(?:^|[\s:/-])UPI[-/]", n)
        and transaction_time is not None
        and MORNING_TRANSPORT_START <= transaction_time < MORNING_TRANSPORT_END
    ):
        return "Transport"
    for category, keywords in CATEGORY_RULES:
        if any(kw in n for kw in keywords):
            return category
    if "NEFT CR" in n or "CREDIT" in n or " CR " in n or "SALARY" in n:
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
        & result["Narration"].str.contains(r"\bUPI(?:[-/:]|$)", case=False, na=False, regex=True)
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
    n = re.sub(r"^UPI[-/]", "", n)
    n = re.sub(r"^NEFT (CR|DR)[-/]", "", n)
    n = re.sub(r"^REV-UPI[-/]", "", n)
    token = re.split(r"[@\-/]", n)[0]
    token = re.sub(r"\s+", " ", token).strip()
    return token or n[:30]
