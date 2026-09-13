"""
HTML_REPORT_GENERATOR.py

Generates beautiful, interactive, family-friendly HTML financial dashboards
with Chart.js charts, month-by-month interactive tab navigation (All Months, Feb 2026,
Mar 2026, etc.), dynamic KPI calculation, category breakdowns, weekly trends,
top recurring vendors, and instant search/filtering.
"""

import json
from pathlib import Path
import pandas as pd


def generate_html_dashboard(
    df: pd.DataFrame,
    output_html_path: Path,
    title: str,
    subtitle: str = "",
) -> None:
    """Generate a clean, modern, interactive HTML dashboard with month tabs and Chart.js charts."""
    # Determine unique months sorted chronologically
    month_order = sorted(
        list(df["MonthYear"].unique()),
        key=lambda my: pd.to_datetime(my, format="%b-%Y")
    )

    # Format all transactions into JSON-friendly dicts
    transactions_list = []
    for _, row in df.iterrows():
        transactions_list.append({
            "date": row["Date"].strftime("%d-%m-%Y"),
            "isoDate": row["Date"].strftime("%Y-%m-%d"),
            "monthYear": str(row["MonthYear"]),
            "week": int(row.get("WeekNumberInMonth", (row["Date"].day - 1) // 7 + 1)),
            "bank": str(row.get("Bank", "HDFC Bank")),
            "narration": str(row["Narration"]),
            "category": str(row["Category"]),
            "type": str(row["Type"]),
            "amount": round(float(row["Amount (₹)"]), 2),
            "closing": round(float(row["Closing Balance (₹)"]), 2),
            "chq": str(row.get("ChqRefNo", "")),
        })

    # Available categories and banks
    all_categories = sorted(list(df["Category"].unique()))
    all_banks = sorted(list(df["Bank"].unique())) if "Bank" in df.columns else ["HDFC Bank"]
    has_multi_banks = len(all_banks) > 1

    # Build month tabs list: "ALL" + each month
    month_tabs = [{"id": "ALL", "label": "All Months (Overview)"}]
    for m in month_order:
        try:
            dt = pd.to_datetime(m, format="%b-%Y")
            formatted_label = dt.strftime("%b %Y")  # e.g., "Feb 2026"
        except Exception:
            formatted_label = m
        month_tabs.append({"id": m, "label": formatted_label})

    # Build tabs HTML
    tabs_buttons = []
    for tab in month_tabs:
        active_cls = " active" if tab["id"] == "ALL" else ""
        tab_id = tab["id"]
        tab_lbl = tab["label"]
        tabs_buttons.append(f'<button class="tab-btn{active_cls}" onclick="selectMonthTab(\'{tab_id}\')">{tab_lbl}</button>')
    tabs_html = "".join(tabs_buttons)

    # Date range strings
    min_date = df["Date"].min().strftime("%d-%m-%Y") if not df.empty else "N/A"
    max_date = df["Date"].max().strftime("%d-%m-%Y") if not df.empty else "N/A"

    # Distinct vibrant color palette
    palette = [
        "#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6",
        "#EC4899", "#14B8A6", "#F97316", "#6366F1", "#84CC16",
        "#06B6D4", "#E11D48", "#059669", "#D97706", "#7C3AED",
        "#DB2777", "#0D9488", "#EA580C", "#4F46E5", "#65A30D",
        "#0891B2", "#BE123C", "#047857", "#B45309"
    ]

    # Category and Bank dropdown options
    category_options_html = "".join(f'<option value="{c}">{c}</option>' for c in all_categories)
    bank_options_html = "".join(f'<option value="{b}">{b}</option>' for b in all_banks)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-primary: #f8fafc;
            --bg-card: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --income: #10b981;
            --expense: #ef4444;
            --savings: #3b82f6;
            --accent: #6366f1;
            --accent-light: #e0e7ff;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        body {{
            background-color: var(--bg-primary);
            color: var(--text-main);
            padding: 24px 16px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1240px;
            margin: 0 auto;
        }}
        /* Header */
        .header {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            color: white;
            padding: 28px;
            border-radius: 16px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .header h1 {{
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .header p {{
            color: #94a3b8;
            font-size: 13px;
        }}
        .header-badge {{
            background: rgba(255, 255, 255, 0.12);
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 13px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            font-weight: 500;
        }}

        /* Month Navigation Tabs */
        .tabs-container {{
            background: var(--bg-card);
            border-radius: 14px;
            padding: 8px;
            margin-bottom: 24px;
            border: 1px solid var(--border);
            display: flex;
            gap: 8px;
            overflow-x: auto;
            scrollbar-width: thin;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }}
        .tab-btn {{
            background: transparent;
            border: none;
            padding: 10px 18px;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            color: var(--text-muted);
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s ease;
        }}
        .tab-btn:hover {{
            background: #f1f5f9;
            color: var(--text-main);
        }}
        .tab-btn.active {{
            background: var(--accent);
            color: #ffffff;
            box-shadow: 0 2px 4px rgba(99, 102, 241, 0.3);
        }}

        /* KPI Cards Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: var(--bg-card);
            padding: 20px 24px;
            border-radius: 14px;
            border: 1px solid var(--border);
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }}
        .card-title {{
            font-size: 12px;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            margin-bottom: 8px;
        }}
        .card-value {{
            font-size: 26px;
            font-weight: 700;
        }}
        .card-value.income {{ color: var(--income); }}
        .card-value.expense {{ color: var(--expense); }}
        .card-value.savings {{ color: var(--savings); }}
        .card-value.count {{ color: var(--accent); }}
        .card-subtext {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
        }}

        /* Charts Grid */
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(520px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}
        @media (max-width: 650px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        .chart-card {{
            background: var(--bg-card);
            border-radius: 14px;
            padding: 22px;
            border: 1px solid var(--border);
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }}
        .chart-card h2 {{
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .chart-container {{
            position: relative;
            height: 300px;
            width: 100%;
        }}

        /* Tables */
        .table-card {{
            background: var(--bg-card);
            border-radius: 14px;
            padding: 24px;
            border: 1px solid var(--border);
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            margin-bottom: 24px;
            overflow-x: auto;
        }}
        .table-card h2 {{
            font-size: 17px;
            font-weight: 700;
            margin-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .filters {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .search-input, .filter-select {{
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 8px;
            font-size: 13px;
            outline: none;
            background: #f8fafc;
        }}
        .search-input:focus, .filter-select:focus {{
            border-color: var(--accent);
            background: #fff;
        }}
        .search-input {{ min-width: 220px; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }}
        th {{
            background: #f1f5f9;
            color: #475569;
            font-weight: 600;
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
            color: var(--text-main);
        }}
        tr:hover td {{
            background-color: #f8fafc;
        }}
        .text-right {{ text-align: right; }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        }}
        .badge-category {{
            background: #ede9fe;
            color: #5b21b6;
        }}
        .badge-debit {{
            background: #fee2e2;
            color: #b91c1c;
        }}
        .badge-credit {{
            background: #d1fae5;
            color: #047857;
        }}
        .badge-bank {{
            background: #e0f2fe;
            color: #0369a1;
        }}
        .progress-bar-bg {{
            background: #e2e8f0;
            border-radius: 4px;
            height: 6px;
            width: 70px;
            display: inline-block;
            overflow: hidden;
            vertical-align: middle;
            margin-right: 8px;
        }}
        .progress-bar-fill {{
            background: var(--accent);
            height: 100%;
            border-radius: 4px;
        }}
        .tx-table-wrap {{
            max-height: 480px;
            overflow-y: auto;
            border: 1px solid var(--border);
            border-radius: 8px;
        }}
        .empty-state {{
            text-align: center;
            padding: 30px;
            color: var(--text-muted);
            font-size: 14px;
        }}
        .footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 12px;
            margin-top: 32px;
            padding: 16px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div>
                <h1>{title}</h1>
                <p id="headerSubtitle">{subtitle or "Interactive Bank Statement & Spending Dashboard"} &bull; {min_date} to {max_date}</p>
            </div>
            <div class="header-badge">
                Shreyas S Bagi &bull; HDFC Bank
            </div>
        </div>

        <!-- Month Navigation Tabs -->
        <div class="tabs-container">
            {tabs_html}
        </div>

        <!-- KPI Cards Grid -->
        <div class="kpi-grid">
            <div class="card">
                <div class="card-title">Total Income / Deposits</div>
                <div class="card-value income" id="kpiIncome">₹0.00</div>
                <div class="card-subtext" id="kpiIncomeSub">Salary &amp; Credits received</div>
            </div>
            <div class="card">
                <div class="card-title">Total Expenses / Debits</div>
                <div class="card-value expense" id="kpiExpense">₹0.00</div>
                <div class="card-subtext" id="kpiExpenseSub">All expenditures &amp; transfers out</div>
            </div>
            <div class="card">
                <div class="card-title">Net Savings / Cashflow</div>
                <div class="card-value" id="kpiSavings">₹0.00</div>
                <div class="card-subtext" id="kpiSavingsSub">Credits minus Debits</div>
            </div>
            <div class="card">
                <div class="card-title">Total Transactions</div>
                <div class="card-value count" id="kpiTxnCount">0</div>
                <div class="card-subtext" id="kpiCategoryCount">0 Categories Tracked</div>
            </div>
        </div>

        <!-- Interactive Charts Grid -->
        <div class="charts-grid">
            <!-- Pie / Donut Chart -->
            <div class="chart-card">
                <h2>📊 Spending Breakdown by Category</h2>
                <div class="chart-container">
                    <canvas id="categoryPieChart"></canvas>
                </div>
            </div>

            <!-- Top Expense Categories Ranking -->
            <div class="chart-card">
                <h2>🏆 Top Expense Categories (₹)</h2>
                <div class="chart-container">
                    <canvas id="categoryBarChart"></canvas>
                </div>
            </div>

            <!-- Weekly Spending Trend Chart -->
            <div class="chart-card">
                <h2>📈 Weekly Spending Trend (₹)</h2>
                <div class="chart-container">
                    <canvas id="weeklyChart"></canvas>
                </div>
            </div>

            <!-- Secondary Chart (Monthly Cashflow or Daily Pattern) -->
            <div class="chart-card">
                <h2 id="secondaryChartTitle">📅 Monthly Cashflow (Debits vs Credits)</h2>
                <div class="chart-container">
                    <canvas id="secondaryChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Category Summary Breakdown Table -->
        <div class="table-card">
            <h2>
                <span>📊 Category Financial Summary</span>
                <span style="font-size: 13px; font-weight: 500; color: var(--text-muted);" id="categoryTableSubtitle"></span>
            </h2>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th class="text-right">Transactions</th>
                        <th class="text-right">Debit (₹)</th>
                        <th>% of Expenses</th>
                        <th class="text-right">Credit (₹)</th>
                        <th class="text-right">Net Change (₹)</th>
                    </tr>
                </thead>
                <tbody id="categoryTableBody">
                </tbody>
            </table>
        </div>

        <!-- Top Regular Vendors / Recurring Payments -->
        <div class="table-card" id="recurringCard">
            <h2>🔁 Top Regular Vendors &amp; Recurring Payments</h2>
            <table>
                <thead>
                    <tr>
                        <th>Merchant / Vendor Keyword</th>
                        <th class="text-right">Frequency</th>
                        <th class="text-right">Total Amount (₹)</th>
                    </tr>
                </thead>
                <tbody id="recurringTableBody">
                </tbody>
            </table>
        </div>

        <!-- Searchable & Filterable Transactions Table -->
        <div class="table-card">
            <h2>
                <span>📝 Categorized Transactions (<span id="txCount">0</span>)</span>
                <div class="filters">
                    <input type="text" id="searchInput" class="search-input" placeholder="🔍 Search narration, date, amount...">
                    <select id="bankFilter" class="filter-select">
                        <option value="">All Accounts</option>
                        {bank_options_html}
                    </select>
                    <select id="categoryFilter" class="filter-select">
                        <option value="">All Categories</option>
                        {category_options_html}
                    </select>
                    <select id="typeFilter" class="filter-select">
                        <option value="">All Types</option>
                        <option value="Debit">Debits only</option>
                        <option value="Credit">Credits only</option>
                    </select>
                </div>
            </h2>
            <div class="tx-table-wrap">
                <table id="transactionsTable">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Account</th>
                            <th>Narration</th>
                            <th>Category</th>
                            <th>Type</th>
                            <th class="text-right">Amount (₹)</th>
                            <th class="text-right">Balance (₹)</th>
                        </tr>
                    </thead>
                    <tbody id="txTableBody">
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            Generated automatically by HDFC Bank Statement Parser &bull; Clear, Interactive Family Financial Dashboard
        </div>
    </div>

    <!-- Chart.js and Dynamic Filter Logic -->
    <script>
        const rawTransactions = {json.dumps(transactions_list)};
        const allMonthsList = {json.dumps(month_order)};
        const palette = {json.dumps(palette)};

        let currentSelectedMonth = "ALL";
        let pieChart = null;
        let barChart = null;
        let weeklyChart = null;
        let secondaryChart = null;

        function getMonthTransactions(monthId) {{
            if (monthId === "ALL") {{
                return rawTransactions;
            }}
            return rawTransactions.filter(tx => tx.monthYear === monthId);
        }}

        function selectMonthTab(monthId) {{
            currentSelectedMonth = monthId;

            // Update Tab Active State
            const buttons = document.querySelectorAll('.tab-btn');
            buttons.forEach(btn => {{
                btn.classList.remove('active');
                if ((monthId === "ALL" && btn.innerText.includes("All Months")) ||
                    (monthId !== "ALL" && btn.getAttribute("onclick").includes(monthId))) {{
                    btn.classList.add('active');
                }}
            }});

            // Refresh entire dashboard view
            updateDashboard(monthId);
        }}

        function updateDashboard(monthId) {{
            const txs = getMonthTransactions(monthId);

            // 1. Compute KPIs
            let totalDebit = 0;
            let totalCredit = 0;
            txs.forEach(t => {{
                if (t.type === "Debit") totalDebit += t.amount;
                else if (t.type === "Credit") totalCredit += t.amount;
            }});
            const netSavings = totalCredit - totalDebit;

            document.getElementById('kpiIncome').innerText = '₹' + totalCredit.toLocaleString('en-IN', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
            document.getElementById('kpiExpense').innerText = '₹' + totalDebit.toLocaleString('en-IN', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});

            const kpiSavings = document.getElementById('kpiSavings');
            if (netSavings >= 0) {{
                kpiSavings.innerText = '₹' + netSavings.toLocaleString('en-IN', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
                kpiSavings.style.color = 'var(--income)';
                document.getElementById('kpiSavingsSub').innerText = 'Net Positive Cashflow';
            }} else {{
                kpiSavings.innerText = '-₹' + Math.abs(netSavings).toLocaleString('en-IN', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
                kpiSavings.style.color = 'var(--expense)';
                document.getElementById('kpiSavingsSub').innerText = 'Net Negative Cashflow';
            }}

            document.getElementById('kpiTxnCount').innerText = txs.length;

            // 2. Category Aggregations
            const catDebitMap = {{}};
            const catCreditMap = {{}};
            const catCountMap = {{}};

            txs.forEach(t => {{
                catCountMap[t.category] = (catCountMap[t.category] || 0) + 1;
                if (t.type === "Debit") {{
                    catDebitMap[t.category] = (catDebitMap[t.category] || 0) + t.amount;
                }} else if (t.type === "Credit") {{
                    catCreditMap[t.category] = (catCreditMap[t.category] || 0) + t.amount;
                }}
            }});

            const allCatsInView = Array.from(new Set(txs.map(t => t.category))).sort();
            document.getElementById('kpiCategoryCount').innerText = `${{allCatsInView.length}} Categories Active`;

            // Sort categories by debit amount descending for chart
            const sortedDebitCats = Object.keys(catDebitMap).sort((a, b) => catDebitMap[b] - catDebitMap[a]);
            const pieLabels = sortedDebitCats;
            const pieValues = sortedDebitCats.map(c => Math.round(catDebitMap[c] * 100) / 100);
            const chartColors = pieLabels.map((_, i) => palette[i % palette.length]);

            // 3. Update Pie / Donut Chart
            if (pieChart) pieChart.destroy();
            const ctxPie = document.getElementById('categoryPieChart').getContext('2d');
            pieChart = new Chart(ctxPie, {{
                type: 'doughnut',
                data: {{
                    labels: pieLabels,
                    datasets: [{{
                        data: pieValues,
                        backgroundColor: chartColors,
                        borderWidth: 2,
                        borderColor: '#ffffff',
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'right',
                            labels: {{ boxWidth: 12, font: {{ size: 11 }} }}
                        }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    const val = context.parsed || 0;
                                    const total = pieValues.reduce((a, b) => a + b, 0);
                                    const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                                    return `${{context.label}}: ₹${{val.toLocaleString('en-IN')}} (${{pct}}%)`;
                                }}
                            }}
                        }}
                    }}
                }}
            }});

            // 4. Update Category Bar Chart (Top 8)
            if (barChart) barChart.destroy();
            const topCats = sortedDebitCats.slice(0, 8);
            const topCatValues = topCats.map(c => catDebitMap[c]);
            const ctxBar = document.getElementById('categoryBarChart').getContext('2d');
            barChart = new Chart(ctxBar, {{
                type: 'bar',
                data: {{
                    labels: topCats,
                    datasets: [{{
                        label: 'Debit (₹)',
                        data: topCatValues,
                        backgroundColor: chartColors.slice(0, 8),
                        borderRadius: 6,
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ callback: v => '₹' + v.toLocaleString('en-IN') }}
                        }}
                    }}
                }}
            }});

            // 5. Update Weekly Spending Chart
            const weeklyMap = {{}};
            txs.forEach(t => {{
                if (t.type === "Debit") {{
                    const key = monthId === "ALL" ? `${{t.monthYear}} W${{t.week}}` : `Week ${{t.week}}`;
                    weeklyMap[key] = (weeklyMap[key] || 0) + t.amount;
                }}
            }});
            const weeklyLabels = Object.keys(weeklyMap);
            const weeklyValues = weeklyLabels.map(k => Math.round(weeklyMap[k] * 100) / 100);

            if (weeklyChart) weeklyChart.destroy();
            const ctxWeekly = document.getElementById('weeklyChart').getContext('2d');
            weeklyChart = new Chart(ctxWeekly, {{
                type: 'line',
                data: {{
                    labels: weeklyLabels,
                    datasets: [{{
                        label: 'Weekly Spending (₹)',
                        data: weeklyValues,
                        borderColor: '#6366f1',
                        backgroundColor: 'rgba(99, 102, 241, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 5,
                        pointHoverRadius: 7,
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ callback: v => '₹' + v.toLocaleString('en-IN') }}
                        }}
                    }}
                }}
            }});

            // 6. Update Secondary Chart
            if (secondaryChart) secondaryChart.destroy();
            const ctxSecondary = document.getElementById('secondaryChart').getContext('2d');
            const secondaryTitle = document.getElementById('secondaryChartTitle');

            if (monthId === "ALL") {{
                secondaryTitle.innerText = "📅 Monthly Cashflow (Income vs Expenses)";
                const mDebits = [];
                const mCredits = [];
                const mNet = [];

                allMonthsList.forEach(m => {{
                    let d = 0, c = 0;
                    rawTransactions.forEach(t => {{
                        if (t.monthYear === m) {{
                            if (t.type === "Debit") d += t.amount;
                            else if (t.type === "Credit") c += t.amount;
                        }}
                    }});
                    mDebits.push(d);
                    mCredits.push(c);
                    mNet.push(c - d);
                }});

                secondaryChart = new Chart(ctxSecondary, {{
                    type: 'bar',
                    data: {{
                        labels: allMonthsList,
                        datasets: [
                            {{
                                label: 'Income / Credits (₹)',
                                data: mCredits,
                                backgroundColor: '#10b981',
                                borderRadius: 4,
                            }},
                            {{
                                label: 'Expenses / Debits (₹)',
                                data: mDebits,
                                backgroundColor: '#ef4444',
                                borderRadius: 4,
                            }},
                            {{
                                type: 'line',
                                label: 'Net Savings (₹)',
                                data: mNet,
                                borderColor: '#3b82f6',
                                borderWidth: 2,
                                tension: 0.2,
                            }}
                        ]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {{
                            y: {{ ticks: {{ callback: v => '₹' + v.toLocaleString('en-IN') }} }}
                        }}
                    }}
                }});
            }} else {{
                secondaryTitle.innerText = "🔢 Transactions Count by Category";
                const catCountSorted = allCatsInView.map(c => ({{ name: c, count: catCountMap[c] || 0 }}))
                    .sort((a, b) => b.count - a.count).slice(0, 8);

                secondaryChart = new Chart(ctxSecondary, {{
                    type: 'bar',
                    data: {{
                        labels: catCountSorted.map(c => c.name),
                        datasets: [{{
                            label: 'Count',
                            data: catCountSorted.map(c => c.count),
                            backgroundColor: '#8b5cf6',
                            borderRadius: 6,
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{ legend: {{ display: false }} }}
                    }}
                }});
            }}

            // 7. Render Category Breakdown Table
            const catTableBody = document.getElementById('categoryTableBody');
            catTableBody.innerHTML = '';
            const catRows = allCatsInView.map(c => {{
                const d = catDebitMap[c] || 0;
                const cr = catCreditMap[c] || 0;
                const net = cr - d;
                const pct = totalDebit > 0 ? (d / totalDebit * 100) : 0;
                return {{ category: c, count: catCountMap[c] || 0, debit: d, credit: cr, net: net, pct: pct }};
            }}).sort((a, b) => b.debit - a.debit);

            catRows.forEach(r => {{
                const tr = document.createElement('tr');
                const netColor = r.net >= 0 ? '#047857' : '#0f172a';
                const netStr = (r.net >= 0 ? '₹' : '-₹') + Math.abs(r.net).toLocaleString('en-IN', {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
                tr.innerHTML = `
                    <td><strong>${{r.category}}</strong></td>
                    <td class="text-right">${{r.count}}</td>
                    <td class="text-right" style="color: #b91c1c; font-weight: 600;">₹${{r.debit.toLocaleString('en-IN', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}</td>
                    <td>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill" style="width: ${{Math.min(r.pct, 100)}}%;"></div>
                        </div>
                        ${{r.pct.toFixed(1)}}%
                    </td>
                    <td class="text-right" style="color: #047857; font-weight: 600;">₹${{r.credit.toLocaleString('en-IN', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}</td>
                    <td class="text-right" style="color: ${{netColor}};">${{netStr}}</td>
                `;
                catTableBody.appendChild(tr);
            }});

            // 8. Render Recurring Payments
            const recTableBody = document.getElementById('recurringTableBody');
            recTableBody.innerHTML = '';
            const recMap = {{}};
            txs.filter(t => t.type === "Debit").forEach(t => {{
                const key = t.narration.toUpperCase().replace("UPI-", "").replace("REV-UPI-", "").split("@")[0].split("-")[0].trim().substring(0, 28);
                if (!recMap[key]) recMap[key] = {{ count: 0, sum: 0 }};
                recMap[key].count += 1;
                recMap[key].sum += t.amount;
            }});

            const minRepeat = monthId === "ALL" ? 4 : 3;
            const recurringVendors = Object.keys(recMap)
                .filter(k => recMap[k].count >= minRepeat)
                .map(k => ({{ key: k, count: recMap[k].count, sum: recMap[k].sum }}))
                .sort((a, b) => b.sum - a.sum).slice(0, 8);

            if (recurringVendors.length > 0) {{
                document.getElementById('recurringCard').style.display = 'block';
                recurringVendors.forEach(r => {{
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><strong>${{r.key}}</strong></td>
                        <td class="text-right"><span class="badge badge-category">${{r.count}} times</span></td>
                        <td class="text-right" style="color: #b91c1c; font-weight: 600;">₹${{r.sum.toLocaleString('en-IN', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}</td>
                    `;
                    recTableBody.appendChild(tr);
                }});
            }} else {{
                document.getElementById('recurringCard').style.display = 'none';
            }}

            // 9. Apply table filter
            applyFilters();
        }}

        // Search & Filter Transactions Table
        function renderTransactionsTable(txList) {{
            const tbody = document.getElementById('txTableBody');
            tbody.innerHTML = '';
            document.getElementById('txCount').innerText = txList.length;

            if (txList.length === 0) {{
                tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No matching transactions found for this search or filter.</td></tr>';
                return;
            }}

            txList.forEach(tx => {{
                const tr = document.createElement('tr');
                const badgeType = tx.type === 'Debit' ? 'badge-debit' : 'badge-credit';
                const amtColor = tx.type === 'Debit' ? '#b91c1c' : '#047857';
                tr.innerHTML = `
                    <td>${{tx.date}}</td>
                    <td><span class="badge badge-bank">${{tx.bank}}</span></td>
                    <td>${{tx.narration}}</td>
                    <td><span class="badge badge-category">${{tx.category}}</span></td>
                    <td><span class="badge ${{badgeType}}">${{tx.type}}</span></td>
                    <td class="text-right" style="color: ${{amtColor}}; font-weight: 600;">₹${{tx.amount.toLocaleString('en-IN', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}</td>
                    <td class="text-right">₹${{tx.closing.toLocaleString('en-IN', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}</td>
                `;
                tbody.appendChild(tr);
            }});
        }}

        function applyFilters() {{
            const search = document.getElementById('searchInput').value.toLowerCase().trim();
            const bank = document.getElementById('bankFilter') ? document.getElementById('bankFilter').value : '';
            const cat = document.getElementById('categoryFilter').value;
            const type = document.getElementById('typeFilter').value;

            const baseTxs = getMonthTransactions(currentSelectedMonth);
            const filtered = baseTxs.filter(tx => {{
                const matchSearch = !search || tx.narration.toLowerCase().includes(search) || tx.date.includes(search) || tx.category.toLowerCase().includes(search) || tx.amount.toString().includes(search) || tx.bank.toLowerCase().includes(search);
                const matchBank = !bank || tx.bank === bank;
                const matchCat = !cat || tx.category === cat;
                const matchType = !type || tx.type === type;
                return matchSearch && matchBank && matchCat && matchType;
            }});

            renderTransactionsTable(filtered);
        }}

        document.getElementById('searchInput').addEventListener('input', applyFilters);
        if (document.getElementById('bankFilter')) {{
            document.getElementById('bankFilter').addEventListener('change', applyFilters);
        }}
        document.getElementById('categoryFilter').addEventListener('change', applyFilters);
        document.getElementById('typeFilter').addEventListener('change', applyFilters);

        // Initial Load (All Months)
        updateDashboard("ALL");
    </script>
</body>
</html>
"""
    output_html_path.write_text(html_content, encoding="utf-8")

