import random
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import select

from database.models import Department, BudgetAllocation, Expenditure
from collectors.base_collector import BaseCollector


class CGACollector(BaseCollector):
    collector_name = "cga_collector"

    def __init__(self, db: Session):
        super().__init__(db)

    def _fetch_pdf(self) -> bytes | None:
        """
        Simulate fetching the monthly accounts PDF from CGA.
        In a real implementation, this would use httpx/playwright to grab the latest file.
        """
        logger.info("CGACollector: Fetching latest monthly expenditure PDF...")
        # Simulating network failure or PDF missing to trigger fallback
        return None

    def _parse_pdf(self, pdf_bytes: bytes) -> list[dict]:
        """
        Extract tabular data using pdfplumber.
        Stubbed out since we rely on fallback simulation for the prototype.
        """
        import pdfplumber
        import io
        
        logger.info("CGACollector: Parsing PDF...")
        results = []
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if not table:
                        continue
                    # Logic to find "J&K" row and map to departments
                    # results.append(...)
        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            
        return results

    def _run_fallback_simulation(self, financial_year: str = "2024-25"):
        """
        Generates realistic month-by-month spending curves for all active departments.
        Govt spending is typically low in Q1/Q2 and spikes in Q4 (Jan-Mar).
        """
        logger.warning("CGACollector: Using Smart Simulation Fallback to generate expenditure data.")
        
        current_month = datetime.now().month
        # Map current month to a fiscal month (April = 1, March = 12)
        fiscal_month = current_month - 3 if current_month >= 4 else current_month + 9
        
        # Get all departments and their allocations
        allocations = (self.db.execute(
            select(Department, BudgetAllocation)
            .join(BudgetAllocation, BudgetAllocation.department_id == Department.id)
            .where(
                Department.is_active.is_(True),
                BudgetAllocation.financial_year == financial_year
            )
        )).all()

        for dept, alloc in allocations:
            total_budget = alloc.budget_estimate
            
            # Check if we already have an entry for this month
            existing = self.db.execute(
                select(Expenditure).where(
                    Expenditure.department_id == dept.id,
                    Expenditure.financial_year == financial_year,
                    Expenditure.month == fiscal_month
                )
            ).scalar_one_or_none()
            
            if existing:
                continue # Already ran for this month

            # Q4 rush factor
            is_q4 = fiscal_month >= 10
            base_monthly = total_budget / 12
            multiplier = random.uniform(1.5, 2.5) if is_q4 else random.uniform(0.5, 1.2)
            
            spent_this_month = int(base_monthly * multiplier)
            
            # Ensure we don't overspend massively (cap at 30% of total in one month)
            spent_this_month = min(spent_this_month, int(total_budget * 0.3))
            
            # Create record
            exp = Expenditure(
                department_id=dept.id,
                financial_year=financial_year,
                month=fiscal_month,
                released_amount=int(spent_this_month * random.uniform(1.0, 1.1)), # Usually release > util
                utilized_amount=spent_this_month,
                source="CGA Simulation",
                snapshot_date=datetime.now(timezone.utc).date()
            )
            self.db.add(exp)
            self._records_inserted += 1
            
        self.db.commit()

    def run_collection(self):
        """Main execution flow called by BaseCollector.run()"""
        pdf_bytes = self._fetch_pdf()
        
        if pdf_bytes:
            self._parse_pdf(pdf_bytes)  # result not stored yet; see todo.md 2.2
            # Logic to insert parsed_data into db
            pass
        else:
            # Fallback to simulation
            self._run_fallback_simulation()
