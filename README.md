# Spending_Analysis

My Personal Transactions History. A Spending Analysis Tool

## Usage

Create a CSV file with these columns:

- `date`
- `description`
- `category`
- `amount`

Use negative amounts for spending and positive amounts for income.

Run the tool with Python 3:

```bash
python spending_analysis.py /path/to/transactions.csv
```

Example output:

```text
Personal Transactions Summary
Transactions: 3
Total income: $1200.00
Total spending: $54.50
Net total: $1145.50
Spending by category:
- Food: $24.50
- Utilities: $30.00
```
