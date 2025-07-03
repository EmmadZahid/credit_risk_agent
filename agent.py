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
    Loads raw Qawaem JSON data from file.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "qawaem_data.json")

    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    return {
        "status": "Success",
        "data": raw_data.get("data", [])
    }

def apply_rulebook_from_raw(company_data: dict, year: int = 2023) -> dict:
    """
    Applies the rulebook using original Qawaem JSON structure.
    """

    # Find financialStatement for the selected year
    fs_data = next(
        (x for x in company_data.get("financialStatement", [])
         if x.get("year") == year),
        None
    )
    if fs_data is None:
        return {"error": f"No financialStatement found for year {year}"}

    ratios = fs_data.get("ratios", {}).get("financialSpreading", {})
    profit_loss = fs_data.get("profitAndLoss", {})
    equity_data = fs_data.get("equity", {})

    revenue = profit_loss.get("totalRevenue", 0)
    net_profit = profit_loss.get("netProfit", 0)
    dscr = ratios.get("dscr", 0)
    gearing_ratio = ratios.get("gearingRatio", 0)
    leverage_ratio = ratios.get("leverageRatio", 0)
    current_ratio = ratios.get("currentRatio", 0)
    external_debt_sales = ratios.get("externalDebtSalesRatio", 0)
    total_equity = equity_data.get("totalEquity", 0)

    # Gather credit flags
    all_flags = []
    for section in ["commercial", "consumer"]:
        rules = company_data.get(section, {}).get("rules", [])
        for rule in rules:
            all_flags.append(rule.get("flag"))

    credit_history_green = all(f == "GREEN" or f is None for f in all_flags)

    rules = {
        "Revenue > 1M": revenue > 1_000_000,
        "Operating Profit > 0": net_profit > 0,
        "DSCR ≥ 1.5": dscr >= 1.5,
        "Gearing Ratio ≤ 1.7": gearing_ratio <= 1.7,
        "Leverage Ratio ≤ 2.0": leverage_ratio <= 2.0,
        "Current Ratio ≥ 1.2": current_ratio >= 1.2,
        "External Debt/Sales < 50%": external_debt_sales < 0.5,
        "Total Equity > 100,000": total_equity > 100_000,
        "Credit History Green": credit_history_green,
    }

    met_rules = [k for k, v in rules.items() if v]
    failed_rules = [k for k, v in rules.items() if not v]
    percent_met = (len(met_rules) / len(rules)) * 100

    if not credit_history_green:
        final_recommendation = "❌ Not Recommended"
    elif percent_met >= 60:
        final_recommendation = "✅ Recommended, Credit officer needs to evaluate some of the ratios."
    else:
        final_recommendation = "❌ Not Recommended"

    return {
        "organization_id": company_data.get("organizationId"),
        "companyName": company_data.get("companyName"),
        "cr_number": company_data.get("commercialRegistrationNumber"),
        "met_rules": met_rules,
        "failed_rules": failed_rules,
        "percent_met": round(percent_met, 2),
        "final_recommendation": final_recommendation,
        "data_used": {
            "revenue": revenue,
            "net_profit": net_profit,
            "dscr": dscr,
            "gearing_ratio": gearing_ratio,
            "leverage_ratio": leverage_ratio,
            "current_ratio": current_ratio,
            "external_debt_sales": external_debt_sales,
            "total_equity": total_equity,
            "credit_history_green": credit_history_green,
        }
    }

