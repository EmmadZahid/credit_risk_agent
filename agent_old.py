from google.adk.agents import Agent, LlmAgent, SequentialAgent
import os
import requests
import json # To potentially pretty-print JSON if needed for debugging
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()

    MODEL_NAME = os.environ.get("GOOGLE_GENAI_MODEL", "gemini-2.0-flash")
except ImportError:
    print("Warning: python-dotenv not installed. Ensure API key is set")
    MODEL_NAME = "gemini-2.0-flash"

def get_financial_raw_data_tool(organization_id: str) -> Dict[str, Any]:
    """
    Simulates fetching raw financial data for a given organization ID from an external API.
    In a real scenario, this would make an actual API call.

    Args:
        organization_id: The unique identifier for the organization.

    Returns:
        A dictionary containing raw financial data (revenue, net_income, etc.)
        or an error message if the organization ID is not found.
    """
    # --- SIMULATED DATA ---
    # In a real application, you would make an API call here, e.g.:
    # response = requests.get(f"https://your.financial.api/data/{organization_id}")
    # response.raise_for_status()
    # return response.json()
    # --- END SIMULATED DATA ---

    financial_data_db = {
        "123": {
            "revenue": 1_200_000.0,
            "net_income": 150_000.0,
            "bounced_cheques": 0,
            "debt_to_equity_ratio": 0.3,
            "years_in_business": 7
        },
        "456": {
            "revenue": 400_000.0,
            "net_income": 30_000.0,
            "bounced_cheques": 2,
            "debt_to_equity_ratio": 1.2,
            "years_in_business": 3
        },
        "789": {
            "revenue": 750_000.0,
            "net_income": 80_000.0,
            "bounced_cheques": 1,
            "debt_to_equity_ratio": 0.6,
            "years_in_business": 5
        }
    }

    data = financial_data_db.get(organization_id)
    if data:
        return {"status": "success", "data": data}
    else:
        return {"status": "error", "message": f"Financial data not found for organization ID: {organization_id}"}

def calculate_credit_score_tool(
    revenue: float,
    net_income: float,
    bounced_cheques: int,
    debt_to_equity_ratio: float,
    years_in_business: int
) -> Dict[str, Any]:
    """
    Calculates a credit score and loan recommendation based on financial data.

    Args:
        revenue: Total revenue of the entity.
        net_income: Net income (profit) of the entity.
        bounced_cheques: Number of bounced cheques in the last year.
        debt_to_equity_ratio: The debt-to-equity ratio.
        years_in_business: Number of years the entity has been in business.

    Returns:
        A dictionary containing the credit score, recommendation, and explanation points.
    """
    base_score = 500
    explanation_points = []
    score = base_score

    # Policy for Revenue
    if revenue >= 1_000_000:
        score += 50
        explanation_points.append("Excellent revenue performance.")
    elif revenue >= 500_000:
        score += 20
        explanation_points.append("Good revenue performance.")
    else:
        explanation_points.append("Revenue is moderate.")

    # Policy for Net Income
    if net_income >= 100_000:
        score += 40
        explanation_points.append("Strong net income contributing positively.")
    elif net_income >= 50_000:
        score += 15
        explanation_points.append("Positive net income.")
    else:
        explanation_points.append("Net income is low or negative.")

    # Policy for Bounced Cheques
    if bounced_cheques == 0:
        score += 30
        explanation_points.append("No bounced cheques, indicating good payment discipline.")
    elif bounced_cheques == 1:
        score -= 20
        explanation_points.append("One bounced cheque detected, minor impact on score.")
    elif bounced_cheques > 1:
        score -= 50
        explanation_points.append("Multiple bounced cheques, significantly impacting score negatively.")

    # Policy for Debt-to-Equity Ratio
    if debt_to_equity_ratio < 0.5:
        score += 25
        explanation_points.append("Very low debt-to-equity ratio, indicating financial stability.")
    elif debt_to_equity_ratio >= 0.5 and debt_to_equity_ratio < 1.0:
        score += 10
        explanation_points.append("Moderate debt-to-equity ratio.")
    else:
        explanation_points.append("High debt-to-equity ratio, raising concerns.")

    # Policy for Years in Business
    if years_in_business >= 5:
        score += 20
        explanation_points.append("Long operational history, adding stability.")
    elif years_in_business >= 2:
        score += 10
        explanation_points.append("Established presence in the market.")
    else:
        explanation_points.append("New business, limited operational history.")

    # Determine Recommendation
    recommendation = "Not Recommended"
    if score >= 650:
        recommendation = "Recommended"
    elif score >= 550:
        recommendation = "Review Required"

    return {
        "credit_score": score,
        "recommendation": recommendation,
        "explanation_points": explanation_points
    }

def send_email_tool(recipient_email: str, subject:str, body: str) -> Dict[str, str]:
    """
    Sends an email to the specified recipient.

    Args:
        recipient_email: The email address of the recipient.
        subject: The subject of the email
        body: The plain text body of the email which is the explanation of the credit assessment.

    Returns:
        A dictionary with a status and a message.
    """
    print(f"\n--- Simulating Email Send ---")
    print(f"To: {recipient_email}")
    print(f"Subject: {subject}")
    print(f"Body:\n{body}")
    print(f"--- End Simulation ---\n")
    return {"status": "success", "message": f"Email sent to {recipient_email}."}


credit_risk_assessment_agent = Agent(
    name="CreditRiskAgent",
    model=MODEL_NAME,
    description="An AI agent for assessing credit risk based on financial data and providing loan recommendations.",
    instruction=(
        "You are a Credit Risk Assessment agent. Your primary goal is to evaluate the creditworthiness of an borrower/organization that will be provided by the user "
        "and based on that you will fetch financial data from external API, calculate a credit score, give a clear loan recommendation, "
        "and explain the assessment.\n"
        "Here's the process:\n"
        "1.  **Fetch Financial Data:** Use the `get_financial_raw_data_tool` to fetch the raw financial data in JSON format. "
        "   The user will provide the borrower/organization id that will be passed to this tool to extract the related financial data."
        "2.  **Calculate Credit Score:** Use the `calculate_credit_score_tool` to calculate the credit score, assessment and recommendation. "
        "   `calculate_credit_score_tool` will use the output of `get_financial_raw_data_tool`. Ensure all required parameters are provided to the tool.\n"
        "3.  **Explain Assessment:** Based on the `credit_score`, `recommendation`, and `explanation_points` "
        "   returned by the tool, provide a comprehensive but easy-to-understand explanation to the user. "
        "   Clearly state the calculated score, the recommendation (Recommended, Review Required, Not Recommended), "
        "   and the key factors influencing the decision.\n"
        "4.  **Offer Email Option:** After explaining the assessment, ask the user "
        "   if user wants all this assessment to be sent on email'\n"
        "5.  **Send Email (if requested):** If the user provides an email address, "
        "   call the `send_email_tool`. For the `body` of the email, include the full assessment details "
        "   (score, recommendation, and explanation).\n"
        "   Confirm to the user that the email has been sent or if there was an issue.\n"
        "Always be polite and professional."
    ),
    tools=[
        get_financial_raw_data_tool,
        calculate_credit_score_tool,
        send_email_tool
    ]
)


root_agent = credit_risk_assessment_agent