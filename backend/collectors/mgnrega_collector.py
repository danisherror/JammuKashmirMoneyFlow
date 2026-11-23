"""
MGNREGA Collector for J&K
Source: nreganarayan.nic.in public MIS
Updates: Daily at 6 AM IST

NO FALLBACK DATA — if the portal is unreachable, we log the failure and
store nothing. The dashboard will show the last successfully fetched data
(or empty if never fetched). Stale-but-labeled is better than invented.

MGNREGA MIS has two useful endpoints for J&K (state_code=01):
  1. District-wise physical progress page (HTML table)
  2. State expenditure statement page (HTML table)

Both are public, no login required. The site uses ASP.NET WebForms
so we request the page, parse the HTML table with BeautifulSoup.

robots.txt: not checked. nreganarayan.nic.in did not resolve on 2026-11-23
(the host itself is in question, todo.md 2.1). BaseCollector.fetch_url checks
robots.txt before every fetch and won't fetch while it is unreachable.
"""
import time
import re
from datetime import date
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import select
from bs4 import BeautifulSoup

from collectors.base_collector import BaseCollector
from database.models import SchemeProgress, Scheme, District
from processors.data_cleaner import apportion, parse_int, percent


# ── Endpoints ─────────────────────────────────────────────────────────────────

BASE = "https://nreganarayan.nic.in"

# District-wise physical progress for J&K (state_code=01)
DISTRICT_PROGRESS_URL = (
    f"{BASE}/netnrega/nrega_reports/Rpt_DistrictWise_Physical_Progress.aspx"
    "?state_code=01&fin_year={fin_year}&Digest=ULsNBe4FkYPpAJ24LfSILQ"
)

# State-level fund statement for J&K
FUND_STATEMENT_URL = (
    f"{BASE}/netnrega/state_html/Statement_Of_Expenditure.aspx"
    "?state_code=01&fin_year={fin_year}"
)

# MGNREGA uses "2024-2025" format; our DB uses "2024-25"
def to_mgnrega_year(fy: str) -> str:
    """Convert "2024-25" → "2024-2025" for MGNREGA URLs"""
    start = fy.split("-")[0]
    end_short = fy.split("-")[1]
    end_full = str(int(start) + 1) if len(end_short) == 2 else end_short
    return f"{start}-{end_full}"

# MGNREGA district name in HTML → our district code
DISTRICT_NAME_MAP = {
    "anantnag":  "ANN",
    "badgam":    "BDG",
    "budgam":    "BDG",
    "bandipore": "BNP",
    "bandipora": "BNP",
    "baramulla": "BRM",
    "doda":      "DDA",
    "ganderbal": "GNB",
    "jammu":     "JMU",
    "kathua":    "KTH",
    "kishtwar":  "KWT",
    "kulgam":    "KLG",
    "kupwara":   "KPW",
    "poonch":    "PNC",
    "pulwama":   "PWM",
    "rajouri":   "RJR",
    "ramban":    "RMB",
    "reasi":     "RSI",
    "samba":     "SMB",
    "shopian":   "SPN",
    "srinagar":  "SGR",
    "udhampur":  "UDH",
}


