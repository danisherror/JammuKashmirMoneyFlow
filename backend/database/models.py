from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime,
    Boolean, Text, ForeignKey, Enum as SAEnum, JSON, BigInteger, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import false, func
import enum

Base = declarative_base()


# ── Enums ────────────────────────────────────────────────────────────────────

class DivisionType(str, enum.Enum):
    JAMMU = "jammu"
    KASHMIR = "kashmir"
    CENTRAL = "central"          # centrally managed (LG office, etc.)


class SchemeType(str, enum.Enum):
    CSS = "css"                  # Centrally Sponsored Scheme (60:40 split)
    CENTRAL = "central"          # 100% central funding
    UT = "ut"                    # J&K UT's own scheme


class CollectorStatus(str, enum.Enum):
    SUCCESS = "success"        # real rows written, nothing skipped
    PARTIAL = "partial"        # finished, but wrote no rows or skipped some
    NO_SOURCE = "no_source"    # no public, automation-friendly source to collect from
    FAILED = "failed"
    RUNNING = "running"
    SKIPPED = "skipped"


class CAGSeverity(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ── Core Reference Tables ─────────────────────────────────────────────────────

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    code = Column(String(20), unique=True, nullable=False)   # e.g. "PWD", "HEALTH"
    division = Column(SAEnum(DivisionType), nullable=False)
    parent_id = Column(Integer, ForeignKey("departments.id"), index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    parent = relationship("Department", remote_side=[id], back_populates="children")
    children = relationship("Department", back_populates="parent")
    allocations = relationship("BudgetAllocation", back_populates="department")
    expenditures = relationship("Expenditure", back_populates="department")
    schemes = relationship("Scheme", back_populates="department")
    tenders = relationship("Tender", back_populates="department")


class District(Base):
    __tablename__ = "districts"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    code = Column(String(10), unique=True, nullable=False)   # e.g. "JMU", "SGR"
    division = Column(SAEnum(DivisionType), nullable=False)
    population = Column(Integer, nullable=True)              # from census
    area_sqkm = Column(Float, nullable=True)
    is_border_district = Column(Boolean, default=False)      # for BADP tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    scheme_progress = relationship("SchemeProgress", back_populates="district")
    dbt_transfers = relationship("DBTTransfer", back_populates="district")


class Scheme(Base):
    __tablename__ = "schemes"

    id = Column(Integer, primary_key=True)
    name = Column(String(300), nullable=False)
    code = Column(String(50), unique=True, nullable=False)   # e.g. "JJM", "PMAY_G"
    scheme_type = Column(SAEnum(SchemeType), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), index=True, nullable=False)
    total_outlay = Column(BigInteger, nullable=True)         # in lakhs
    start_year = Column(Integer, nullable=True)
    end_year = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    source_url = Column(String(500), nullable=True)          # where data is fetched from
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    department = relationship("Department", back_populates="schemes")
    progress = relationship("SchemeProgress", back_populates="scheme")
    dbt_transfers = relationship("DBTTransfer", back_populates="scheme")


# ── Budget & Expenditure ──────────────────────────────────────────────────────

class BudgetAllocation(Base):
    """
    Annual allocation for each department from Union Budget / J&K Budget.
    Source: jkfinance.nic.in, indiabudget.gov.in
    Updated: Once a year (Feb) + revised estimates (Oct)
    """
    __tablename__ = "budget_allocations"

    id = Column(Integer, primary_key=True)
    department_id = Column(Integer, ForeignKey("departments.id"), index=True, nullable=False)
    financial_year = Column(String(10), index=True, nullable=False)      # "2024-25"
    budget_estimate = Column(BigInteger, nullable=False)     # in lakhs — original allocation
    revised_estimate = Column(BigInteger, nullable=True)     # revised mid-year
    actual_previous_year = Column(BigInteger, nullable=True) # last year's actual spend
    is_capital = Column(Boolean, default=False)              # capital or revenue head
    major_head = Column(String(10), nullable=True)           # accounting code
    source = Column(String(100), default="jkfinance.nic.in")
    # Made-up row from database/demo_data.py (DEMO_MODE=true). Deleted on startup when demo mode is off.
    is_demo = Column(Boolean, nullable=False, default=False, server_default=false(), index=True)
    # The saved source document this row was read from (todo.md 1.4). Required: no fact row without one.
    snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    department = relationship("Department", back_populates="allocations")
    snapshot = relationship("SourceSnapshot")


class Expenditure(Base):
    """
    Monthly actual expenditure per department.
    Source: CGA monthly accounts (cga.nic.in)
    Updated: Monthly on ~25th
    """
    __tablename__ = "expenditures"

    id = Column(Integer, primary_key=True)
    department_id = Column(Integer, ForeignKey("departments.id"), index=True, nullable=False)
    financial_year = Column(String(10), index=True, nullable=False)
    month = Column(Integer, index=True, nullable=False)                  # 1=April, 12=March (Indian FY)
    released_amount = Column(BigInteger, nullable=True)      # Finance Dept released
    utilized_amount = Column(BigInteger, nullable=True)      # Actually spent
    is_capital = Column(Boolean, default=False)
    source = Column(String(100), default="cga.nic.in")
    snapshot_date = Column(Date, index=True, nullable=False)
    # The saved source document this row was read from (todo.md 1.4). Required: no fact row without one.
    snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    department = relationship("Department", back_populates="expenditures")
    snapshot = relationship("SourceSnapshot")


# ── Scheme Progress ───────────────────────────────────────────────────────────

class SchemeProgress(Base):
    """
    Physical + financial progress for each scheme, per district, per snapshot.
    Sources: JJM API, PMAY portal, MGNREGA MIS, PFMS
    Updated: Daily (MGNREGA/JJM) or Weekly (PMAY)
    """
    __tablename__ = "scheme_progress"

    id = Column(Integer, primary_key=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), index=True, nullable=False)
    district_id = Column(Integer, ForeignKey("districts.id"), index=True, nullable=False)
    financial_year = Column(String(10), index=True, nullable=False)

    # Physical targets & achievement (units depend on scheme)
    target_physical = Column(Float, nullable=True)           # e.g. 1000 houses
    achieved_physical = Column(Float, nullable=True)         # e.g. 640 houses built
    physical_unit = Column(String(50), nullable=True)        # "households", "km", "persons"

    # Financial (in lakhs)
    funds_allocated = Column(BigInteger, nullable=True)
    funds_released = Column(BigInteger, nullable=True)
    funds_utilized = Column(BigInteger, nullable=True)

    # Computed gap (filled by gap_calculator processor)
    utilization_pct = Column(Float, nullable=True)           # utilized / allocated * 100
    release_pct = Column(Float, nullable=True)               # released / allocated * 100
    physical_pct = Column(Float, nullable=True)              # achieved / target * 100

    snapshot_date = Column(Date, index=True, nullable=False)
    source = Column(String(100), nullable=True)
    raw_data = Column(JSON, nullable=True)                   # original API response
    # The saved source document this row was read from (todo.md 1.4). Required: no fact row without one.
    snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=False)
    # JJM/MGNREGA read district figures and state fund totals from two documents; this is the fund one.
    funds_snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    scheme = relationship("Scheme", back_populates="progress")
    district = relationship("District", back_populates="scheme_progress")
    snapshot = relationship("SourceSnapshot", foreign_keys=[snapshot_id])
    funds_snapshot = relationship("SourceSnapshot", foreign_keys=[funds_snapshot_id])


