from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, TextIO


@dataclass(frozen=True)
class Transaction:
    date: str
    description: str
    category: str
    amount: Decimal


@dataclass(frozen=True)
class SpendingSummary:
    transaction_count: int
    total_income: Decimal
    total_spending: Decimal
    net_total: Decimal
    spending_by_category: dict[str, Decimal]


def load_transactions(handle: TextIO) -> list[Transaction]:
    reader = csv.DictReader(handle)
    required_fields = {"date", "description", "category", "amount"}

    if reader.fieldnames is None:
        raise ValueError("Transaction data must include a header row.")

    normalized_fieldnames = [(field or "").strip().lower() for field in reader.fieldnames]
    header_counts = Counter(field for field in normalized_fieldnames if field)
    duplicate_fields = sorted(field for field, count in header_counts.items() if count > 1)
    if duplicate_fields:
        duplicates = ", ".join(duplicate_fields)
        raise ValueError(f"Transaction data has duplicate fields after normalization: {duplicates}.")

    missing_fields = required_fields.difference(normalized_fieldnames)
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ValueError(f"Transaction data is missing required fields: {missing}.")

    normalized_rows = []
    for row_number, row in enumerate(reader, start=2):
        normalized_row = {}
        for key, value in row.items():
            if key is None:
                raise ValueError(f"Row {row_number} has more values than headers.")

            normalized_row[key.strip().lower()] = (value or "").strip()

        for field in required_fields:
            if not normalized_row.get(field):
                raise ValueError(f"Missing {field} value on row {row_number}.")

        try:
            amount = Decimal(normalized_row["amount"])
        except (InvalidOperation, KeyError) as exc:
            raise ValueError(f"Invalid amount on row {row_number}.") from exc

        normalized_rows.append(
            Transaction(
                date=normalized_row["date"],
                description=normalized_row["description"],
                category=normalized_row["category"],
                amount=amount,
            )
        )

    return normalized_rows


def summarize_transactions(transactions: Iterable[Transaction]) -> SpendingSummary:
    total_income = Decimal("0")
    total_spending = Decimal("0")
    spending_by_category: dict[str, Decimal] = {}
    transaction_count = 0

    for transaction in transactions:
        transaction_count += 1
        if transaction.amount > 0:
            total_income += transaction.amount
        elif transaction.amount < 0:
            spending_amount = -transaction.amount
            total_spending += spending_amount
            spending_by_category[transaction.category] = spending_by_category.get(transaction.category, Decimal("0")) + spending_amount

    return SpendingSummary(
        transaction_count=transaction_count,
        total_income=total_income,
        total_spending=total_spending,
        net_total=total_income - total_spending,
        spending_by_category=dict(sorted(spending_by_category.items(), key=lambda item: (-item[1], item[0]))),
    )


def format_report(summary: SpendingSummary) -> str:
    lines = [
        "Personal Transactions Summary",
        f"Transactions: {summary.transaction_count}",
        f"Total income: ${summary.total_income:.2f}",
        f"Total spending: ${summary.total_spending:.2f}",
        f"Net total: ${summary.net_total:.2f}",
        "Spending by category:",
    ]

    if summary.spending_by_category:
        lines.extend(f"- {category}: ${amount:.2f}" for category, amount in summary.spending_by_category.items())
    else:
        lines.append("- No spending transactions")

    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze personal transaction history from a CSV file.")
    parser.add_argument("csv_file", help="Path to a CSV file with date, description, category, and amount columns")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    csv_file = Path(args.csv_file)
    try:
        with csv_file.open(newline="", encoding="utf-8") as handle:
            transactions = load_transactions(handle)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(format_report(summarize_transactions(transactions)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