def calculate_scorecard_from_raw(company_data: dict, year: int = 2023) -> dict:
    """
    Computes scorecard using raw JSON structure.
    """

    # Fetch financials
    fs_data = next(
        (x for x in company_data.get("financialStatement", [])
         if x.get("year") == year),
        None
    )
    if fs_data is None:
        return {"error": f"No financialStatement found for year {year}"}

    ratios = fs_data.get("ratios", {}).get("financialSpreading", {})
    profit_loss = fs_data.get("profitAndLoss", {})
    bms = company_data.get("bms", {})

    # Years in business
    def years_in_business(date_str):
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return (datetime.now() - dt).days / 365.25
        except:
            return None

    years = years_in_business(bms.get("yearsInBusiness"))
    if years is None:
        years_score = 0
        years_value = "Unknown"
    elif years < 3:
        if ratios.get("npmGrowth", 0) > 0:
            years_score = 1.4
        else:
            years_score = -1
        years_value = f"{years:.1f} years"
    elif 3 <= years < 10:
        years_score = 3
        years_value = f"{years:.1f} years"
    else:
        years_score = 4
        years_value = f"{years:.1f} years"

    # Example: only a few scores for brevity
    nitaqat_map = {
        "Red": -4,
        "Yellow": -2,
        "Green": 0,
        "Low Green": 0,
        "Platinum": 2
    }
    nitaqat_score = nitaqat_map.get(bms.get("nitaqatColor", "Unknown"), 0)

    revenue_growth = ratios.get("revenueGrowth", 0)
    revenue_growth_score = (
        4 if revenue_growth > 30 else
        3 if 5 <= revenue_growth <= 30 else
        1 if revenue_growth < 5 else
        -2 if revenue_growth > 10 else
        -1
    )

    gpm_growth = ratios.get("gpmGrowth",0)

    gpm_score = (
        -3   if gpm_growth > -20 else
        -1.5 if  gpm_growth <= -20 else
        0.75 if gpm_growth > 3 else
        2.25 if 3 <= gpm_growth <= 20 else
        3 if gpm_growth > 20 else
        0
    )

    npm = ratios.get("netProfitMargin",0)

    npm_score = (
        -6   if npm < 0 else
        -0.75 if  npm < 5 else
        1.5 if 5 < npm < 15 else
        3 if npm > 15 else
        0
    )

    npm_growth = ratios.get("npmGrowth",0)

    npm_growth_score = (
        -3   if npm_growth > -20 else
        -1.5 if  npm_growth < -20 else
        0.75 if  npm_growth < 3 else
        2.25 if 3 < npm_growth < 20 else
        3 if npm_growth > 20 else
        0
    )

    cashFlowFromOperatingActivities = ratios.get("cashFlowFromOperatingActivities",0)

    cashFlowFromOperatingActivities_score = (
        -2   if cashFlowFromOperatingActivities < 0 else
         2   if cashFlowFromOperatingActivities > 0 else
         0 
    )

    # Minimal table for demonstration
    scorecard_table = [
        {"rule": "Years in Business", "value": years_value, "score": years_score},
        {"rule": "Nitaqat Color", "value": bms.get("nitaqatColor"), "score": nitaqat_score},
        {"rule": "Revenue Growth", "value": revenue_growth, "score": revenue_growth_score},
        {"rule": "GPM Growth", "value": gpm_growth, "score": gpm_score},
        {"rule": "NPM", "value": npm, "score": npm_score},
        {"rule": "NPM Growth", "value": gpm_growth, "score": npm_growth_score},
        {"rule": "CashFlow From Operating Activities", "value": cashFlowFromOperatingActivities, "score": cashFlowFromOperatingActivities_score}
    ]

    total_score = round(sum(x["score"] for x in scorecard_table), 2)

    if total_score >= 90:
        grade = "A+"
    elif total_score >= 70:
        grade = "A"
    elif total_score >= 60:
        grade = "B"
    elif total_score >= 50:
        grade = "C"
    elif total_score >= 40:
        grade = "D"
    else:
        grade = "R"

    return {
        "scorecard_table": scorecard_table,
        "total_score": total_score,
        "grade": grade
    }