# ── Tenders ───────────────────────────────────────────────────────────────────

class Tender(Base):
    """
    All public tenders from jktenders.gov.in
    Updated: Daily
    """
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True)
    tender_ref = Column(String(100), unique=True, nullable=False)  # portal's own ID
    department_id = Column(Integer, ForeignKey("departments.id"), index=True, nullable=True)
    department_name_raw = Column(String(300), nullable=True)       # as-scraped, before mapping
    title = Column(Text, nullable=False)
    estimated_cost = Column(BigInteger, nullable=True)             # in lakhs
    awarded_cost = Column(BigInteger, nullable=True)
    contractor_name = Column(String(300), nullable=True)
    status = Column(String(50), index=True, nullable=True)                     # "active","awarded","cancelled"
    published_date = Column(Date, nullable=True)
    bid_end_date = Column(Date, nullable=True)
    award_date = Column(Date, nullable=True)
    completion_date = Column(Date, nullable=True)
    location = Column(String(200), nullable=True)
    district_id = Column(Integer, ForeignKey("districts.id"), index=True, nullable=True)
    source_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # The saved source document this row was read from (todo.md 1.4). Required: no fact row without one.
    snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=False)

    department = relationship("Department", back_populates="tenders")
    snapshot = relationship("SourceSnapshot")


