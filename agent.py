from google.adk.agents import Agent
import os
import json
import smtplib
from email.message import EmailMessage
from typing import Dict, Any, Optional
from .instructions import (
   COMPANY_APPROVAL_OR_REJECTION_DECISION_INSTRCUTION
)

# Load your AllCompanies.json file
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, "qawaem_data.json")

with open(file_path, "r", encoding="utf-8") as f:
    qawaem_data = json.load(f)
    
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
                "organization_id": int - Its the main id. It can be called company id or borrower id or organization id,
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

    companies_data = qawaem_data.get("data", [])

    # Extract simplified data (flattened into text for prompt injection)
    simplified_data = []

    for company in companies_data:
        company_name = company.get("companyName", "Unknown")
        cr_number = company.get("commercialRegistrationNumber", "")
        organization_id = company.get("organizationId", "")
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
                "organization_id": organization_id,
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

def send_email_tool(input: Dict[str, Any]) -> Dict[str, str]:
    """
    Sends an email using MailHog SMTP.

    Args:
        input: {
            "to": str,
            "subject": str,
            "summary_data": dict (required - body is generated from these parameters)
        }

    Returns:
        dict: {"status": "Success" | "Error", "message": str}
    """
    try:
        to_email = input.get("to")
        subject = input.get("subject", "Credit Analysis Result")
        summary_data = input.get("summary_data")
        body = input.get("body")

        if not to_email:
            return {"status": "Error", "message": "Missing 'to' email address."}

        if summary_data:
            body = build_credit_summary_email_body(summary_data)

        if not body:
            return {"status": "Error", "message": "Missing email body or summary data."}

        msg = EmailMessage()
        msg["From"] = "noreply@lendo.local"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP("localhost", 1025) as smtp:
            smtp.send_message(msg)

        return {"status": "Success", "message": f"Email sent to {to_email}"}

    except Exception as e:
        return {"status": "Error", "message": str(e)}
    
def build_credit_summary_email_body(summary_data: Dict[str, Any]) -> str:
    """
    Builds a credit decision email body using dynamic values from summary_data.

    Args:
        summary_data: {
            "companyName": str,
            "crNumber": str,
            "simahScore": int,
            "dpd": str,
            "revenue": str,
            "netProfitMargin": str,
            "dscr": str,
            "bouncedCheques": str,
            "riskRating": str,
            "finalRecommendation": str
        }

    Returns:
        str: Email body as plain text
    """
    return f"""Dear CreditDecision@lendo.sa,

Please find the credit file for Company: {summary_data.get("companyName", "Unknown")} (CR# {summary_data.get("crNumber", "N/A")}). Below is a summary:

🔹 SIMAH Score: {summary_data.get("simahScore", "N/A")}
🔹 DPD: {summary_data.get("dpd", "N/A")}
🔹 Qawaem Revenue: {summary_data.get("revenue", "N/A")}
🔹 Net Profit Margin: {summary_data.get("netProfitMargin", "N/A")}
🔹 DSCR: {summary_data.get("dscr", "N/A")}
🔹 Bounced Cheques: {summary_data.get("bouncedCheques", "N/A")}
🔹 Risk Rating: {summary_data.get("riskRating", "N/A")}
🔹 FINAL RECOMMENDATION: {summary_data.get("finalRecommendation", "N/A")}

Attached: Credit File <TODO: CREATE CREDIT FILE>

Regards,
ADK AGENT
"""

financial_analysis_agent = Agent(
    name="CreditPolicyAgent",
    model="gemini-2.0-flash",
    instruction=COMPANY_APPROVAL_OR_REJECTION_DECISION_INSTRCUTION,
    tools=[
        get_financial_raw_data_approval_or_rejection_tool,
        send_email_tool  # Register the email sending tool
    ]
    )

root_agent = financial_analysis_agent