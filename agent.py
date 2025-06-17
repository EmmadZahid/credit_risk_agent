from google.adk.agents import Agent
import os
import json
from typing import Dict, Any, Optional
from .instructions import (
   COMPANY_APPROVAL_OR_REJECTION_DECISION_INSTRCUTION
)
def get_financial_raw_data_approval_or_rejection_tool() -> Dict[str, any]:
    """
    Reads financial data from a JSON file and parses/prepares it to be used by an agent for approving or rejecting a company.

    Returns:
        dict: A dictionary with the overall status and detailed financial data.

        Example structure:
        {
            "status": "Success" | "Error",
            "data": {
                "companyName": str - The registered name of the company,
                "cr_number": str - The commercial registration number of the company,
                "year": int - The fiscal year the financial data belongs to,
                "netProfit": float - Net income after deducting all expenses and taxes,
                "revenue": float - Total revenue generated during the year,
                "cashFlowFromOperatingActivities": float - Net cash generated or used from operating activities,
                "currentRatio": float - Liquidity ratio measuring the ability to cover short-term liabilities,
                "dscr": float - Debt Service Coverage Ratio indicating ability to service debt,
                "debtRatio": float - Ratio of total liabilities to total assets,
                "netProfitMargin": float - Profitability ratio showing net profit as a percentage of revenue,
                "leverageRatio": float - Degree of financial leverage used by the company,
                "gearingRatio": float - Proportion of debt to equity capital,
                "totalEquity": float - Shareholders' total equity at the end of the year
            }
        }
    """

    # Load your AllCompanies.json file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "qawaem_data.json")

    with open(file_path, "r", encoding="utf-8") as f:
        qawaem_data = json.load(f)

    companies_data = qawaem_data.get("data", [])

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
    return {
        "status":"Success",
        "data": simplified_data
    }

financial_analysis_agent = Agent(
    name="CreditPolicyAgent",
    model="gemini-2.0-flash",
    instruction=COMPANY_APPROVAL_OR_REJECTION_DECISION_INSTRCUTION,
    tools=[
        get_financial_raw_data_approval_or_rejection_tool
    ]
    )

root_agent = financial_analysis_agent