# ── DBT Transfers ─────────────────────────────────────────────────────────────

class DBTTransfer(Base):
    """
    Direct Benefit Transfer data for J&K — beneficiaries enrolled vs paid.
    Source: dbtbharat.gov.in
    Updated: Daily
    """
    __tablename__ = "dbt_transfers"

    id = Column(Integer, primary_key=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), index=True, nullable=False)
    district_id = Column(Integer, ForeignKey("districts.id"), index=True, nullable=False)
    financial_year = Column(String(10), index=True, nullable=False)

    beneficiaries_enrolled = Column(Integer, nullable=True)
    beneficiaries_paid = Column(Integer, nullable=True)
    transactions_count = Column(Integer, nullable=True)
    amount_transferred = Column(BigInteger, nullable=True)   # in lakhs

    # Last-mile gap (filled by processor)
    last_mile_gap_pct = Column(Float, nullable=True)         # (enrolled - paid) / enrolled * 100

    snapshot_date = Column(Date, index=True, nullable=False)
    source = Column(String(100), default="dbtbharat.gov.in")
    # The saved source document this row was read from (todo.md 1.4). Required: no fact row without one.
    snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    scheme = relationship("Scheme", back_populates="dbt_transfers")
    district = relationship("District", back_populates="dbt_transfers")
    snapshot = relationship("SourceSnapshot")


# ── CAG Findings ──────────────────────────────────────────────────────────────

class CAGFinding(Base):
    """
    Audit findings from CAG reports for J&K.
    Source: cag.gov.in — annual PDFs parsed + Claude-summarized
    Updated: Annually (checked monthly)
    """
    __tablename__ = "cag_findings"

    id = Column(Integer, primary_key=True)
    report_year = Column(Integer, nullable=False)
    report_title = Column(String(500), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), index=True, nullable=True)
    department_name_raw = Column(String(300), nullable=True)

    finding_raw = Column(Text, nullable=False)               # extracted PDF paragraph
    finding_summary = Column(Text, nullable=True)            # Claude-generated summary
    amount_flagged = Column(BigInteger, nullable=True)       # in lakhs
    severity = Column(SAEnum(CAGSeverity), nullable=True)
    paragraph_ref = Column(String(50), nullable=True)        # "Para 3.4"
    page_number = Column(Integer, nullable=True)
    source_pdf_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # The saved source document this row was read from (todo.md 1.4). Required: no fact row without one.
    snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=False)

    snapshot = relationship("SourceSnapshot")


# ── Official documents (PDF) ──────────────────────────────────────────────────