def analyze_company(input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs analysis on raw Qawaem data.
    """

    data_response = Lendo_Credit_Decision_Engine()
    if data_response.get("status") != "Success":
        return {"status": "Error", "message": "Failed to load financial data."}

    all_companies = data_response.get("data", [])
    results = []

    for company_data in all_companies:
        if input.get("organization_id") and str(company_data["organizationId"]) != str(input["organization_id"]):
            continue

        rulebook_result = apply_rulebook_from_raw(company_data)
        scorecard_result = calculate_scorecard_from_raw(company_data)

        justification = f"""
Company: {company_data.get('companyName')}
CR#: {company_data.get('commercialRegistrationNumber')}

✅ Met Rules:
{', '.join(rulebook_result['met_rules'])}

❌ Failed Rules:
{', '.join(rulebook_result['failed_rules'])}

Financial Data Used:
{json.dumps(rulebook_result['data_used'], indent=2)}

Scorecard:
{json.dumps(scorecard_result, indent=2)}
"""

        summary_data = {
            "companyName": company_data.get("companyName"),
            "crNumber": company_data.get("commercialRegistrationNumber"),
            "simahScore": scorecard_result.get("total_score"),
            "dpd": str(company_data.get("commercial", {}).get("dpd_commercial")),
            "revenue": str(rulebook_result["data_used"]["revenue"]),
            "netProfitMargin": str(rulebook_result["data_used"]["net_profit"]),
            "dscr": str(rulebook_result["data_used"]["dscr"]),
            "bouncedCheques": str(company_data.get("commercial", {}).get("bounced_cheque_commercial")),
            "riskRating": rulebook_result["final_recommendation"],
            "finalRecommendation": rulebook_result["final_recommendation"],
        }

        result = {
            "companyName": company_data.get("companyName"),
            "organization_id": company_data.get("organizationId"),
            "cr_number": company_data.get("commercialRegistrationNumber"),
            "year": company_data.get("financialStatement", [{}])[0].get("year"),
            "final_recommendation": rulebook_result["final_recommendation"],
            "score": scorecard_result["total_score"],
            "grade": scorecard_result["grade"],
            "met_rules": rulebook_result["met_rules"],
            "failed_rules": rulebook_result["failed_rules"],
            "justification": justification.strip(),
            "summary_data": summary_data,
            "pdf_data": summary_data,
        }
        results.append(result)

    if not results:
        return {"status": "Error", "message": "No matching companies found."}

    return results[0] if len(results) == 1 else {"status": "Success", "results": results}


def CreateDoc(input: Dict[str, Any]) -> Dict[str, str]:
    """
    Creates the credit file for email.

    Args:
        input: {
            "pdf_data": dict
        }

    Returns:
        dict: {"status": "Success" | "Error", "message": str}
    """
    try:
        pdf_data = input.get("pdf_data")
        if pdf_data is None:
            return {"status": "Error", "message": "Missing pdf_data for file creation."}

        pdf_data["score"] = str(pdf_data.get("score", ""))
        pdf_data["grade"] = str(pdf_data.get("grade", ""))
        create_lendo_credit_file(output_data=pdf_data)
        return {"status": "Success", "message": "Credit file created successfully."}

    except subprocess.CalledProcessError as e:
        return {"status": "Error", "message": f"Failed to run generate-credit-file.py: {e}"}
    except Exception as e:
        return {"status": "Error", "message": str(e)}

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
        pdf_data = input.get("pdf_data")

        if not to_email:
            return {"status": "Error", "message": "Missing 'to' email address."}

        if summary_data:
            body = build_credit_summary_email_body(summary_data)

        if not body:
            return {"status": "Error", "message": "Missing email body or summary data."}

        # Step 1: Generate credit file directly
        #create_lendo_credit_file(output_data=pdf_data)

        # Step 2: Locate the generated file
        file_name = "Lendo Credit File - ADK AGENT.docx"
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
        #with smtplib.SMTP("localhost", 1025) as smtp:
        #    smtp.send_message(msg)

        # Step 5: Send email with sendgrid
        SMTP_SERVER = "smtp.sendgrid.net"
        SMTP_PORT = 587
        SMTP_USERNAME = "apikey"  # literally the word 'apikey'
        SMTP_PASSWORD = "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"  # replace with your actual SendGrid API key

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
        Lendo_Credit_Decision_Engine, 
        analyze_company,
        #Send_Email, 
        #CreateDoc
    ]
    )

# init agent
root_agent = financial_analysis_agent