from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime,
    Boolean, Text, ForeignKey, Enum as SAEnum, JSON, BigInteger
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
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
    SUCCESS = "success"
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
    parent_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    children = relationship("Department", backref="parent", foreign_keys=[parent_id])
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
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
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
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    financial_year = Column(String(10), nullable=False)      # "2024-25"
    budget_estimate = Column(BigInteger, nullable=False)     # in lakhs — original allocation
    revised_estimate = Column(BigInteger, nullable=True)     # revised mid-year
    actual_previous_year = Column(BigInteger, nullable=True) # last year's actual spend
    is_capital = Column(Boolean, default=False)              # capital or revenue head
    major_head = Column(String(10), nullable=True)           # accounting code
    source = Column(String(100), default="jkfinance.nic.in")
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    department = relationship("Department", back_populates="allocations")


class Expenditure(Base):
    """
    Monthly actual expenditure per department.
    Source: CGA monthly accounts (cga.nic.in)
    Updated: Monthly on ~25th
    """
    __tablename__ = "expenditures"

    id = Column(Integer, primary_key=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    financial_year = Column(String(10), nullable=False)
    month = Column(Integer, nullable=False)                  # 1=April, 12=March (Indian FY)
    released_amount = Column(BigInteger, nullable=True)      # Finance Dept released
    utilized_amount = Column(BigInteger, nullable=True)      # Actually spent
    is_capital = Column(Boolean, default=False)
    source = Column(String(100), default="cga.nic.in")
    snapshot_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    department = relationship("Department", back_populates="expenditures")


# ── Scheme Progress ───────────────────────────────────────────────────────────

class SchemeProgress(Base):
    """
    Physical + financial progress for each scheme, per district, per snapshot.
    Sources: JJM API, PMAY portal, MGNREGA MIS, PFMS
    Updated: Daily (MGNREGA/JJM) or Weekly (PMAY)
    """
    __tablename__ = "scheme_progress"

    id = Column(Integer, primary_key=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    financial_year = Column(String(10), nullable=False)

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

    snapshot_date = Column(Date, nullable=False)
    source = Column(String(100), nullable=True)
    raw_data = Column(JSON, nullable=True)                   # original API response
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    scheme = relationship("Scheme", back_populates="progress")
    district = relationship("District", back_populates="scheme_progress")


# ── Tenders ───────────────────────────────────────────────────────────────────

class Tender(Base):
    """
    All public tenders from jktenders.gov.in
    Updated: Daily
    """
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True)
    tender_ref = Column(String(100), unique=True, nullable=False)  # portal's own ID
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    department_name_raw = Column(String(300), nullable=True)       # as-scraped, before mapping
    title = Column(Text, nullable=False)
    estimated_cost = Column(BigInteger, nullable=True)             # in lakhs
    awarded_cost = Column(BigInteger, nullable=True)
    contractor_name = Column(String(300), nullable=True)
    status = Column(String(50), nullable=True)                     # "active","awarded","cancelled"
    published_date = Column(Date, nullable=True)
    bid_end_date = Column(Date, nullable=True)
    award_date = Column(Date, nullable=True)
    completion_date = Column(Date, nullable=True)
    location = Column(String(200), nullable=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=True)
    source_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    department = relationship("Department", back_populates="tenders")


# ── DBT Transfers ─────────────────────────────────────────────────────────────

class DBTTransfer(Base):
    """
    Direct Benefit Transfer data for J&K — beneficiaries enrolled vs paid.
    Source: dbtbharat.gov.in
    Updated: Daily
    """
    __tablename__ = "dbt_transfers"

    id = Column(Integer, primary_key=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    financial_year = Column(String(10), nullable=False)

    beneficiaries_enrolled = Column(Integer, nullable=True)
    beneficiaries_paid = Column(Integer, nullable=True)
    transactions_count = Column(Integer, nullable=True)
    amount_transferred = Column(BigInteger, nullable=True)   # in lakhs

    # Last-mile gap (filled by processor)
    last_mile_gap_pct = Column(Float, nullable=True)         # (enrolled - paid) / enrolled * 100

    snapshot_date = Column(Date, nullable=False)
    source = Column(String(100), default="dbtbharat.gov.in")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    scheme = relationship("Scheme", back_populates="dbt_transfers")
    district = relationship("District", back_populates="dbt_transfers")


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
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    department_name_raw = Column(String(300), nullable=True)

    finding_raw = Column(Text, nullable=False)               # extracted PDF paragraph
    finding_summary = Column(Text, nullable=True)            # Claude-generated summary
    amount_flagged = Column(BigInteger, nullable=True)       # in lakhs
    severity = Column(SAEnum(CAGSeverity), nullable=True)
    paragraph_ref = Column(String(50), nullable=True)        # "Para 3.4"
    page_number = Column(Integer, nullable=True)
    source_pdf_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Sync / Health Tracking ────────────────────────────────────────────────────

class DataSyncLog(Base):
    """
    Tracks every collector run — success, failure, records updated.
    Used by the /alerts/sync-status endpoint and SyncStatusPanel on frontend.
    """
    __tablename__ = "data_sync_log"

    id = Column(Integer, primary_key=True)
    collector_name = Column(String(100), nullable=False)     # "mgnrega_collector"
    status = Column(SAEnum(CollectorStatus), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    records_fetched = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    extra_info = Column(JSON, nullable=True)                 # any collector-specific metadata