class SourceSnapshot(Base):
    """
    One saved copy of a source document (PDF/HTML/JSON), identified by its SHA-256.
    Rows derived from the document point here so anyone can re-check a figure.
    Written through database.snapshots.save_snapshot; downloadable from GET /api/v1/snapshots/{id}.
    """
    __tablename__ = "source_snapshots"

    id = Column(Integer, primary_key=True)
    source_type = Column(String(50), index=True, nullable=False)    # "appropriation_accounts", "jjm_collector"
    collector_name = Column(String(100), index=True, nullable=True)  # collector or loader that fetched it
    title = Column(String(300), nullable=True)
    source_url = Column(String(500), nullable=False)
    sha256 = Column(String(64), unique=True, nullable=False)
    storage_path = Column(String(500), nullable=False)              # relative to settings.raw_snapshot_dir
    content_type = Column(String(100), nullable=True)
    byte_size = Column(BigInteger, nullable=False)
    fetched_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AppropriationAccountLine(Base):
    """
    One row of the "Summary of Appropriation Accounts" (CAG, audited, annual).
    Amounts are in ₹ THOUSAND exactly as printed — not lakhs like the older tables.
    final_grant is original + supplementary (not the Budget Estimate); expenditure is gross.
    Department is resolved through GrantDepartmentMap, so the mapping can be fixed without reloading.
    """
    __tablename__ = "appropriation_account_lines"
    __table_args__ = (
        UniqueConstraint("financial_year", "grant_no", "section", "kind", name="uq_appropriation_line"),
    )

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=False)
    financial_year = Column(String(10), index=True, nullable=False)
    grant_no = Column(Integer, nullable=False)
    grant_name_raw = Column(String(300), nullable=False)
    section = Column(String(10), nullable=False)                    # "revenue" | "capital"
    kind = Column(String(10), nullable=False)                       # "voted" | "charged"
    final_grant_thousand = Column(BigInteger, nullable=False)
    gross_expenditure_thousand = Column(BigInteger, nullable=False)
    saving_thousand = Column(BigInteger, nullable=False)
    excess_thousand = Column(BigInteger, nullable=False)
    page = Column(Integer, nullable=False)                          # page in the snapshot PDF
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    snapshot = relationship("SourceSnapshot")


# Grant pages of the same PDFs (parsers.appropriation_details), loaded in the same transaction as
# the summary rows above. Amounts are in ₹ THOUSAND; the notes print ₹ lakh, converted exactly.

class AppropriationMajorHead(Base):
    """A major head listed on a grant's pages, per section."""
    __tablename__ = "appropriation_major_heads"
    __table_args__ = (
        UniqueConstraint("financial_year", "grant_no", "section", "code", name="uq_appropriation_major_head"),
    )

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=False)
    financial_year = Column(String(10), index=True, nullable=False)
    grant_no = Column(Integer, nullable=False)
    section = Column(String(10), nullable=False)
    code = Column(String(4), nullable=False)
    name = Column(String(300), nullable=False)
    page = Column(Integer, nullable=False)


class AppropriationSectionBlock(Base):
    """One Voted/Charged block at the top of a grant's pages: original, supplementary, surrendered."""
    __tablename__ = "appropriation_section_blocks"
    __table_args__ = (
        UniqueConstraint("financial_year", "grant_no", "section", "kind", name="uq_appropriation_section_block"),
    )

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=False)
    financial_year = Column(String(10), index=True, nullable=False)
    grant_no = Column(Integer, nullable=False)
    section = Column(String(10), nullable=False)
    kind = Column(String(10), nullable=False)
    original_thousand = Column(BigInteger, nullable=False)
    supplementary_thousand = Column(BigInteger, nullable=False)
    reappropriation_thousand = Column(BigInteger, nullable=False)  # printed only in 2021-22
    final_grant_thousand = Column(BigInteger, nullable=False)
    expenditure_thousand = Column(BigInteger, nullable=False)
    saving_thousand = Column(BigInteger, nullable=False)
    excess_thousand = Column(BigInteger, nullable=False)
    surrendered_thousand = Column(BigInteger, nullable=False)
    page = Column(Integer, nullable=False)


class AppropriationNote(Base):
    """A numbered note under "Notes and Comments", verbatim."""
    __tablename__ = "appropriation_notes"
    __table_args__ = (UniqueConstraint("financial_year", "grant_no", "number", name="uq_appropriation_note"),)

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=False)
    financial_year = Column(String(10), index=True, nullable=False)
    grant_no = Column(Integer, nullable=False)
    section = Column(String(10), nullable=True)
    kind = Column(String(10), nullable=True)
    number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    category = Column(String(30), nullable=False)  # saving | excess | unutilised | ... | comment
    reasons_not_communicated = Column(Boolean, nullable=False)
    page = Column(Integer, nullable=False)


