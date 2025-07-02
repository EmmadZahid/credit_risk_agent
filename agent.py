import os
import json
import smtplib
import subprocess
from google.adk.agents import Agent
from email.message import EmailMessage
from typing import Dict, Any, Optional
from .generate_credit_file import create_lendo_credit_file
from .instructions import (
   COMPANY_APPROVAL_OR_REJECTION_DECISION_INSTRCUTION
)

# Load your AllCompanies.json file
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, "qawaem_data.json")

with open(file_path, "r", encoding="utf-8") as f:
    qawaem_data = json.load(f)
    
def Lendo_Credit_Decision_Engine() -> Dict[str, any]:
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
                "totalEquity": float - Shareholders' total equity at the end of the year,
       
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
        consumer = company.get("consumer",{})
        commercial = company.get("commercial",{})
        bms = company.get("bms",{});
              
        dpd_commercial = None
        dpd_commercial_flag = None
        bounced_cheque_commercial = None
        bounced_cheque_commercial_flag = None
        unsettled_commercial = None
        unsettled_commercial_flag = None
        court_cases_commercial = None
        court_cases_commercial_flag = None

         # Handle commercial rules extraction
        if commercial and "rules" in commercial:
            for commercial_rule_data in commercial["rules"]:
                param_name = commercial_rule_data.get("parameterName")

                if param_name == "30-dpd on existing facilities":
                    dpd_commercial = commercial_rule_data.get("parameterValue")
                    dpd_commercial_flag = commercial_rule_data.get("flag")

                elif param_name == "Bounced Cheques":
                    bounced_cheque_commercial = commercial_rule_data.get("parameterValue")
                    bounced_cheque_commercial_flag = commercial_rule_data.get("flag")

                elif param_name == "Unsettled Defaults":
                    unsettled_commercial = commercial_rule_data.get("parameterValue")
                    unsettled_commercial_flag = commercial_rule_data.get("flag")

                elif param_name == "Outstanding Court Cases":
                    court_cases_commercial = commercial_rule_data.get("parameterValue")
                    court_cases_commercial_flag = commercial_rule_data.get("flag")

            dpd_consumer = None   
            dpd_consumer_flag = None
            bounced_cheque_consumer = None
            bounced_cheque_consumer_flag = None
            unsettled_consumer = None
            unsettled_consumer_flag = None
            court_cases_consumer = None
            court_cases_consumer_flag = None
        
        if consumer and "rules" in consumer:
            for consumer_rule_data in consumer["rules"]:
                param_name = consumer_rule_data.get("parameterName")

                if param_name == "30-dpd on existing facilities":
                    dpd_consumer = consumer_rule_data.get("parameterValue")
                    dpd_consumer_flag = consumer_rule_data.get("flag")

                elif param_name == "Bounced Cheques":
                    bounced_cheque_consumer = consumer_rule_data.get("parameterValue")
                    bounced_cheque_consumer_flag = consumer_rule_data.get("flag")

                elif param_name == "Unsettled Defaults":
                    unsettled_consumer = consumer_rule_data.get("parameterValue")
                    unsettled_consumer_flag = consumer_rule_data.get("flag")

                elif param_name == "Outstanding Court Cases":
                    court_cases_consumer = consumer_rule_data.get("parameterValue")
                    court_cases_consumer_flag = consumer_rule_data.get("flag")

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
                "qawaem": {"netProfit": profit_loss.get("netProfit", 0),
                "revenue": profit_loss.get("totalRevenue", 0),
                "cashFlowFromOperatingActivities": cashflow.get("netCashFlowsFromUsedInOperatingActivities", 0),
                "currentRatio": spreading.get("currentRatio", 0),
                "dscr": spreading.get("dscr", 0),
                "debtRatio": spreading.get("debtRatio", 0),
                "netProfitMargin": spreading.get("netProfitMargin", 0),
                "netProfitMarginGrowth":spreading.get("npmGrowth", 0),
                "grossProfitMargin": spreading.get("grossProfitMargin", 0),
                "grossProfitMarginGrowth":spreading.get("gpmGrowth", 0),
                "leverageRatio": spreading.get("leverageRatio", 0),
                "gearingRatio": spreading.get("gearingRatio", 0),
                "totalEquity": yearly_data.get("totalEquity",0),
                "revenueGrowth":spreading.get("revenueGrowth", 0),
                "interestCoverage": spreading.get("interestCoverage", 0),
                "externalDebtSales": spreading.get("externalDebtSalesRatio", 0),
                "receivablePercentageSales": spreading.get("receivablePercentageSales", 0),
                "daysSalesOutstanding": spreading.get("daysSalesOutstanding", 0),

                },
                "commercial":{
                "dpd_commercial": dpd_commercial,
                "dpd_commercial_flag": dpd_commercial_flag,
                "bounced_cheque_commercial": bounced_cheque_commercial,
                "bounced_cheque_commercial_flag": bounced_cheque_commercial_flag,
                "unsettled_commercial": unsettled_commercial,
                "unsettled_commercial_flag": unsettled_commercial_flag,
                "court_cases_commercial": court_cases_commercial,
                "court_cases_commercial_flag" : court_cases_commercial_flag,
                },
                "consumer":{
                "dpd_consumer": dpd_consumer,
                "dpd_consumer_flag": dpd_consumer_flag,
                "bounced_cheque_consumer": bounced_cheque_consumer,
                "bounced_cheque_consumer_flag": bounced_cheque_consumer_flag,
                "unsettled_consumer": unsettled_consumer,
                "unsettled_consumer_flag": unsettled_consumer_flag,
                "court_cases_consumer": court_cases_consumer,
                "court_cases_consumer_flag" : court_cases_consumer_flag
                },
                "bms":{
                    "nitaqatColor": "Low Green",
                    "yearsInBusiness": "2016-03-18",
                    "market": "Local Market (Including GCC)", 
                    "industry": "Information & Communication, Arts & Recreation",
                    "typeOfCustomer": "Govt. & Semi Govt. Entities, and well-known Corporation",
                    "customerConcentration": bms.get("customerConcentration",0),
                    "changeInOwnership": "No",
                    "changeInManagement": "No",
                    "breachInFinancialCovenant": "No",
                    "delayedAfs": "No"
                }
            })
    return {
        "status":"Success",
        "data": simplified_data
    }

