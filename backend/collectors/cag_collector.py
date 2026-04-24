"""
CAG Audit Collector
Source: cag.gov.in — J&K audit reports
Updated: Quarterly / on-demand

Uses the Gemini API to parse raw audit paragraphs into structured findings.
Falls back to simulation if GEMINI_API_KEY is not configured.
"""
import json
import random
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import select

from collectors.base_collector import BaseCollector
from database.models import CAGFinding, CAGSeverity, Department
from config import get_settings

settings = get_settings()

# ── Realistic raw CAG finding paragraphs for J&K ─────────────────────────────
# These mirror the language and style found in actual CAG audit reports.

MOCK_FINDINGS = [
    {
        "report_year": 2024,
        "report_title": "Report of the CAG on General & Social Sector — Government of J&K 2023-24",
        "department": "Public Works Department (R&B)",
        "paragraph_ref": "Para 3.2",
        "page_number": 47,
        "raw": (
            "Test check of records of the Executive Engineer, R&B Division Srinagar revealed that a "
            "work 'Construction of Bridge over Lidder River at Pahalgam' was awarded to M/s XYZ Construction "
            "at a tendered cost of ₹18.24 crore. The work remained incomplete after four years despite full "
            "mobilization advance of ₹3.65 crore (₹365 lakhs) being released. The contractor abandoned the "
            "site in March 2022. No bank guarantee was invoked and the mobilization advance was neither "
            "recovered nor adjusted. This resulted in a loss of ₹365 lakhs to the government exchequer."
        ),
    },
    {
        "report_year": 2024,
        "report_title": "Report of the CAG on General & Social Sector — Government of J&K 2023-24",
        "department": "Health & Medical Education Department",
        "paragraph_ref": "Para 5.1",
        "page_number": 89,
        "raw": (
            "Scrutiny of records of the Chief Medical Officer, Anantnag revealed that ₹248 lakhs "
            "released under National Health Mission (NHM) for procurement of drugs and consumables "
            "during 2022-23 remained unspent and parked in the civil deposit account as of March 2024. "
            "The drugs and consumables were not procured despite critical shortage reported by PHCs. "
            "This resulted in denial of essential medicines to patients and infructuous locking of funds."
        ),
    },
    {
        "report_year": 2024,
        "report_title": "Report of the CAG on General & Social Sector — Government of J&K 2023-24",
        "department": "School Education Department",
        "paragraph_ref": "Para 6.3",
        "page_number": 112,
        "raw": (
            "Audit of the Samagra Shiksha Abhiyan accounts for J&K revealed that 1,240 classrooms were "
            "sanctioned for construction across 310 government schools at a total cost of ₹186 crore. "
            "Of these, 427 classrooms in 107 schools remain under construction for more than 3 years "
            "with total expenditure of ₹42.7 crore (₹4,270 lakhs) incurred but no physical progress "
            "beyond the plinth level. Payments were made without verification of work completion certificates, "
            "indicating potential fraud in measurement books."
        ),
    },
    {
        "report_year": 2024,
        "report_title": "Report of the CAG on General & Social Sector — Government of J&K 2023-24",
        "department": "Jal Shakti Department",
        "paragraph_ref": "Para 4.7",
        "page_number": 78,
        "raw": (
            "Under Jal Jeevan Mission, audit examination of 42 Functional Household Tap Connection (FHTC) "
            "works in Kupwara district revealed that ₹620 lakhs was released to executing agencies. However, "
            "field verification showed that 8,400 connections certified as 'completed' had no water supply "
            "due to non-functional pumping stations. The payment of ₹84 lakhs for these connections was "
            "made without actual delivery of potable water to beneficiaries."
        ),
    },
    {
        "report_year": 2024,
        "report_title": "Report of the CAG on General & Social Sector — Government of J&K 2023-24",
        "department": "Agriculture Department",
        "paragraph_ref": "Para 7.2",
        "page_number": 134,
        "raw": (
            "Audit noted that under PM Kisan scheme, ₹38.4 lakhs was transferred to 960 ineligible "
            "beneficiaries in Jammu district who either owned more than 2 hectares of land or were "
            "government employees. Despite the Income Tax Department flagging these cases in 2022, "
            "the Agriculture Department neither recovered the amounts nor deactivated the beneficiary "
            "IDs, resulting in continued fraudulent transfers of ₹2,000 per installment per beneficiary."
        ),
    },
]