class AppropriationHeadLine(Base):
    """
    One row of a note table: a head below the major head with its O / S / R, total grant, actual,
    saving/excess and the official remark. Amounts the table doesn't print are NULL, not 0.
    A head can sit in more than one note (e.g. excess and unspent supplementary), hence note_number
    in the key.
    """
    __tablename__ = "appropriation_head_lines"
    __table_args__ = (
        UniqueConstraint(
            "financial_year", "grant_no", "section", "kind", "head_code", "note_number",
            name="uq_appropriation_head_line",
        ),
    )

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=False)
    financial_year = Column(String(10), index=True, nullable=False)
    grant_no = Column(Integer, nullable=False)
    section = Column(String(10), nullable=False)
    kind = Column(String(10), nullable=False)
    note_number = Column(Integer, nullable=False)
    category = Column(String(30), nullable=False)
    reasons_not_communicated = Column(Boolean, nullable=False)
    head_code = Column(String(40), nullable=False)        # "2052.090.0099.0431"
    major_head_code = Column(String(4), nullable=False)
    head_name = Column(String(300), nullable=False)       # name of the last level
    head_path = Column(JSON, nullable=False)              # [{"level", "code", "name"}, ...]
    original_thousand = Column(BigInteger, nullable=True)
    supplementary_thousand = Column(BigInteger, nullable=True)
    reappropriation_thousand = Column(BigInteger, nullable=True)
    final_grant_thousand = Column(BigInteger, nullable=True)
    expenditure_thousand = Column(BigInteger, nullable=True)
    saving_thousand = Column(BigInteger, nullable=True)
    excess_thousand = Column(BigInteger, nullable=True)
    remark = Column(Text, nullable=False)
    printed_error = Column(Text, nullable=True)           # figures that don't add up in the PDF itself
    page = Column(Integer, nullable=False)


class AppropriationDocumentIssue(Base):
    """Things the parser kept aside instead of guessing: non-head tables, misfiled rows, footnotes."""
    __tablename__ = "appropriation_document_issues"

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=False)
    financial_year = Column(String(10), index=True, nullable=False)
    kind = Column(String(30), nullable=False)  # skipped_table | misfiled | footnote | headerless_table
    grant_no = Column(Integer, nullable=True)  # from the text's "page P, grant N" prefix
    page = Column(Integer, nullable=True)
    text = Column(Text, nullable=False)


class AppropriationRecovery(Base):
    """
    Appendix II: recoveries adjusted in reduction of expenditure, per grant and section (₹ thousand).
    Not the Budget Estimate of expenditure: these are deducted from gross expenditure to get net
    expenditure (see parsers.appropriation_recoveries). Nil is stored as 0, as printed ("-").
    """
    __tablename__ = "appropriation_recoveries"
    __table_args__ = (
        UniqueConstraint("financial_year", "grant_no", "section", name="uq_appropriation_recovery"),
    )

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("source_snapshots.id"), index=True, nullable=False)
    financial_year = Column(String(10), index=True, nullable=False)
    grant_no = Column(Integer, nullable=False)
    grant_name_raw = Column(String(300), nullable=False)
    section = Column(String(10), nullable=False)
    budget_estimate_thousand = Column(BigInteger, nullable=False)  # estimate of recoveries
    actual_thousand = Column(BigInteger, nullable=False)
    page = Column(Integer, nullable=False)                         # page with the grant name
    actuals_page = Column(Integer, nullable=False)


class GrantDepartmentMap(Base):
    """Which tracker department a numbered grant belongs to, per financial year."""
    __tablename__ = "grant_department_map"
    __table_args__ = (UniqueConstraint("financial_year", "grant_no", name="uq_grant_department"),)

    id = Column(Integer, primary_key=True)
    financial_year = Column(String(10), index=True, nullable=False)
    grant_no = Column(Integer, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), index=True, nullable=False)
    note = Column(Text, nullable=True)

    department = relationship("Department")


# ── Sync / Health Tracking ────────────────────────────────────────────────────

class DataSyncLog(Base):
    """
    Tracks every collector run — success, failure, records updated.
    Used by the /alerts/sync-status endpoint and SyncStatusPanel on frontend.
    """
    __tablename__ = "data_sync_log"

    id = Column(Integer, primary_key=True)
    collector_name = Column(String(100), index=True, nullable=False)     # "mgnrega_collector"
    status = Column(SAEnum(CollectorStatus), index=True, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    records_fetched = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    extra_info = Column(JSON, nullable=True)                 # any collector-specific metadata