def Send_Email(input: Dict[str, Any]) -> Dict[str, str]:
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

        if not to_email:
            return {"status": "Error", "message": "Missing 'to' email address."}

        if summary_data:
            body = build_credit_summary_email_body(summary_data)

        if not body:
            return {"status": "Error", "message": "Missing email body or summary data."}

        # Step 1: Generate credit file directly
        file_name = f"Lendo Credit File - {summary_data.get("crNumber", "N/A")}.docx"
        create_lendo_credit_file(summary_data, file_name)

        # Step 2: Locate the generated file
        if not os.path.exists(file_name):
            return {"status": "Error", "message": f"File '{file_name}' not found after generation."}

        # Step 3: Create email message
        msg = EmailMessage()
        msg["From"] = "imran.shafqat@lendo.sa"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        # Step 4: Attach the Word file
        with open(file_name, "rb") as f:
            file_data = f.read()
            msg.add_attachment(
                file_data,
                maintype="application",
                subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename=file_name
            )

        # Step 5: Send email with local mailhog docker
        # with smtplib.SMTP("localhost", 1025) as smtp:
        #    smtp.send_message(msg)

        # Step 5: Send email with sendgrid
        SMTP_SERVER = "smtp.sendgrid.net"
        SMTP_PORT = 587
        SMTP_USERNAME = "apikey"  # literally the word 'apikey'
        SMTP_PASSWORD = "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"  # replace with your actual SendGrid API key
        
        # Send email now
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()  # upgrade the connection to secure
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(msg)

        return {"status": "Success", "message": f"Email sent to {to_email}"}

    except subprocess.CalledProcessError as e:
        return {"status": "Error", "message": f"Failed to run generate-credit-file.py: {e}"}
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
            "finalRecommendation": str,
            "finalDecision": str
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
📌 Final Recommendation: {summary_data.get("finalRecommendation", "N/A")}

Attached: Credit File

Regards,
ADK AGENT
"""

# Agent config
financial_analysis_agent = Agent(
    name="CreditPolicyAgent",
    model="gemini-2.0-flash",
    instruction=COMPANY_APPROVAL_OR_REJECTION_DECISION_INSTRCUTION,
    tools=[
        Lendo_Credit_Decision_Engine, # Register the main decisioning tool
        Send_Email # Register the email sending tool
    ]
    )

# init agent
root_agent = financial_analysis_agent