import subprocess
import sys
import tempfile
import textwrap
import unittest
from decimal import Decimal
from io import StringIO
from pathlib import Path

from spending_analysis import Transaction, format_report, load_transactions, summarize_transactions


class LoadTransactionsTests(unittest.TestCase):
    def test_load_transactions_reads_csv_rows(self):
        handle = StringIO(
            textwrap.dedent(
                """\
                date,description,category,amount
                2026-09-01,Coffee,Food,-4.50
                2026-09-02,Paycheck,Income,1200.00
                """
            )
        )

        transactions = load_transactions(handle)

        self.assertEqual(
            transactions,
            [
                Transaction("2026-09-01", "Coffee", "Food", Decimal("-4.50")),
                Transaction("2026-09-02", "Paycheck", "Income", Decimal("1200.00")),
            ],
        )

    def test_load_transactions_requires_expected_columns(self):
        handle = StringIO("date,description,amount\n2026-09-01,Coffee,-4.50\n")

        with self.assertRaisesRegex(ValueError, "missing required fields: category"):
            load_transactions(handle)

    def test_load_transactions_rejects_blank_required_values(self):
        handle = StringIO("date,description,category,amount\n2026-09-01,Coffee,,-4.50\n")

        with self.assertRaisesRegex(ValueError, "Missing category value on row 2"):
            load_transactions(handle)

    def test_load_transactions_rejects_extra_values(self):
        handle = StringIO("date,description,category,amount\n2026-09-01,Coffee,Food,-4.50,unexpected\n")

        with self.assertRaisesRegex(ValueError, "Row 2 has more values than headers"):
            load_transactions(handle)


class SpendingSummaryTests(unittest.TestCase):
    def test_summarize_transactions_separates_income_and_spending(self):
        summary = summarize_transactions(
            [
                Transaction("2026-09-01", "Groceries", "Food", Decimal("-25.25")),
                Transaction("2026-09-02", "Bus pass", "Transport", Decimal("-10.00")),
                Transaction("2026-09-03", "Refund", "Food", Decimal("5.00")),
                Transaction("2026-09-04", "Dinner", "Food", Decimal("-9.75")),
            ]
        )

        self.assertEqual(summary["transaction_count"], 4)
        self.assertEqual(summary["total_income"], Decimal("5.00"))
        self.assertEqual(summary["total_spending"], Decimal("45.00"))
        self.assertEqual(summary["net_total"], Decimal("-40.00"))
        self.assertEqual(
            summary["spending_by_category"],
            {"Food": Decimal("35.00"), "Transport": Decimal("10.00")},
        )

    def test_format_report_handles_no_spending(self):
        report = format_report(
            {
                "transaction_count": 1,
                "total_income": Decimal("25.00"),
                "total_spending": Decimal("0.00"),
                "net_total": Decimal("25.00"),
                "spending_by_category": {},
            }
        )

        self.assertIn("- No spending transactions", report)


class CliTests(unittest.TestCase):
    def test_cli_prints_summary(self):
        csv_data = textwrap.dedent(
            """\
            date,description,category,amount
            2026-09-01,Rent,Housing,-800.00
            2026-09-05,Salary,Income,2000.00
            """
        )
        repo_root = Path(__file__).resolve().parents[1]

        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as handle:
            handle.write(csv_data)
            csv_path = handle.name

        try:
            result = subprocess.run(
                [sys.executable, str(repo_root / "spending_analysis.py"), csv_path],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            Path(csv_path).unlink()

        self.assertIn("Personal Transactions Summary", result.stdout)
        self.assertIn("Total income: $2000.00", result.stdout)
        self.assertIn("- Housing: $800.00", result.stdout)

    def test_cli_reports_invalid_csv(self):
        csv_data = textwrap.dedent(
            """\
            date,description,amount
            2026-09-01,Rent,-800.00
            """
        )
        repo_root = Path(__file__).resolve().parents[1]

        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as handle:
            handle.write(csv_data)
            csv_path = handle.name

        try:
            result = subprocess.run(
                [sys.executable, str(repo_root / "spending_analysis.py"), csv_path],
                capture_output=True,
                text=True,
            )
        finally:
            Path(csv_path).unlink()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required fields: category", result.stderr)

    def test_cli_reports_missing_file(self):
        repo_root = Path(__file__).resolve().parents[1]
        missing_path = repo_root / "does-not-exist.csv"

        result = subprocess.run(
            [sys.executable, str(repo_root / "spending_analysis.py"), str(missing_path)],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
