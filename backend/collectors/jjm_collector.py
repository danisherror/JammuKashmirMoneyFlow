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

robots.txt: https://ejalshakti.gov.in/robots.txt returned HTTP 404 on
2026-11-23, i.e. no rules, every path allowed (RFC 9309 §2.3.1.3,
https://www.rfc-editor.org/rfc/rfc9309#section-2.3.1.3). Re-checked on every
fetch by BaseCollector.fetch_url.
"""
import time
import re
from datetime import date
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import select

from collectors.base_collector import BaseCollector
from database.models import SchemeProgress, Scheme, District
from processors.data_cleaner import apportion, parse_int, percent

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
    label = "Jal Jeevan Mission"
    source_name = "ejalshakti.gov.in"
    source_url = f"{BASE}/JJMIndia.aspx"
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

        self.coverage_snapshot = self.snapshot(response, title="JJM district coverage, J&K")
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
        Returns {"allocated": int, "released": int | None, "utilized": int | None} in lakhs;
        None when the response has no such figure (unknown, not 0).
        Raises ValueError if there is no allocation figure.
        """
        params = {"stateCode": JK_STATE_CODE}
        logger.info(f"[jjm] Fetching fund utilization from {FUND_API}")

        time.sleep(self.request_delay)
        with self.get_http_client() as client:
            response = self.fetch_url(client, FUND_API, params=params)

        self.fund_snapshot = self.snapshot(response, title="JJM fund utilisation, J&K")
        raw  = response.json()
        data = raw[0] if isinstance(raw, list) and raw else raw
        if not isinstance(data, dict):
            raise ValueError(f"JJM fund API returned unexpected type: {type(data)}")

        # Try all known key variants — the API has changed key names in past versions
        def pick(d: dict, *keys) -> int | None:
            for k in keys:
                value = parse_int(d.get(k))
                if value is not None:
                    return value
            return None

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

        if not result["allocated"]:
            raise ValueError(
                f"JJM fund API returned no allocation (got {result['allocated']!r}) for J&K. "
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

            def get_int(d, *keys) -> int | None:
                """First key with a number; None (unknown) when none has one."""
                for k in keys:
                    value = parse_int(d.get(k))
                    if value is not None:
                        return value
                return None

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
        because the fund API only gives J&K state totals. If any district's household count is
        unknown the shares can't be worked out, so every district's funds are stored as unknown.
        """
        today      = date.today()
        hh_counts  = [r.get("total_hh") for r in district_rows]
        total_hh   = sum(hh_counts) if None not in hh_counts else None

        if total_hh == 0:
            raise ValueError("[jjm] Total households across all districts is 0 — cannot apportion funds")
        if total_hh is None:
            logger.warning("[jjm] Some districts have no household count — district funds stored as unknown")

        for row in district_rows:
            district = self.db.execute(
                select(District).where(District.code == row["district_code"])
            ).scalar_one_or_none()
            if not district:
                logger.warning(f"[jjm] District {row['district_code']} not in DB")
                self.skip(f"district {row['district_code']} not in DB")
                continue

            dist_hh    = row.get("total_hh")
            hh_tap     = row.get("hh_with_tap")
            share      = dist_hh / total_hh if total_hh else None

            dist_allocated = apportion(fund_totals.get("allocated"), share)
            dist_released  = apportion(fund_totals.get("released"),  share)
            dist_utilized  = apportion(fund_totals.get("utilized"),  share)

            physical_pct = percent(hh_tap,        dist_hh)
            util_pct     = percent(dist_utilized, dist_allocated)
            release_pct  = percent(dist_released, dist_allocated)

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
                existing.snapshot_id        = self.coverage_snapshot.id
                existing.funds_snapshot_id  = self.fund_snapshot.id
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
                    snapshot_id       = self.coverage_snapshot.id,
                    funds_snapshot_id = self.fund_snapshot.id,
                ))
                self._records_inserted += 1

        self.db.commit()
        logger.info(
            f"[jjm] Saved {self._records_inserted} inserted "
            f"+ {self._records_updated} updated district records"
        )
