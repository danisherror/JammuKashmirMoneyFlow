"""
Export routes — CSV / ZIP download for researchers, journalists, NGOs.
GET /api/v1/export/zip            → Full database ZIP (all CSVs)
GET /api/v1/export/schemes        → All scheme progress as CSV
GET /api/v1/export/districts      → All district-level data as CSV
GET /api/v1/export/tenders        → All tenders as CSV
GET /api/v1/export/dbt            → All DBT transfers as CSV
"""
import csv
import io
import zipfile
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.connection import get_db
from database.models import (
    SchemeProgress, Scheme, District, Department,
    Tender, DBTTransfer, BudgetAllocation, Expenditure,
)

router = APIRouter(prefix="/export", tags=["Export"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    """Return a streaming CSV response from a list of dicts."""
    if not rows:
        output = io.StringIO()
        output.write("no_data\n")
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


async def _scheme_progress_rows(db: AsyncSession, financial_year: str) -> list[dict]:
    rows = (await db.execute(
        select(SchemeProgress, Scheme, District, Department)
        .join(Scheme, SchemeProgress.scheme_id == Scheme.id)
        .join(District, SchemeProgress.district_id == District.id)
        .join(Department, Scheme.department_id == Department.id)
        .where(SchemeProgress.financial_year == financial_year)
        .order_by(SchemeProgress.snapshot_date.desc(), Scheme.name, District.name)
    )).all()

    return [
        {
            "snapshot_date":        sp.snapshot_date,
            "scheme_name":          scheme.name,
            "scheme_code":          scheme.code,
            "scheme_type":          scheme.scheme_type,
            "department":           dept.name,
            "district":             district.name,
            "district_code":        district.code,
            "division":             district.division,
            "financial_year":       sp.financial_year,
            "target_physical":      sp.target_physical,
            "achieved_physical":    sp.achieved_physical,
            "physical_unit":        sp.physical_unit,
            "physical_pct":         sp.physical_pct,
            "funds_allocated_lakh": sp.funds_allocated,
            "funds_released_lakh":  sp.funds_released,
            "funds_utilized_lakh":  sp.funds_utilized,
            "utilization_pct":      sp.utilization_pct,
            "release_pct":          sp.release_pct,
            "source":               sp.source,
        }
        for sp, scheme, district, dept in rows
    ]


async def _tenders_rows(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(
        select(Tender)
        .order_by(Tender.published_date.desc())
    )).scalars().all()

    return [
        {
            "tender_ref":       t.tender_ref,
            "title":            t.title,
            "department":       t.department_name_raw,
            "status":           t.status,
            "estimated_cost_lakh": t.estimated_cost,
            "awarded_cost_lakh":   t.awarded_cost,
            "contractor_name":  t.contractor_name,
            "location":         t.location,
            "published_date":   t.published_date,
            "bid_end_date":     t.bid_end_date,
            "award_date":       t.award_date,
            "source_url":       t.source_url,
        }
        for t in rows
    ]


async def _dbt_rows(db: AsyncSession, financial_year: str) -> list[dict]:
    rows = (await db.execute(
        select(DBTTransfer, Scheme, District)
        .join(Scheme, DBTTransfer.scheme_id == Scheme.id)
        .join(District, DBTTransfer.district_id == District.id)
        .where(DBTTransfer.financial_year == financial_year)
        .order_by(DBTTransfer.snapshot_date.desc())
    )).all()

    return [
        {
            "snapshot_date":            dbt.snapshot_date,
            "scheme_name":              scheme.name,
            "district":                 district.name,
            "financial_year":           dbt.financial_year,
            "beneficiaries_enrolled":   dbt.beneficiaries_enrolled,
            "beneficiaries_paid":       dbt.beneficiaries_paid,
            "transactions_count":       dbt.transactions_count,
            "amount_transferred_lakh":  dbt.amount_transferred,
            "last_mile_gap_pct":        dbt.last_mile_gap_pct,
        }
        for dbt, scheme, district in rows
    ]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/schemes", summary="Export scheme progress as CSV")
async def export_schemes(
    financial_year: str = Query("2024-25"),
    db: AsyncSession = Depends(get_db),
):
    """Download all scheme-district progress data as a clean CSV file."""
    rows = await _scheme_progress_rows(db, financial_year)
    fname = f"jk_scheme_progress_{financial_year.replace('-','_')}.csv"
    return csv_response(rows, fname)


@router.get("/tenders", summary="Export all tenders as CSV")
async def export_tenders(db: AsyncSession = Depends(get_db)):
    """Download all tender data as a clean CSV file."""
    rows = await _tenders_rows(db)
    return csv_response(rows, "jk_tenders.csv")


@router.get("/dbt", summary="Export DBT transfer data as CSV")
async def export_dbt(
    financial_year: str = Query("2024-25"),
    db: AsyncSession = Depends(get_db),
):
    """Download all Direct Benefit Transfer data as a clean CSV file."""
    rows = await _dbt_rows(db, financial_year)
    fname = f"jk_dbt_{financial_year.replace('-','_')}.csv"
    return csv_response(rows, fname)


@router.get("/zip", summary="Export full database as ZIP of CSVs")
async def export_zip(
    financial_year: str = Query("2024-25"),
    db: AsyncSession = Depends(get_db),
):
    """
    Download a ZIP file containing all datasets as individual CSV files.
    Perfect for researchers, journalists, and NGOs.
    """
    scheme_rows  = await _scheme_progress_rows(db, financial_year)
    tender_rows  = await _tenders_rows(db)
    dbt_rows     = await _dbt_rows(db, financial_year)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:

        # README
        readme = f"""J&K Public Money Flow Tracker — Data Export
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
Financial Year: {financial_year}

Files in this archive:
  scheme_progress.csv  — District-wise physical & financial progress for all schemes
  tenders.csv          — All public works tenders from jktenders.gov.in
  dbt_transfers.csv    — Direct Benefit Transfer beneficiary & payment data

Data Sources:
  MGNREGA: nreganarayan.nic.in
  Jal Jeevan Mission: ejalshakti.gov.in
  PM Awas Yojana: pmayg.nic.in
  DBT: dbtbharat.gov.in
  Tenders: jktenders.gov.in

License: Open Data — Attribution required.
"""
        zf.writestr("README.txt", readme)

        def rows_to_csv_str(rows: list[dict]) -> str:
            if not rows:
                return "no_data\n"
            out = io.StringIO()
            w = csv.DictWriter(out, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
            return out.getvalue()

        zf.writestr(f"scheme_progress_{financial_year.replace('-','_')}.csv",
                    rows_to_csv_str(scheme_rows))
        zf.writestr("tenders.csv",        rows_to_csv_str(tender_rows))
        zf.writestr(f"dbt_transfers_{financial_year.replace('-','_')}.csv",
                    rows_to_csv_str(dbt_rows))

    zip_buffer.seek(0)
    ts = date.today().strftime("%Y%m%d")
    filename = f"jk_money_flow_{financial_year.replace('-','_')}_{ts}.zip"

    return StreamingResponse(
        iter([zip_buffer.read()]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/gap-analysis", summary="Export gap analysis as CSV")
async def export_gap_analysis(
    financial_year: str = Query("2024-25"),
    db: AsyncSession = Depends(get_db),
):
    """Download department-level fund gap analysis as CSV."""
    from sqlalchemy import and_, func as sqlfunc
    from database.models import Department, BudgetAllocation, Expenditure, Scheme, SchemeProgress

    rows = (await db.execute(
        select(Department, BudgetAllocation)
        .join(BudgetAllocation, and_(
            BudgetAllocation.department_id == Department.id,
            BudgetAllocation.financial_year == financial_year,
        ))
        .where(Department.is_active == True)
    )).all()

    exp_rows = (await db.execute(
        select(Expenditure.department_id, sqlfunc.sum(Expenditure.utilized_amount).label("total"))
        .where(Expenditure.financial_year == financial_year)
        .group_by(Expenditure.department_id)
    )).all()
    exp_map = {r.department_id: (r.total or 0) for r in exp_rows}

    pfms_rows = (await db.execute(
        select(Scheme.department_id, sqlfunc.sum(SchemeProgress.funds_released).label("total"))
        .join(SchemeProgress, SchemeProgress.scheme_id == Scheme.id)
        .where(SchemeProgress.financial_year == financial_year)
        .group_by(Scheme.department_id)
    )).all()
    pfms_map = {r.department_id: (r.total or 0) for r in pfms_rows}

    output_rows = []
    for dept, alloc in rows:
        utilized = exp_map.get(dept.id, 0)
        budget = alloc.budget_estimate or 0
        released = pfms_map.get(dept.id, 0)
        effective_release = max(released, budget) if released == 0 else released
        gap = effective_release - utilized
        util_pct = round((utilized / budget * 100), 2) if budget > 0 else 0
        output_rows.append({
            "department": dept.name,
            "department_code": dept.code,
            "division": dept.division,
            "financial_year": financial_year,
            "allocated_lakhs": budget,
            "released_lakhs": effective_release,
            "utilized_lakhs": utilized,
            "gap_lakhs": gap,
            "utilization_pct": util_pct,
        })
    output_rows.sort(key=lambda x: x["gap_lakhs"], reverse=True)
    return csv_response(output_rows, f"jk_gap_analysis_{financial_year.replace('-','_')}.csv")


@router.get("/cag-findings", summary="Export CAG audit findings as CSV")
async def export_cag_findings(db: AsyncSession = Depends(get_db)):
    """Download all CAG audit findings as CSV."""
    from database.models import CAGFinding
    from sqlalchemy import desc

    rows = (await db.execute(
        select(CAGFinding).order_by(desc(CAGFinding.report_year), desc(CAGFinding.id))
    )).scalars().all()

    output_rows = [
        {
            "report_year": r.report_year,
            "report_title": r.report_title,
            "department": r.department_name_raw,
            "finding_summary": r.finding_summary,
            "amount_flagged_lakhs": r.amount_flagged,
            "severity": r.severity,
            "paragraph_ref": r.paragraph_ref,
            "source_pdf_url": r.source_pdf_url,
        }
        for r in rows
    ]
    return csv_response(output_rows, "jk_cag_findings.csv")
