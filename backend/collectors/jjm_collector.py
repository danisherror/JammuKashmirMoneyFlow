"""
Jal Jeevan Mission Collector for J&K
Source: ejalshakti.gov.in/jjmreport — public JSON API, no auth required
Updates: Daily at 6 AM IST

NO FALLBACK DATA. If the API is down → exception is raised → DataSyncLog
records FAILED → dashboard shows last successfully fetched snapshot.

JJM API endpoints (discovered via browser network tab on the portal):
  Base: https://ejalshakti.gov.in/jjmreport/JJMIndia.aspx
  The page loads data via AJAX calls to these JSON endpoints.
  State code for J&K: 01
"""
import time
import re
from datetime import date
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import select

from collectors.base_collector import BaseCollector
from database.models import SchemeProgress, Scheme, District

# ── API endpoints ─────────────────────────────────────────────────────────────

BASE = "https://ejalshakti.gov.in/jjmreport"

# These endpoints return JSON arrays with district-level data
# Discovered from the JJM dashboard network requests (all public)
COVERAGE_API   = f"{BASE}/api/JJMIndia/GetDistrictData"
FUND_API       = f"{BASE}/api/JJMIndia/GetStateFundData"
VILLAGE_API    = f"{BASE}/api/JJMIndia/GetDistrictVillageData"

JK_STATE_CODE  = "01"

# JJM API district names → our district codes
# The API returns names in uppercase; we normalize before lookup
DISTRICT_MAP = {
    "ANANTNAG":  "ANN",
    "BUDGAM":    "BDG",
    "BANDIPORE": "BNP",
    "BANDIPORA": "BNP",
    "BARAMULLA": "BRM",
    "DODA":      "DDA",
    "GANDERBAL": "GNB",
    "JAMMU":     "JMU",
    "KATHUA":    "KTH",
    "KISHTWAR":  "KWT",
    "KULGAM":    "KLG",
    "KUPWARA":   "KPW",
    "POONCH":    "PNC",
    "PULWAMA":   "PWM",
    "RAJOURI":   "RJR",
    "RAMBAN":    "RMB",
    "REASI":     "RSI",
    "SAMBA":     "SMB",
    "SHOPIAN":   "SPN",
    "SRINAGAR":  "SGR",
    "UDHAMPUR":  "UDH",
}


