from google.adk.agents import Agent
import os
import json

# Load your AllCompanies.json file
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, "qawaem_data.json")

with open(file_path, "r", encoding="utf-8") as f:
    all_data = json.load(f)

companies_data = all_data.get("data", [])

# Extract simplified data (flattened into text for prompt injection)
simplified_data = []

for company in companies_data:
    company_name = company.get("companyName", "Unknown")
    cr_number = company.get("commercialRegistrationNumber", "")
    financial_statements = company.get("financialStatement", [])

    for yearly_data in financial_statements:
        year = yearly_data.get("year", "")
        ratios = yearly_data.get("ratios", {})
        spreading = ratios.get("financialSpreading", {})
        profit_loss = yearly_data.get("profitAndLoss", {})
        cashflow = yearly_data.get("cashflow", {})

        simplified_data.append({
            "companyName": company_name,
            "cr_number": cr_number,
            "year": year,
            "netProfit": profit_loss.get("netProfit", 0),
            "revenue": profit_loss.get("totalRevenue", 0),
            "cashFlowFromOperatingActivities": cashflow.get("netCashFlowsFromUsedInOperatingActivities", 0),
            "currentRatio": spreading.get("currentRatio", 0),
            "dscr": spreading.get("dscr", 0),
            "debtRatio": spreading.get("debtRatio", 0),
            "netProfitMargin": spreading.get("netProfitMargin", 0),
            "leverageRatio": spreading.get("leverageRatio", 0),
            "gearingRatio": spreading.get("gearingRatio", 0),
            "totalEquity": yearly_data.get("totalEquity",0)
        })

# Convert data to string for full prompt injection
data_context = json.dumps(simplified_data, indent=2)

# Now build your credit policy agent with your full rulebook embedded
financial_analysis_agent = Agent(
    name="CreditPolicyAgent",
    model="gemini-2.0-flash",
    instruction=f"""
You are a credit decision agent. You must analyze financial data and strictly follow these credit approval rules.

RULEBOOK:
- Turnover: Revenue must exceed SAR 1,000,000 — Reject if not met.
- Operating Profit: Must be positive — Reject if loss.
- Credit History (Company & Owner): No 30+ dpd, no more than 5 bounced cheques ≤ 250K, no unsettled defaults or court cases — Reject if violated.
- DSCR: Asset Light ≥ 1.75, Asset Heavy ≥ 1.5 — Reject if below.
- Gearing Ratio: Asset Light ≤ 1.5, Asset Heavy ≤ 1.7 — Reject if exceeded.
- Leverage Ratio: Asset Light ≤ 1.75, Asset Heavy ≤ 2.0 — Reject if exceeded.
- Current Ratio: Asset Light ≥ 1.5, Asset Heavy ≥ 1.2 — Reject if below.
- External Debt/Sales: Asset Light < 40%, Asset Heavy < 50% — Reject if exceeded.
- Total Equity: Must exceed SAR 100,000 — Reject if not met.

You must apply these rules to each company, analyze the financial data, and clearly state for each company:

- Company Name
- Approved or Rejected
- Reasons for approval or rejection (rule by rule)
- Full justification

Here is the financial data you will use:

{data_context}
"""
)

root_agent = financial_analysis_agent