class MGNREGACollector(BaseCollector):
    collector_name = "mgnrega_collector"
    label = "MGNREGA"
    source_name = "nreganarayan.nic.in"
    source_url = f"{BASE}/netnrega/home.aspx"
    request_delay  = 2.0

    def __init__(self, db: Session, financial_year: str = "2024-25"):
        super().__init__(db)
        self.financial_year    = financial_year
        self.mgnrega_fin_year  = to_mgnrega_year(financial_year)

    # ── Main entry ────────────────────────────────────────────────────────────

    def run_collection(self):
        scheme = self.db.execute(
            select(Scheme).where(Scheme.code == "MGNREGA")
        ).scalar_one_or_none()
        if not scheme:
            raise RuntimeError("MGNREGA scheme not in DB — run seed first")

        district_rows = self._fetch_district_progress()   # raises on failure
        fund_totals   = self._fetch_fund_statement()       # raises on failure

        self._records_fetched = len(district_rows)
        self._save_progress(scheme, district_rows, fund_totals)

    # ── Fetchers ──────────────────────────────────────────────────────────────

    def _fetch_district_progress(self) -> list[dict]:
        """
        Fetch the district-wise physical progress HTML page and parse its table.
        Raises an exception if the page is unreachable or the table cannot be found.
        """
        url = DISTRICT_PROGRESS_URL.format(fin_year=self.mgnrega_fin_year)
        logger.info(f"[mgnrega] Fetching district progress: {url}")

        with self.get_http_client() as client:
            response = self.fetch_url(client, url)  # retries 3× on timeout

        self.progress_snapshot = self.snapshot(response, title="MGNREGA district-wise physical progress, J&K")
        rows = self._parse_district_table(response.text)
        if not rows:
            raise ValueError(
                "MGNREGA district progress table parsed 0 rows. "
                "The page structure may have changed. URL: " + url
            )
        logger.info(f"[mgnrega] Parsed {len(rows)} district rows")
        return rows

    def _fetch_fund_statement(self) -> dict:
        """
        Fetch the state-level fund expenditure statement for J&K.
        Returns {"allocated": int, "released": int, "utilized": int} in lakhs.
        Raises if page is unreachable or no numbers found.
        """
        url = FUND_STATEMENT_URL.format(fin_year=self.mgnrega_fin_year)
        logger.info(f"[mgnrega] Fetching fund statement: {url}")

        time.sleep(self.request_delay)
        with self.get_http_client() as client:
            response = self.fetch_url(client, url)

        self.fund_snapshot = self.snapshot(response, title="MGNREGA statement of expenditure, J&K")
        result = self._parse_fund_table(response.text)
        if not any(result.values()):
            raise ValueError(
                "MGNREGA fund statement gave no fund figures. "
                "Page may have changed structure. URL: " + url
            )
        logger.info(f"[mgnrega] Fund totals: {result}")
        return result

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_district_table(self, html: str) -> list[dict]:
        """
        Parse MGNREGA district-wise physical progress HTML.

        The page has a table like:
          S.No | District | HH Registered | HH Demanded | HH Provided | Person Days | ...

        We locate the table by looking for a header containing both
        "district" and "person" (case-insensitive).
        """
        soup = BeautifulSoup(html, "lxml")
        target_table = None

        for table in soup.find_all("table"):
            text = table.get_text(" ", strip=True).lower()
            if "district" in text and "person" in text and "demanded" in text:
                target_table = table
                break

        if not target_table:
            logger.error("[mgnrega] Could not locate district progress table in HTML")
            logger.debug(f"[mgnrega] Page snippet: {html[:500]}")
            return []

        results = []
        rows = target_table.find_all("tr")

        for row in rows[1:]:   # skip header
            cols = [
                td.get_text(strip=True).replace(",", "").replace(" ", "")
                for td in row.find_all(["td", "th"])
            ]
            if len(cols) < 6:
                continue

            # Find district name column — skip serial number column
            district_raw = ""
            for col in cols[1:4]:   # district is usually col 1 or 2
                if col and not col.isdigit() and len(col) > 3:
                    district_raw = col
                    break

            district_key  = district_raw.lower().strip()
            our_code = DISTRICT_NAME_MAP.get(district_key)

            if not our_code:
                # Try partial match for variations like "Bandipore" vs "Bandipora"
                for key, code in DISTRICT_NAME_MAP.items():
                    if key in district_key or district_key in key:
                        our_code = code
                        break

            if not our_code:
                logger.debug(f"[mgnrega] Unmatched district name: '{district_raw}'")
                continue

            # Column positions vary slightly by year; use position offsets from district col
            try:
                # Typical order after district name:
                # HH_registered, HH_demanded, HH_provided, person_days, sc_days, st_days, women_days
                # A missing column is unknown (None), not 0 (todo.md 1.3).
                num_cols = [c for c in cols if c and re.search(r"\d", c)]

                def col(i: int) -> int | None:
                    return parse_int(num_cols[i]) if len(num_cols) > i else None

                results.append({
                    "district_code":            our_code,
                    "district_name":            district_raw,
                    "hh_registered":            col(0),
                    "hh_demanded":              col(1),
                    "hh_provided_employment":   col(2),
                    "person_days_generated":    col(3),
                    "sc_person_days":           col(4),
                    "st_person_days":           col(5),
                    "women_person_days":        col(6),
                })
            except (IndexError, ValueError) as e:
                logger.warning(f"[mgnrega] Column parse error for '{district_raw}': {e}")
                continue

        return results

    def _parse_fund_table(self, html: str) -> dict:
        """
        Parse the state expenditure statement page.
        Looks for a table with columns containing allocation/release/expenditure figures.
        Returns totals in lakhs.
        """
        soup = BeautifulSoup(html, "lxml")

        # The statement page has J&K's row in a table with central allocation, state share, total
        for table in soup.find_all("table"):
            text = table.get_text(" ", strip=True).lower()
            if "alloc" in text and ("expend" in text or "utiliz" in text):
                rows = table.find_all("tr")
                for row in rows:
                    cols = [
                        td.get_text(strip=True).replace(",", "")
                        for td in row.find_all("td")
                    ]
                    # Find the totals row — usually labelled "Total" or "Grand Total"
                    row_text = " ".join(cols).lower()
                    if "total" in row_text or "grand" in row_text:
                        nums = []
                        for col in cols:
                            cleaned = re.sub(r"[^\d.]", "", col)
                            if cleaned and float(cleaned) > 1000:  # skip small/zero cols
                                nums.append(int(float(cleaned)))
                        if len(nums) >= 3:
                            return {
                                "allocated": nums[0],
                                "released":  nums[1],
                                "utilized":  nums[2],
                            }

        # No totals row: the fund figures are unknown, not zero.
        logger.warning("[mgnrega] Could not find totals row in fund statement — funds unknown")
        return {"allocated": None, "released": None, "utilized": None}

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save_progress(
        self,
        scheme: Scheme,
        district_rows: list[dict],
        fund_totals: dict,
    ):
        """
        Upsert SchemeProgress rows. One row per district per snapshot_date.
        Funds are apportioned to districts proportional to person-days generated,
        because the fund statement only gives J&K state totals. If any district's person-days are
        unknown the shares can't be worked out, so every district's funds are stored as unknown.
        """
        today = date.today()
        person_days_all = [r.get("person_days_generated") for r in district_rows]
        total_person_days = sum(person_days_all) if None not in person_days_all else None
        if total_person_days == 0:
            raise ValueError("[mgnrega] Total person_days is 0 — cannot apportion funds")

        for row in district_rows:
            district = self.db.execute(
                select(District).where(District.code == row["district_code"])
            ).scalar_one_or_none()
            if not district:
                logger.warning(f"[mgnrega] District code {row['district_code']} not in DB")
                self.skip(f"district {row['district_code']} not in DB")
                continue

            person_days  = row.get("person_days_generated")
            share        = person_days / total_person_days if total_person_days else None

            dist_allocated = apportion(fund_totals.get("allocated"), share)
            dist_released  = apportion(fund_totals.get("released"),  share)
            dist_utilized  = apportion(fund_totals.get("utilized"),  share)

            hh_demanded = row.get("hh_demanded")
            hh_provided = row.get("hh_provided_employment")

            util_pct     = percent(dist_utilized, dist_allocated)
            release_pct  = percent(dist_released, dist_allocated)
            physical_pct = percent(hh_provided,   hh_demanded)

            existing = self.db.execute(
                select(SchemeProgress).where(
                    SchemeProgress.scheme_id      == scheme.id,
                    SchemeProgress.district_id    == district.id,
                    SchemeProgress.snapshot_date  == today,
                    SchemeProgress.financial_year == self.financial_year,
                )
            ).scalar_one_or_none()

            if existing:
                existing.target_physical    = hh_demanded
                existing.achieved_physical  = hh_provided
                existing.funds_allocated    = dist_allocated
                existing.funds_released     = dist_released
                existing.funds_utilized     = dist_utilized
                existing.utilization_pct    = util_pct
                existing.release_pct        = release_pct
                existing.physical_pct       = physical_pct
                existing.raw_data           = row
                existing.snapshot_id        = self.progress_snapshot.id
                existing.funds_snapshot_id  = self.fund_snapshot.id
                self._records_updated += 1
            else:
                self.db.add(SchemeProgress(
                    scheme_id       = scheme.id,
                    district_id     = district.id,
                    financial_year  = self.financial_year,
                    target_physical = hh_demanded,
                    achieved_physical = hh_provided,
                    physical_unit   = "households",
                    funds_allocated = dist_allocated,
                    funds_released  = dist_released,
                    funds_utilized  = dist_utilized,
                    utilization_pct = util_pct,
                    release_pct     = release_pct,
                    physical_pct    = physical_pct,
                    snapshot_date   = today,
                    source          = "nreganarayan.nic.in",
                    raw_data        = row,
                    snapshot_id     = self.progress_snapshot.id,
                    funds_snapshot_id = self.fund_snapshot.id,
                ))
                self._records_inserted += 1

        self.db.commit()
        logger.info(
            f"[mgnrega] Saved {self._records_inserted} inserted "
            f"+ {self._records_updated} updated district records"
        )
