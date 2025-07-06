import os
import json
import smtplib
import subprocess
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from email.message import EmailMessage
from typing import Dict, Any, Optional
from .generate_credit_file import create_lendo_credit_file
from datetime import datetime
from .instructions import (
   COMPANY_APPROVAL_OR_REJECTION_DECISION_INSTRCUTION
)

def years_in_business(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return round((datetime.now() - dt).days / 365.25, 1)
    except:
        return None

def load_file(fileName: str, folderName: str = '') -> Dict[str, Any]:
    """
    Loads a JSON file given a folder and file name (without extension).
    
    Args:
        folderName: Name of the folder containing the file.
        fileName: Name of the JSON file (without `.json` extension).
    
    Returns:
        Parsed JSON data (from the "data" field), or empty list if not found.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, folderName, f"{fileName}.json")

    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    
    return raw_data.get("data", [])

all_companies = load_file("qawaem_data")

def financial_data_analysis_tool(borrower_id: str, year: int) -> Dict[str, any]:
    """
    Retrieves financial data of company for any anyalysis.
    Gives reasons of the analysis. Also it can explain the financial data relate questions.

    ARGS:
        borrower_id: This is the company id that will be provided by the user
    
    Returns:
        - analysis: this is the dictionary of whole analysis 
        - scorecard: this is the scorecard and all its details
        - company_data: This is the raw data of company. It can be used to answer some deep questions
    """
    for company_data in all_companies:
        if borrower_id and str(company_data["organizationId"]) == str(borrower_id):
            break

    analysis = analyze_company(company_data, year)
    scoring = calculate_scorecard(company_data, year)
    return {
        "analysis": analysis,
        "scorecard": scoring,
        "company_data": company_data
    }

def apply_rulebook(company_data: dict, year:int) -> dict:
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
    
    bms = load_file(f"BR{company_data.get("organizationId")}", "bms")

    inc_date_str = bms["smeLegalInformation"]["crIssueDateGregorian"]
    years_in_business_value = years_in_business(inc_date_str)

    rules = {
        "Years in business > 2": years_in_business_value > 2,
        "Revenue > 1M": revenue > 1_000_000,
        "Net Profit > 0": net_profit > 0,
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
            "years_in_business_value":years_in_business_value,
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

def calculate_scorecard(company_data: dict, year:int) -> dict:
    """
    Calculates the credit risk score and risk grade of company using company_data. It will apply some rules to calculate the score and grade.

        - if score is between 90 to 100, give grade A+
        - if score is between 70 to 89.99, give grade A
        - if score is between 60 to 69.99, give grade B
        - if score is between 50 to 59.99, give grade C
        - if score is between 40 to 49.99, give grade D
        - if score is between 0 to 39.99, give grade R 
    Args:
        company_data: This is the all financial data of a single company. 
        year: This is the year of financial data for which analysis is required. If year is not provided by user, then use the latest financialStatement year from the data.

    Returns:
        A dictionary containing the score and grade and score table.
            credit_score: The total score or credit risk score
            grade: The grade calculated from score
            score_table: The table that has the rule name, value from data and assigned value for that rule
    """

    bms = load_file(f"BR{company_data.get("organizationId")}", "bms")

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
   # bms = company_data.get("bms", {})

    inc_date_str = bms["smeLegalInformation"]["crIssueDateGregorian"]
    years_in_business_value = years_in_business(inc_date_str)

    years_in_business_score = (
    -1 if years_in_business_value < 3 else
    1.4 if years_in_business_value == 3 else
    3 if 3 < years_in_business_value <10 else
    4 if years_in_business_value >=10  else
    None
    )

    nitaqat_value = bms["otherInformation"]["nitaqatColor"]
    nitaqat_score = (
        -4 if nitaqat_value == "Red" or nitaqat_value =="Very Small Red" else
        -2 if nitaqat_value == "Yellow" else
        0 if nitaqat_value == "Green" or nitaqat_value == "Low Green" or nitaqat_value == "High Green" else
        2 if nitaqat_value == "Platinum" else
        None
    )

    revenue_growth = ratios.get("revenueGrowth", 0)
    revenue_growth_score = (
        4 if revenue_growth > 30 else
        3 if 5 <= revenue_growth <= 30 else
        1 if revenue_growth < 5 else
        -2 if revenue_growth > 10 else
        None
    )

    gpm_growth = ratios.get("gpmGrowth",0)

    gpm_score = (
        -3   if gpm_growth > -20 else
        -1.5 if  gpm_growth <= -20 else
        0.75 if gpm_growth > 3 else
        2.25 if 3 <= gpm_growth <= 20 else
        3 if gpm_growth > 20 else
        None
    )

    npm = ratios.get("netProfitMargin",0)

    npm_score = (
        -6   if npm < 0 else
        -0.75 if  npm < 5 else
        1.5 if 5 < npm < 15 else
        3 if npm > 15 else
        None
    )

    npm_growth = ratios.get("npmGrowth",0)

    npm_growth_score = (
        -3   if npm_growth > -20 else
        -1.5 if  npm_growth < -20 else
        0.75 if  npm_growth < 3 else
        2.25 if 3 < npm_growth < 20 else
        3 if npm_growth > 20 else
        None
    )

    cashFlowFromOperatingActivities = ratios.get("cashFlowFromOperatingActivities",0)

    cashFlowFromOperatingActivities_score = (
        -2   if cashFlowFromOperatingActivities < 0 else
         2   if cashFlowFromOperatingActivities > 0 else
         None 
    )

    current_ratio = ratios.get("currentRatio",0)

    current_ratio_score = (
        -2   if current_ratio < 1 else
        1.5 if  1 < current_ratio < 4 else
        2 if  current_ratio < 4 else
        None
    )

    leverage_ratio = ratios.get("leverageRatio",0)

    leverage_ratio_score = (
        -2   if current_ratio < 1 else
        1 if  1 < current_ratio < 2 else
        2 if  current_ratio > 2 else
        None
    )

    interest_coverage_ratio = ratios.get("interestCoverage",0)

    interest_coverage_ratio_score = (
        -2 if interest_coverage_ratio < 1 else
         2  if interest_coverage_ratio >  4 else
         1.5  if 1 < interest_coverage_ratio < 4 else
         None
    )

    dso_ratio = ratios.get("daysSalesOutstanding",0)

    dso_ratio_score = (
        -2 if dso_ratio > 270 else
        -1 if 180 < dso_ratio < 270 else
         0 if 120 < dso_ratio < 180 else
         2 if dso_ratio < 120 else
         None
    )

    receivables_ratio = ratios.get("receivablePercentageSales",0)

    receivables_ratio_score = (
        -2 if receivables_ratio > 100 else
        -1 if 70 < receivables_ratio < 100  else
         0 if 50 < receivables_ratio < 70 else
         2 if receivables_ratio < 50 else
         None
    )

    external_sales_debt_ratio = ratios.get("externalDebtSalesRatio",0)

    external_sales_debt_ratio_score = (
        -1  if external_sales_debt_ratio > 50 else
         0  if 25 < external_sales_debt_ratio < 50 else
         2  if external_sales_debt_ratio < 25 else
         None
    )

    dscr_ratio = ratios.get("dscr",0)

    dscr_ratio_score = (
        -2 if dscr_ratio < 1 else
         2  if dscr_ratio >  2 else
         1  if 1 < dscr_ratio < 2 else
         None
    )

    change_in_ownership = "No"

    change_in_ownership_score = (
        1 if change_in_ownership == "No" else
        0.9 if change_in_ownership == "Yes" else
        None
    )

    change_in_management = "No"

    change_in_management_score = (
        1 if   change_in_management == "No" else
        0.9 if change_in_management == "Yes" else
        None
    )

    breach_financial_covenants = "No"

    breach_financial_covenants_score = (
        1 if   breach_financial_covenants == "No" else
        0.9 if breach_financial_covenants == "Yes" else
        None
    )

    delayed_afs = "No"

    delayed_afs_score = (
        1 if   delayed_afs == "No" else
        0.9 if delayed_afs == "Yes" else
        None
    )

    legal_structure = "Company 100% owned by Locals (ultimately)"

    legal_structure_score = (
    -1.5 if legal_structure == "Sole Proprietorship / One Person Company (local / foreign investment)" else
    -1.5 if legal_structure == "Non-Saudi Company" else
     0   if legal_structure == "Foreign Investment (Saudi Company 100% owned by foreign)" else
     3   if legal_structure == "Mixed ownership (Local & Foreign)" else
     4.5 if legal_structure == "Company 100% owned by Locals (ultimately)" else
     6   if legal_structure == "Public Listed" else
     None
    )

    succession_risk = "Complementary management by partners and/or experienced team"

    succession_risk_score = (
    -1.25 if succession_risk == "Sole Proprietorship with no second line involved in business" else
     1.25 if succession_risk == "Sole Proprietorship / experienced second line involved in business" else
     2.5  if succession_risk == "Company managed only by one of the partners" else
     5    if succession_risk == "Complementary management by partners and/or experienced team" else
     None
    )

    owners_experience = "Experience in different field of business (> 5 years)"
    owners_experience_score = (
    -1.25 if owners_experience == "No Experience" else
     1.25 if owners_experience == "Experience in different field of business (< 5 years)" else
     2.5  if owners_experience == "Experience in different field of business (> 5 years)" else
     3.75 if owners_experience == "Experience in same / related field (< 5 years)" else
     5    if owners_experience == "Experience in same / related field (> 5 years)" else
     None
    )

    management_experience = "Managed by an experienced team (with Co. for > 3 years)"

    management_experience_score = (
     3    if management_experience == "Managed by Owner(s)" else
     1.5  if management_experience == "Managed by an experienced team (with Co. for < 3 years)" else
     3    if management_experience == "Managed by an experienced team (with Co. for > 3 years)" else
     None
    )

    credit_history = "At least 1 loan fully settled w/ regular repayment and clean records"

    credit_history_score = (
    -3    if credit_history == "Irregular (Defaults, Past dues, Write off, Court cases)" else
     0    if credit_history == "No credit history with clean records (or report is not obtained)" else
     4.5  if credit_history == "O/s Financing w/ regular repayment and clean records (no full settlement)" else
     6    if credit_history == "At least 1 loan fully settled w/ regular repayment and clean records" else
     None
    )

    netaqat_value = "Green"

    netaqat_score = (
        -4 if netaqat_value == "Red" else
        -2 if netaqat_value == "Yellow" else
        0 if netaqat_value == "Green" else
        2 if netaqat_value == "Platinum" else
        None
    )

    market_value = "Local market (including GCC)"
    
    market_score = (
        -1.5 if market_value == ">25% of sales for high-risk countries" else
        1.5 if market_value == ">25% of sales for other countries (excluding GCC)" else
        3 if market_value == "Local market (including GCC)" else
        None
    )

    industry_value = "Agriculture, Forestry and Fishing"

    industry_score = (
        2 if any(keyword in industry_value for keyword in ["Water supply", "waste mgmt", "defense", "other services", "households"]) else
        3.5 if any(keyword in industry_value for keyword in ["Agriculture", "Forestry", "Manufacturing", "Transport", "Real Estate"]) else
        5 if any(keyword in industry_value for keyword in ["Health", "Retail", "Motor Repair"]) else
        6 if any(keyword in industry_value for keyword in ["Mining", "Utilities", "Food", "Finance", "Education", "Prof. Services"]) else
        7 if any(keyword in industry_value for keyword in ["Information", "Communication", "Arts", "Recreation"]) else
        None
    )

    type_of_customers_value = "Govt. & Semi Govt. Entities, and well-known Corporation"

    type_of_customers_score = (
        2 if type_of_customers_value == "Consumers or unknown entities" else
        3 if type_of_customers_value == "Well-known Corporations (Public listed and/or closed)" else
        3.6 if type_of_customers_value == "Govt. & Semi Govt. Entities, and well-known Corporation" else
        4 if type_of_customers_value == "Govt. & Semi Govt. Entities" else
        None
    )

    customers_concentration_value ="6 to <20 Customers"

    customers_concentration_score = (
        1.25 if customers_concentration_value == "<=5 Customers" else
        3.75 if customers_concentration_value == "6 to <20 Customers" else
        5 if customers_concentration_value == "20 Customers or more" else
        None
    )

    inventory_liquidity_value = "Ready for sale w/ proper management system"

    inventory_liquidity_score = (
        -3 if inventory_liquidity_value == "Inventory liquidity/management is concerning" else
        3 if inventory_liquidity_value == "N.A. (Low inventory or service industry)" else
        1.5 if inventory_liquidity_value == "Liquidity/management uncertain" else
        3 if inventory_liquidity_value == "Ready for sale w/ proper management system" else
        None
    )

    access_to_fund_value = "Proven support from owners/related parties"

    access_to_fund_score = (
        0 if access_to_fund_value == "No access" else
        1 if access_to_fund_value == "Proven access to FI" else
        2 if access_to_fund_value == "Proven support from owners/related parties" else
        None
    )

    relationship_with_lendo  = "No Relationship"

    relationship_with_lendo_score = (
        1 if relationship_with_lendo == "No Relationship" else
        0.75 if relationship_with_lendo == "Frequent PDs, unsatisfactory relationship" else
        1.05 if relationship_with_lendo == "Satisfactory relationship with some PDs" else
        1.15 if relationship_with_lendo == "Satisfactory relationship with timely repayments" else
        None
    )

    control_over_cashflow = "Full Control (AACP, noncancellable standing order, etc.)"
    control_over_cashflow_score = (
        1.25 if control_over_cashflow == "Full Control (AACP, noncancellable standing order, etc.)" else
        1.05 if control_over_cashflow == "Partial control (cancelled by third party)" else
        1.01 if control_over_cashflow == "Partial control (cancelled by client)" else
        1.15 if control_over_cashflow == "Satisfactory relationship with timely repayments" else
        1.15 if control_over_cashflow == "No Control" else
        None
    )



    results = {
    f"{prefix}_{suffix}": next(
        (
            r.get("parameterValue") if suffix == "value" else r.get("flag")
            for r in company_data.get(section, {}).get("rules", [])
            if r.get("parameterName") == param_name
        ),
        None,
    )
    for section, param_name, prefix, suffix in [
        ("commercial", "Bounced Cheques", "bcc", "value"),
        ("commercial", "Bounced Cheques", "bcc", "flag"),
        ("consumer", "Bounced Cheques", "bccs", "value"),
        ("consumer", "Bounced Cheques", "bccs", "flag"),
        ("commercial", "Outstanding Court Cases", "ccc", "value"),
        ("commercial", "Outstanding Court Cases", "ccc", "flag"),
        ("consumer", "Outstanding Court Cases", "cccs", "value"),
        ("consumer", "Outstanding Court Cases", "cccs", "flag"),
    ]
}

 
    bcc_flag = results["bcc_flag"]
    bccs_flag = results["bccs_flag"]
    ccc_flag = results["ccc_flag"]
    cccs_flag = results["cccs_flag"]

    returned_cheques_score = None
    
    returned_cheques_score = (
    -3 if (bcc_flag in ("GREEN", None) and
          bccs_flag in ("GREEN", None) and
          ccc_flag in ("RED", None) and
          cccs_flag in ("RED", None)) else
    3 if (bcc_flag == "GREEN" or bccs_flag == "GREEN") and
         (ccc_flag == "GREEN" or cccs_flag == "GREEN") else
   -1.5 if (bcc_flag == "RED" or bccs_flag == "RED") and
           (ccc_flag == "GREEN" and cccs_flag == "GREEN") else
    0
    )

    dpd_value = int(company_data["commercial"].get("dpd_commercial", 0) or 0)
    dpd_commercial_flag = company_data["commercial"].get("dpd_commercial_flag")
    dpd_consumer_flag = company_data["consumer"].get("dpd_consumer_flag")
    
    unsettled_commercial_flag = company_data["commercial"].get("unsettled_commercial_flag")
    unsettled_consumer_flag = company_data["consumer"].get("unsettled_consumer_flag")

    results = {
    f"{prefix}_{suffix}": next(
        (
            r.get("parameterValue") if suffix == "value" else r.get("flag")
            for r in company_data.get(section, {}).get("rules", [])
            if r.get("parameterName") == param_name
        ),
        None,
    )
    for section, param_name, prefix, suffix in [
        ("commercial", "30-dpd on existing facilities", "dpd", "value"),
        ("consumer", "30-dpd on existing facilities", "dpd", "value"),
    ]
}

    defaults_pd_score = (
        -35 if dpd_value > 90 else
        -14 if 30 <= dpd_value <= 90 else
        -7 if 1 <= dpd_value < 30 else
        7 if (years_in_business_value and years_in_business_value > 2) else
        0
    )

    all_flags = [
        dpd_commercial_flag,
        dpd_consumer_flag,
        unsettled_commercial_flag,
        unsettled_consumer_flag,
        bcc_flag,
        bccs_flag,
        ccc_flag,
        cccs_flag,
    ]

    # Check if any flag is RED
    has_red_flags = any(flag == "RED" for flag in all_flags)

    scorecard_table = [
        {"rule": "Nitaqat Color", "value": nitaqat_value, "score": nitaqat_score},
        {"rule": "Revenue Growth", "value": revenue_growth, "score": revenue_growth_score},
        {"rule": "GPM Growth", "value": gpm_growth, "score": gpm_score},
        {"rule": "NPM", "value": npm, "score": npm_score},
        {"rule": "NPM Growth", "value": npm_growth, "score": npm_growth_score},
        {"rule": "CashFlow From Operating Activities", "value": cashFlowFromOperatingActivities, "score": cashFlowFromOperatingActivities_score},
        {"rule": "Current Ratio", "value": current_ratio, "score": current_ratio_score},
        {"rule": "Leverage Ratio", "value": leverage_ratio, "score": leverage_ratio_score},
        {"rule": "Interest Coverage", "value": interest_coverage_ratio, "score": interest_coverage_ratio_score},
        {"rule": "DSR Ratio", "value": dscr_ratio, "score": dscr_ratio_score},
        {"rule": "Receivables Ratio", "value": receivables_ratio, "score": receivables_ratio_score},
        {"rule": "External Sales Ratio", "value": external_sales_debt_ratio, "score": external_sales_debt_ratio_score},
        {"rule": "Change in Ownership", "value": change_in_ownership_score, "score": change_in_ownership_score},
        {"rule": "Change in Management", "value": change_in_management, "score": change_in_management_score},
        {"rule": "Breach in Financial Covenants", "value": breach_financial_covenants, "score": breach_financial_covenants_score},
        {"rule": "Delayed AFS", "value": delayed_afs, "score": delayed_afs_score},
        {"rule": "Succession Risk ", "value": succession_risk, "score": succession_risk_score},
        {"rule": "Owner Experience", "value": owners_experience, "score": owners_experience_score},
        {"rule": "Management Experience", "value": management_experience, "score": management_experience_score},
        {"rule": "Credit History", "value": credit_history, "score": credit_history_score},
        {"rule": "Years in Business Value", "value": years_in_business_value, "score": years_in_business_score},
        {"rule": "Market Value", "value": market_value, "score": market_score},
        {"rule": "Industry", "value": industry_value, "score": industry_score},
        {"rule": "Type of Customer", "value": type_of_customers_value, "score": type_of_customers_score},
        {"rule": "Customer Concenteration", "value": customers_concentration_value, "score": customers_concentration_score},
        {"rule": "Inventory Liquidity Management", "value": inventory_liquidity_value, "score": inventory_liquidity_score},
        {"rule": "Access to Additional Fund", "value": access_to_fund_value, "score": access_to_fund_score},
        {"rule": "Relationship with Lendo", "value": relationship_with_lendo, "score": relationship_with_lendo_score},
        {"rule": "Access to Additional Fund", "value": access_to_fund_value, "score": access_to_fund_score},
        {"rule": "Control over Cash Flow", "value": control_over_cashflow, "score": control_over_cashflow_score},
        {"rule": "Return Cheque Score", "value": f"BCC:{bcc_flag}, BCCS:{bccs_flag}, CCC:{ccc_flag}, CCCS:{cccs_flag}", "score": returned_cheques_score},
        {"rule": "Defaults / PDs","value": f"Has RED Flags: {has_red_flags}, Years in Business: {years_in_business_value}","score": defaults_pd_score}
    ]

    credit_score = round(sum(x["score"] if x["score"] is not None else 0 for x in scorecard_table), 2)

    if credit_score >= 90:
        grade = "A+"
    elif credit_score >= 70:
        grade = "A"
    elif credit_score >= 60:
        grade = "B"
    elif credit_score >= 50:
        grade = "C"
    elif credit_score >= 40:
        grade = "D"
    else:
        grade = "R"

    return {
        "scorecard_table": scorecard_table,
        "credit_score": credit_score,
        "grade": grade
    }

def analyze_company(company_data:Dict[str, any], year:int) -> Dict[str, Any]:
    """
    Runs analysis on raw data.

    Args:
        company_data: This is the all financial data of a single company. 
        year: This is the year of financial data for which analysis is required. If year is not provided by user, then use the latest financialStatement year from the data.

    Returns:
        A dictionary with the analysis results.
    """

    rulebook_result = apply_rulebook(company_data, year)

    summary_data = {
        "companyName": company_data.get("companyName"),
        "crNumber": company_data.get("commercialRegistrationNumber"),
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
        "year": year,
        "final_recommendation": rulebook_result["final_recommendation"],
        "met_rules": rulebook_result["met_rules"],
        "failed_rules": rulebook_result["failed_rules"],
        "summary_data": summary_data
    }

    return result





def send_email_tool(input: Dict[str, Any]) -> Dict[str, str]:
    """
    Sends an email using MailHog SMTP.

    Args:
        input: {
            "companyId": number (like 1742, 4560, 2140 OR 1901)
            "to": str (email address to send email to),
            "subject": str (email subject),
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
        file_name = f"Lendo Credit File - {summary_data.get('crNumber', 'N/A')}.docx"

        create_lendo_credit_file(input.get("companyId"), summary_data, file_name)

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
        with smtplib.SMTP("localhost", 1025) as smtp:
           smtp.send_message(msg)

        # Step 5: Send email with sendgrid
        # SMTP_SERVER = "smtp.sendgrid.net"
        # SMTP_PORT = 587
        # SMTP_USERNAME = "apikey"  # literally the word 'apikey'
        # SMTP_PASSWORD = os.getenv("EMAIL_API_KEY")

        # Error handling if the api key is missing
        # if not SMTP_PASSWORD:
        #     raise EnvironmentError("❌ EMAIL_API_KEY environment variable is missing or not set.")
        # else:
        #     print("✅ EMAIL_API_KEY loaded successfully.")
        
        # Send email now
        # with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        #     smtp.starttls()  # upgrade the connection to secure
        #     smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        #     smtp.send_message(msg)

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

root_agent = Agent(
    model=os.environ.get("GOOGLE_GENAI_MODEL"),
    name="CrediRiskAgent",
    description="An agent that analyze the financial data",
    instruction="""
    You are credit risk financial agent that will answer to user quesitons.
    User can ask you about analyzing or recommendation of the company.
    
    You have to format the response for recommendation as below. The financial values e.g. revenue, net profit etc. are in SAR:
    - **Company Name**
    - **Year**
    - **Recommendation**
    - **Met Rules** in table view with values
    - **Failed Rules** in table view with values
    - **Credit Score**
    - **Grade**
    - **Score card** in table view
    - **Justificaiton**

    Also user can ask some more details about your analysis and the data.
    IF user has not provided you the company id second time, use the previous one and do same for year
    Answer him professionally.

    User can ask to send email by providing the email address. If the user provides an email address, call the `send_email_tool` with a `summary_data` object including:
        - companyName
        - crNumber
        - simahScore: "send the total score calculated in this parameter from `credit_score` score step"
        - dpd
        - revenue
        - netProfitMargin
        - dscr
        - bouncedCheques
        - riskRating: "send the grade calculated in this parameter from `grade` in score step. The possible value could be A, B, C etc."
        - finalRecommendation: "✅ Recommend for financing" or "❌ Not Recommend for financing"
        - finalDecision: "send the `Final Decision` string you created here but don't add emoji at start of string, remove emoji and send english sentense only"
    The `send_email_tool` will automatically generate the email body.
    Inform the user whether the email was successfully sent or if there was an error.
    """,
    tools=[financial_data_analysis_tool, send_email_tool]
)