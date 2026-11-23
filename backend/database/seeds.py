"""
Static reference data for J&K money flow tracker.
Departments, Districts, and Schemes that don't change with scrapes.
Budget allocations are not seeded here: the old figures had no citation (the 2023-24 ones were
"scaled down by ~10% for demonstration"), so they now live in database/demo_data.py and load only
with DEMO_MODE=true.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import (
    Department, District, Scheme, DivisionType, SchemeType, GrantDepartmentMap,
)


# ── Departments ───────────────────────────────────────────────────────────────

DEPARTMENTS = [
    {"name": "Public Works Department (Roads & Buildings)", "code": "PWD",        "division": DivisionType.CENTRAL},
    {"name": "Health & Medical Education",                  "code": "HEALTH",     "division": DivisionType.CENTRAL},
    {"name": "School Education",                            "code": "SCHOOLEDU",  "division": DivisionType.CENTRAL},
    {"name": "Higher Education",                            "code": "HIGHEREDU",  "division": DivisionType.CENTRAL},
    {"name": "Jal Shakti (PHE)",                            "code": "JALSHAKTI",  "division": DivisionType.CENTRAL},
    {"name": "Power Development Department",                "code": "PDD",        "division": DivisionType.CENTRAL},
    {"name": "Agriculture Production Department",           "code": "AGRI",       "division": DivisionType.CENTRAL},
    {"name": "Horticulture Department",                     "code": "HORTI",      "division": DivisionType.CENTRAL},
    {"name": "Rural Development & Panchayati Raj",          "code": "RDPR",       "division": DivisionType.CENTRAL},
    {"name": "Urban Local Bodies",                          "code": "ULB",        "division": DivisionType.CENTRAL},
    {"name": "Social Welfare Department",                   "code": "SOCIALWEL",  "division": DivisionType.CENTRAL},
    {"name": "Police & Home Department",                    "code": "POLICE",     "division": DivisionType.CENTRAL},
    {"name": "Revenue Department",                          "code": "REVENUE",    "division": DivisionType.CENTRAL},
    {"name": "Industries & Commerce",                       "code": "INDUSTRIES", "division": DivisionType.CENTRAL},
    {"name": "Tourism Department",                          "code": "TOURISM",    "division": DivisionType.CENTRAL},
    {"name": "Forest Department",                           "code": "FOREST",     "division": DivisionType.CENTRAL},
    {"name": "Finance Department",                          "code": "FINANCE",    "division": DivisionType.CENTRAL},
    {"name": "General Administration Department",           "code": "GAD",        "division": DivisionType.CENTRAL},
    {"name": "Labour & Employment",                         "code": "LABOUR",     "division": DivisionType.CENTRAL},
    {"name": "Animal & Sheep Husbandry",                    "code": "ANIMAL",     "division": DivisionType.CENTRAL},
]

# ── Districts ─────────────────────────────────────────────────────────────────

DISTRICTS = [
    # Jammu Division
    {"name": "Jammu",      "code": "JMU", "division": DivisionType.JAMMU,   "population": 1529958, "area_sqkm": 3097,  "is_border": False},
    {"name": "Samba",      "code": "SMB", "division": DivisionType.JAMMU,   "population": 318898,  "area_sqkm": 904,   "is_border": True},
    {"name": "Kathua",     "code": "KTH", "division": DivisionType.JAMMU,   "population": 616435,  "area_sqkm": 2651,  "is_border": True},
    {"name": "Udhampur",   "code": "UDH", "division": DivisionType.JAMMU,   "population": 555357,  "area_sqkm": 2639,  "is_border": False},
    {"name": "Reasi",      "code": "RSI", "division": DivisionType.JAMMU,   "population": 314667,  "area_sqkm": 1719,  "is_border": False},
    {"name": "Rajouri",    "code": "RJR", "division": DivisionType.JAMMU,   "population": 619266,  "area_sqkm": 2630,  "is_border": True},
    {"name": "Poonch",     "code": "PNC", "division": DivisionType.JAMMU,   "population": 476820,  "area_sqkm": 1674,  "is_border": True},
    {"name": "Doda",       "code": "DDA", "division": DivisionType.JAMMU,   "population": 409576,  "area_sqkm": 8912,  "is_border": False},
    {"name": "Kishtwar",   "code": "KWT", "division": DivisionType.JAMMU,   "population": 230696,  "area_sqkm": 4036,  "is_border": False},
    {"name": "Ramban",     "code": "RMB", "division": DivisionType.JAMMU,   "population": 283713,  "area_sqkm": 1329,  "is_border": False},
    # Kashmir Division
    {"name": "Srinagar",   "code": "SGR", "division": DivisionType.KASHMIR, "population": 1192792, "area_sqkm": 2228,  "is_border": False},
    {"name": "Budgam",     "code": "BDG", "division": DivisionType.KASHMIR, "population": 753745,  "area_sqkm": 1371,  "is_border": False},
    {"name": "Anantnag",   "code": "ANN", "division": DivisionType.KASHMIR, "population": 1078692, "area_sqkm": 3574,  "is_border": False},
    {"name": "Kulgam",     "code": "KLG", "division": DivisionType.KASHMIR, "population": 422786,  "area_sqkm": 2237,  "is_border": False},
    {"name": "Pulwama",    "code": "PWM", "division": DivisionType.KASHMIR, "population": 570060,  "area_sqkm": 1398,  "is_border": False},
    {"name": "Shopian",    "code": "SPN", "division": DivisionType.KASHMIR, "population": 265960,  "area_sqkm": 515,   "is_border": False},
    {"name": "Baramulla",  "code": "BRM", "division": DivisionType.KASHMIR, "population": 1015503, "area_sqkm": 4588,  "is_border": True},
    {"name": "Bandipora",  "code": "BNP", "division": DivisionType.KASHMIR, "population": 392232,  "area_sqkm": 398,   "is_border": True},
    {"name": "Kupwara",    "code": "KPW", "division": DivisionType.KASHMIR, "population": 870354,  "area_sqkm": 2379,  "is_border": True},
    {"name": "Ganderbal",  "code": "GNB", "division": DivisionType.KASHMIR, "population": 297003,  "area_sqkm": 259,   "is_border": False},
]


# ── Schemes ───────────────────────────────────────────────────────────────────

SCHEMES = [
    {
        "name": "Jal Jeevan Mission",
        "code": "JJM",
        "scheme_type": SchemeType.CSS,
        "dept_code": "JALSHAKTI",
        "total_outlay": 800000,      # ₹8000 Cr in lakhs
        "start_year": 2019,
        "end_year": 2024,
        "source_url": "https://ejalshakti.gov.in/jjmreport/JJMIndia.aspx",
        "description": "Tap water connection to every rural household in J&K",
    },
    {
        "name": "PM Awas Yojana - Gramin",
        "code": "PMAY_G",
        "scheme_type": SchemeType.CSS,
        "dept_code": "RDPR",
        "total_outlay": 210000,
        "start_year": 2016,
        "end_year": 2026,
        "source_url": "https://pmayg.nic.in",
        "description": "Pucca houses for homeless and kutcha house dwellers in rural J&K",
    },
    {
        "name": "PM Awas Yojana - Urban",
        "code": "PMAY_U",
        "scheme_type": SchemeType.CSS,
        "dept_code": "ULB",
        "total_outlay": 95000,
        "start_year": 2015,
        "end_year": 2025,
        "source_url": "https://pmaymis.gov.in",
        "description": "Affordable housing in urban areas of J&K",
    },
    {
        "name": "Mahatma Gandhi NREGA",
        "code": "MGNREGA",
        "scheme_type": SchemeType.CSS,
        "dept_code": "RDPR",
        "total_outlay": 180000,
        "start_year": 2006,
        "end_year": None,
        "source_url": "https://nreganarayan.nic.in",
        "description": "Guaranteed 100 days rural employment per household in J&K",
    },
    {
        "name": "Smart Cities Mission - Jammu",
        "code": "SCM_JMU",
        "scheme_type": SchemeType.CENTRAL,
        "dept_code": "ULB",
        "total_outlay": 100000,
        "start_year": 2016,
        "end_year": 2025,
        "source_url": "https://smartcities.gov.in",
        "description": "Smart infrastructure development in Jammu city",
    },
    {
        "name": "Smart Cities Mission - Srinagar",
        "code": "SCM_SGR",
        "scheme_type": SchemeType.CENTRAL,
        "dept_code": "ULB",
        "total_outlay": 100000,
        "start_year": 2016,
        "end_year": 2025,
        "source_url": "https://smartcities.gov.in",
        "description": "Smart infrastructure development in Srinagar city",
    },
    {
        "name": "Samagra Shiksha Abhiyan",
        "code": "SSA",
        "scheme_type": SchemeType.CSS,
        "dept_code": "SCHOOLEDU",
        "total_outlay": 145000,
        "start_year": 2018,
        "end_year": None,
        "source_url": "https://samagrashiksha.gov.in",
        "description": "Integrated school education from pre-school to class XII",
    },
    {
        "name": "Ayushman Bharat - PMJAY",
        "code": "PMJAY",
        "scheme_type": SchemeType.CSS,
        "dept_code": "HEALTH",
        "total_outlay": 85000,
        "start_year": 2018,
        "end_year": None,
        "source_url": "https://bis.pmjay.gov.in",
        "description": "Health insurance coverage of ₹5 lakh per family per year",
    },
    {
        "name": "Holistic Agriculture Development Programme",
        "code": "HADP",
        "scheme_type": SchemeType.UT,
        "dept_code": "AGRI",
        "total_outlay": 500000,
        "start_year": 2022,
        "end_year": 2027,
        "source_url": "https://jkagri.gov.in",
        "description": "₹5000 Cr UT-specific scheme for transforming J&K agriculture",
    },
    {
        "name": "Mission Youth",
        "code": "MYOUTH",
        "scheme_type": SchemeType.UT,
        "dept_code": "LABOUR",
        "total_outlay": 20000,
        "start_year": 2020,
        "end_year": None,
        "source_url": "https://jkmissionyouth.gov.in",
        "description": "Self-employment and skill development for J&K youth",
    },
    {
        "name": "National Health Mission",
        "code": "NHM",
        "scheme_type": SchemeType.CSS,
        "dept_code": "HEALTH",
        "total_outlay": 120000,
        "start_year": 2013,
        "end_year": None,
        "source_url": "https://nhm.gov.in",
        "description": "Strengthening public health systems across J&K",
    },
    {
        "name": "Border Area Development Programme",
        "code": "BADP",
        "scheme_type": SchemeType.CENTRAL,
        "dept_code": "RDPR",
        "total_outlay": 35000,
        "start_year": 1986,
        "end_year": None,
        "source_url": "https://doner.gov.in",
        "description": "Development of border districts — Kupwara, Baramulla, Poonch, Rajouri etc.",
    },
    {
        "name": "Direct Benefit Transfer",
        "code": "DBT",
        "scheme_type": SchemeType.CENTRAL,
        "dept_code": "FINANCE",
        "total_outlay": 0,
        "start_year": 2013,
        "end_year": None,
        "source_url": "https://dbtbharat.gov.in",
        "description": "Direct cash transfers to beneficiaries bank accounts",
    },
]


# ── Grant → department mapping (Appropriation Accounts) ───────────────────────
# The CAG accounts list 36 numbered grants; the tracker has 20 departments. Only grants whose
# name clearly matches a tracker department are mapped. The rest stay unmapped and are shown
# under their official grant name. Each entry carries a fragment of the official grant name;
# tests/test_grant_department_map.py checks it against the parsed PDF for every year listed,
# so a renumbered grant fails CI instead of being mapped to the wrong department.
# Grant numbers and names checked identical in 2021-22, 2022-23 and 2023-24 (2026-11-22).
GRANT_MAP_YEARS = ("2021-22", "2022-23", "2023-24")
GRANT_DEPARTMENT_MAP = [
    # (grant_no, fragment of official grant name, department code, note)
    (1,  "General Administration",       "GAD",        None),
    (2,  "Home",                         "POLICE",     None),
    (6,  "Power Development",            "PDD",        None),
    (7,  "Education",                    "SCHOOLEDU",  "Grant is titled 'Education Department'; higher education is grant 27."),
    (8,  "Finance",                      "FINANCE",    "Includes pensions and debt servicing (charged)."),
    (11, "Industry and Commerce",        "INDUSTRIES", None),
    (12, "Agriculture",                  "AGRI",       None),
    (13, "Sheep Husbandary",             "ANIMAL",     None),
    (14, "Revenue",                      "REVENUE",    None),
    (16, "Public Works",                 "PWD",        None),
    (17, "Health",                       "HEALTH",     None),
    (18, "Social Welfare",               "SOCIALWEL",  None),
    (20, "Tourism",                      "TOURISM",    None),
    (21, "Forest",                       "FOREST",     None),
    (23, "Public Health Engineering",    "JALSHAKTI",  "Only PHE; Irrigation and Flood Control (grant 22) is not mapped."),
    (25, "Labour",                       "LABOUR",     "Grant also covers Stationery and Printing."),
    (27, "Higher Education",             "HIGHEREDU",  None),
    (28, "Rural Development",            "RDPR",       None),
    (32, "Horticulture",                 "HORTI",      None),
]


# ── Seed Functions ────────────────────────────────────────────────────────────

async def seed_departments(db: AsyncSession):
    for dept_data in DEPARTMENTS:
        result = await db.execute(select(Department).where(Department.code == dept_data["code"]))
        if result.scalar_one_or_none():
            continue
        dept = Department(
            name=dept_data["name"],
            code=dept_data["code"],
            division=dept_data["division"],
        )
        db.add(dept)
    await db.flush()  # schemes and the grant map look departments up by code


async def seed_districts(db: AsyncSession):
    for d in DISTRICTS:
        result = await db.execute(select(District).where(District.code == d["code"]))
        if result.scalar_one_or_none():
            continue
        district = District(
            name=d["name"],
            code=d["code"],
            division=d["division"],
            population=d["population"],
            area_sqkm=d["area_sqkm"],
            is_border_district=d["is_border"],
        )
        db.add(district)


async def seed_schemes(db: AsyncSession):
    for s in SCHEMES:
        result = await db.execute(select(Scheme).where(Scheme.code == s["code"]))
        if result.scalar_one_or_none():
            continue

        dept_result = await db.execute(select(Department).where(Department.code == s["dept_code"]))
        dept = dept_result.scalar_one_or_none()
        if not dept:
            continue

        scheme = Scheme(
            name=s["name"],
            code=s["code"],
            scheme_type=s["scheme_type"],
            department_id=dept.id,
            total_outlay=s["total_outlay"],
            start_year=s["start_year"],
            end_year=s["end_year"],
            source_url=s["source_url"],
            description=s["description"],
        )
        db.add(scheme)


async def seed_grant_department_map(db: AsyncSession):
    result = await db.execute(select(Department.code, Department.id))
    dept_ids = dict(result.all())
    for fy in GRANT_MAP_YEARS:
        for grant_no, _fragment, code, note in GRANT_DEPARTMENT_MAP:
            if code not in dept_ids:
                continue
            existing = await db.execute(
                select(GrantDepartmentMap).where(
                    GrantDepartmentMap.financial_year == fy,
                    GrantDepartmentMap.grant_no == grant_no,
                )
            )
            if existing.scalar_one_or_none():
                continue
            db.add(GrantDepartmentMap(financial_year=fy, grant_no=grant_no, department_id=dept_ids[code], note=note))
    await db.flush()