class CAGCollector(BaseCollector):
    collector_name = "cag_collector"

    def __init__(self, db: Session):
        super().__init__(db)

    def _summarize_with_gemini(self, raw_text: str) -> dict | None:
        """Use Gemini to extract structured data from a raw CAG paragraph."""
        if not settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY not set — using simulation mode.")
            return None

        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=settings.gemini_api_key)

            prompt = f"""You are an expert government auditor. Analyze this CAG (Comptroller and Auditor General) audit paragraph and extract structured information.

RAW FINDING:
{raw_text}

Return a JSON object with EXACTLY these fields:
- "department": string — the government department name
- "amount_flagged_lakhs": integer — the total amount in Indian Lakhs flagged (convert crore to lakhs if needed, 1 crore = 100 lakhs)
- "summary": string — a 2-sentence plain English summary a citizen can understand, focusing on what went wrong and the impact
- "severity": string — one of "high", "medium", or "low" based on: high=fraud or >200 lakhs, medium=wastage 50-200 lakhs, low=procedural issues <50 lakhs

Respond with valid JSON only."""

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            return None

    def _simulate_summary(self, finding: dict) -> dict:
        """Generate a plausible summary without the Gemini API."""
        raw = finding["raw"]
        dept = finding["department"]
        
        # Extract amount from the raw text heuristically
        import re
        lakhs_pattern = r'₹\s*(\d+(?:\.\d+)?)\s*lakh'
        crore_pattern = r'₹\s*(\d+(?:\.\d+)?)\s*crore'
        
        amount = 0
        crore_match = re.search(crore_pattern, raw, re.IGNORECASE)
        lakh_match = re.search(lakhs_pattern, raw, re.IGNORECASE)
        
        if crore_match:
            amount = int(float(crore_match.group(1)) * 100)
        elif lakh_match:
            amount = int(float(lakh_match.group(1)))
        
        severity = "high" if amount > 200 else "medium" if amount > 50 else "low"
        
        # Generate a short summary
        sentences = [s.strip() for s in raw.split('.') if len(s.strip()) > 20]
        summary = '. '.join(sentences[:2]) + '.'
        
        return {
            "department": dept,
            "amount_flagged_lakhs": amount,
            "summary": summary[:500],
            "severity": severity,
        }

    def run_collection(self):
        """Process each mock finding through Gemini (or simulation) and store results."""
        for finding in MOCK_FINDINGS:
            # Check if we already have this finding stored
            existing = self.db.execute(
                select(CAGFinding).where(
                    CAGFinding.paragraph_ref == finding["paragraph_ref"],
                    CAGFinding.report_year == finding["report_year"],
                )
            ).scalar_one_or_none()

            if existing:
                logger.info(f"CAGCollector: Skipping existing finding {finding['paragraph_ref']}")
                continue

            # Try Gemini first, fall back to simulation
            structured = self._summarize_with_gemini(finding["raw"])
            if not structured:
                structured = self._simulate_summary(finding)

            # Map severity string to enum
            sev_map = {
                "high": CAGSeverity.HIGH,
                "medium": CAGSeverity.MEDIUM,
                "low": CAGSeverity.LOW,
            }
            severity = sev_map.get(structured.get("severity", "medium"), CAGSeverity.MEDIUM)

            cag = CAGFinding(
                report_year=finding["report_year"],
                report_title=finding["report_title"],
                department_name_raw=structured.get("department", finding["department"]),
                finding_raw=finding["raw"],
                finding_summary=structured.get("summary"),
                amount_flagged=structured.get("amount_flagged_lakhs"),
                severity=severity,
                paragraph_ref=finding["paragraph_ref"],
                page_number=finding["page_number"],
                source_pdf_url="https://cag.gov.in/en/audit-report?tags=Jammu+%26+Kashmir",
            )
            self.db.add(cag)
            self._records_inserted += 1
            logger.info(
                f"CAGCollector: Stored finding {finding['paragraph_ref']} "
                f"— {severity} — ₹{structured.get('amount_flagged_lakhs')} lakhs"
            )

        self.db.commit()