class JJMCollector(BaseCollector):
    collector_name = "jjm_collector"
    request_delay  = 1.5

    def __init__(self, db: Session, financial_year: str = "2024-25"):
        super().__init__(db)
        self.financial_year = financial_year

    # ── Main entry ────────────────────────────────────────────────────────────

    def run_collection(self):
        scheme = self.db.execute(
            select(Scheme).where(Scheme.code == "JJM")
        ).scalar_one_or_none()
        if not scheme:
            raise RuntimeError("JJM scheme not in DB — run seed first")

        district_rows = self._fetch_district_coverage()  # raises on failure
        fund_totals   = self._fetch_fund_utilization()   # raises on failure

        self._records_fetched = len(district_rows)
        self._save_progress(scheme, district_rows, fund_totals)

    # ── Fetchers ──────────────────────────────────────────────────────────────

    def _fetch_district_coverage(self) -> list[dict]:
        """
        Call the JJM district coverage API for J&K.
        Returns list of dicts with household coverage per district.
        Raises ValueError if response is empty or malformed.
        """
        params = {
            "stateCode": JK_STATE_CODE,
            "type":      "D",   # D = District level
        }
        logger.info(f"[jjm] Fetching district coverage from {COVERAGE_API}")

        with self.get_http_client() as client:
            response = self.fetch_url(client, COVERAGE_API, params=params)

        raw = response.json()
        rows = self._parse_coverage_response(raw)

        if not rows:
            raise ValueError(
                f"JJM coverage API returned 0 district rows for J&K (state_code={JK_STATE_CODE}). "
                f"Raw response keys: {list(raw.keys()) if isinstance(raw, dict) else type(raw).__name__}"
            )

        logger.info(f"[jjm] Parsed {len(rows)} district coverage rows")
        return rows

    def _fetch_fund_utilization(self) -> dict:
        """
        Call the JJM fund utilization API for J&K.
        Returns {"allocated": int, "released": int, "utilized": int} in lakhs.
        Raises ValueError if response is empty.
        """
        params = {"stateCode": JK_STATE_CODE}
        logger.info(f"[jjm] Fetching fund utilization from {FUND_API}")

        time.sleep(self.request_delay)
        with self.get_http_client() as client:
            response = self.fetch_url(client, FUND_API, params=params)

        raw  = response.json()
        data = raw[0] if isinstance(raw, list) and raw else raw
        if not isinstance(data, dict):
            raise ValueError(f"JJM fund API returned unexpected type: {type(data)}")

        # Try all known key variants — the API has changed key names in past versions
        def pick(d: dict, *keys, default=0) -> int:
            for k in keys:
                if k in d and d[k] is not None:
                    return int(float(str(d[k]).replace(",", "")))
            return default

        result = {
            "allocated": pick(data,
                "totalAllocation", "total_allocation",
                "CentralShare", "TotalAllocation", "allocated"),
            "released": pick(data,
                "fundsReleased", "funds_released",
                "Released", "release", "released"),
            "utilized": pick(data,
                "fundsUtilized", "funds_utilized",
                "Utilized", "expenditure", "utilized"),
        }

        if result["allocated"] == 0:
            raise ValueError(
                f"JJM fund API returned allocated=0 for J&K. "
                f"Available keys in response: {list(data.keys())}"
            )

        logger.info(f"[jjm] Fund totals for J&K: {result}")
        return result

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_coverage_response(self, raw) -> list[dict]:
        """
        Parse JJM API JSON into a clean list.
        The API returns either:
          - A list of district objects directly
          - {"data": [...]} or {"result": [...]}
        """
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("data") or raw.get("result") or raw.get("Data") or []
        else:
            logger.error(f"[jjm] Unexpected response type: {type(raw)}")
            return []

        results = []
        for item in items:
            if not isinstance(item, dict):
                continue

            # Normalize district name — try all known key variants
            name = (
                item.get("districtName") or item.get("DistrictName") or
                item.get("district_name") or item.get("District") or ""
            ).upper().strip()

            # Remove common suffixes/prefixes that appear in some API versions
            name = re.sub(r"\s*\(.*?\)", "", name).strip()

            our_code = DISTRICT_MAP.get(name)
            if not our_code:
                # Partial match fallback for minor spelling differences
                for key, code in DISTRICT_MAP.items():
                    if key in name or name in key:
                        our_code = code
                        logger.debug(f"[jjm] Partial match '{name}' → '{key}' ({code})")
                        break

            if not our_code:
                logger.debug(f"[jjm] No district match for name: '{name}'")
                continue

            def get_int(d, *keys) -> int:
                for k in keys:
                    v = d.get(k)
                    if v is not None:
                        try:
                            return int(float(str(v).replace(",", "")))
                        except (ValueError, TypeError):
                            pass
                return 0

            results.append({
                "district_code":     our_code,
                "district_name":     name,
                "total_hh":          get_int(item,
                    "totalHH", "total_hh", "TotalHH",
                    "totalRuralHH", "TotalRuralHH"),
                "hh_with_tap":       get_int(item,
                    "hhWithTap", "hh_with_tap", "HHWithTap",
                    "tapConnections", "TapConnections",
                    "fhtcProvided", "FHTCProvided"),
                "fhtc_provided":     get_int(item,
                    "fhtcProvided", "FHTCProvided",
                    "FunctionalHHTC", "functionalHHTC"),
                "villages_covered":  get_int(item,
                    "villagesCovered", "VillagesCovered",
                    "villages_covered", "fullyCovedVillages"),
                "total_villages":    get_int(item,
                    "totalVillages", "TotalVillages",
                    "total_villages"),
            })

        return results

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save_progress(
        self,
        scheme: Scheme,
        district_rows: list[dict],
        fund_totals: dict,
    ):
        """
        Upsert SchemeProgress. Funds apportioned by district household share
        because the fund API only gives J&K state totals.
        """
        today      = date.today()
        total_hh   = sum(r.get("total_hh", 0) for r in district_rows)

        if total_hh == 0:
            raise ValueError("[jjm] Total households across all districts is 0 — cannot apportion funds")

        for row in district_rows:
            district = self.db.execute(
                select(District).where(District.code == row["district_code"])
            ).scalar_one_or_none()
            if not district:
                logger.warning(f"[jjm] District {row['district_code']} not in DB")
                self.skip(f"district {row['district_code']} not in DB")
                continue

            dist_hh    = row.get("total_hh", 0)
            hh_tap     = row.get("hh_with_tap", 0)
            share      = dist_hh / total_hh if total_hh > 0 else 0

            dist_allocated = int(fund_totals.get("allocated", 0) * share)
            dist_released  = int(fund_totals.get("released",  0) * share)
            dist_utilized  = int(fund_totals.get("utilized",  0) * share)

            physical_pct = round(hh_tap          / dist_hh       * 100, 2) if dist_hh        > 0 else None
            util_pct     = round(dist_utilized   / dist_allocated * 100, 2) if dist_allocated > 0 else None
            release_pct  = round(dist_released   / dist_allocated * 100, 2) if dist_allocated > 0 else None

            existing = self.db.execute(
                select(SchemeProgress).where(
                    SchemeProgress.scheme_id      == scheme.id,
                    SchemeProgress.district_id    == district.id,
                    SchemeProgress.snapshot_date  == today,
                    SchemeProgress.financial_year == self.financial_year,
                )
            ).scalar_one_or_none()

            if existing:
                existing.target_physical    = dist_hh
                existing.achieved_physical  = hh_tap
                existing.physical_pct       = physical_pct
                existing.funds_allocated    = dist_allocated
                existing.funds_released     = dist_released
                existing.funds_utilized     = dist_utilized
                existing.utilization_pct    = util_pct
                existing.release_pct        = release_pct
                existing.raw_data           = row
                self._records_updated += 1
            else:
                self.db.add(SchemeProgress(
                    scheme_id         = scheme.id,
                    district_id       = district.id,
                    financial_year    = self.financial_year,
                    target_physical   = dist_hh,
                    achieved_physical = hh_tap,
                    physical_unit     = "households",
                    funds_allocated   = dist_allocated,
                    funds_released    = dist_released,
                    funds_utilized    = dist_utilized,
                    utilization_pct   = util_pct,
                    release_pct       = release_pct,
                    physical_pct      = physical_pct,
                    snapshot_date     = today,
                    source            = "ejalshakti.gov.in",
                    raw_data          = row,
                ))
                self._records_inserted += 1

        self.db.commit()
        logger.info(
            f"[jjm] Saved {self._records_inserted} inserted "
            f"+ {self._records_updated} updated district records"
        )
