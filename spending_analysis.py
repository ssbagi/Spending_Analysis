from __future__ import annotations

import argparse
import csv
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


def load_transactions(handle: TextIO) -> list[Transaction]:
    reader = csv.DictReader(handle)
    required_fields = {"date", "description", "category", "amount"}

    if reader.fieldnames is None:
        raise ValueError("Transaction data must include a header row.")

    missing_fields = required_fields.difference(field.strip().lower() for field in reader.fieldnames)
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ValueError(f"Transaction data is missing required fields: {missing}.")

    normalized_rows = []
    for row_number, row in enumerate(reader, start=2):
        normalized_row = {key.strip().lower(): (value or "").strip() for key, value in row.items()}
        try:
            amount = Decimal(normalized_row["amount"])
        except (InvalidOperation, KeyError) as exc:
            raise ValueError(f"Invalid amount on row {row_number}.") from exc

        normalized_rows.append(
            Transaction(
                date=normalized_row.get("date", ""),
                description=normalized_row.get("description", ""),
                category=normalized_row.get("category", "Uncategorized") or "Uncategorized",
                amount=amount,
            )
        )

    return normalized_rows


def summarize_transactions(transactions: Iterable[Transaction]) -> dict[str, object]:
    total_income = Decimal("0")
    total_spending = Decimal("0")
    spending_by_category: dict[str, Decimal] = {}
    transaction_count = 0

    for transaction in transactions:
        transaction_count += 1
        if transaction.amount >= 0:
            total_income += transaction.amount
        else:
            spending_amount = -transaction.amount
            total_spending += spending_amount
            spending_by_category[transaction.category] = spending_by_category.get(transaction.category, Decimal("0")) + spending_amount

    return {
        "transaction_count": transaction_count,
        "total_income": total_income,
        "total_spending": total_spending,
        "net_total": total_income - total_spending,
        "spending_by_category": dict(sorted(spending_by_category.items(), key=lambda item: (-item[1], item[0]))),
    }


def format_report(summary: dict[str, object]) -> str:
    spending_by_category: dict[str, Decimal] = summary["spending_by_category"]  # type: ignore[assignment]
    lines = [
        "Personal Transactions Summary",
        f"Transactions: {summary['transaction_count']}",
        f"Total income: ${summary['total_income']:.2f}",
        f"Total spending: ${summary['total_spending']:.2f}",
        f"Net total: ${summary['net_total']:.2f}",
        "Spending by category:",
    ]

    if spending_by_category:
        lines.extend(f"- {category}: ${amount:.2f}" for category, amount in spending_by_category.items())
    else:
        lines.append("- No spending transactions")

    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze personal transaction history from a CSV file.")
    parser.add_argument("csv_file", type=Path, help="Path to a CSV file with date, description, category, and amount columns")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    with args.csv_file.open(newline="", encoding="utf-8") as handle:
        transactions = load_transactions(handle)

    print(format_report(summarize_transactions(transactions)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
