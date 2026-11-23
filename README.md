# J&K Public Money Flow Tracker

## Quick Start

### 1. Copy environment file
```bash
cp .env.example .env
```

### 2. Run with Docker (recommended)
```bash
docker-compose up --build
```

### 3. Or run manually

**Backend:**
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## URLs
- Frontend: http://localhost:5173
- API:      http://localhost:8000
- API Docs: http://localhost:8000/docs

## Manually trigger a collector
```bash
curl -X POST http://localhost:8000/api/v1/alerts/trigger/mgnrega
curl -X POST http://localhost:8000/api/v1/alerts/trigger/jjm
```

## Data Sources
What actually runs, read from `backend/scheduler/jobs.py` (`create_scheduler`). Times are IST; the weekly hour is `MGNREGA_FETCH_HOUR` (default 6). Nothing runs when `SCHEDULER_ENABLED=false`. The Sync Status page shows each collector's real next run time.

| Collector (`collector_name`) | Source | Schedule | Status |
|---|---|---|---|
| MGNREGA (`mgnrega_collector`) | nreganarayan.nic.in | Weekly, Sunday 06:00 | Failing: the host does not resolve; the correct host is not yet checked (todo 2.1) |
| JJM (`jjm_collector`) | ejalshakti.gov.in | Weekly, Sunday 06:00 | Failing: the district endpoint returned HTTP 404 on 2026-11-22 (todo 2.1) |
| PMAY (`pmay_collector`) | pmayg.nic.in (candidate, not yet checked) | Weekly, Sunday 06:00 | `no_source` (todo 2.4) |
| DBT (`dbt_collector`) | dbtbharat.gov.in (candidate, not yet checked) | Weekly, Sunday 06:00 | `no_source` (todo 2.4) |
| Tenders (`tenders_collector`) | jktenders.gov.in (candidate, not yet checked) | Weekly, Sunday 06:00 | `no_source` (todo 2.4) |
| PFMS (`pfms_collector`) | pfms.nic.in (candidate, not yet checked) | Weekly, Sunday 06:00 | `no_source` (todo 2.4) |
| CGA monthly spend (`cga_collector`) | none found yet | Weekly, Sunday 06:00 **and** monthly, 26th 08:00 | `no_source` (todo 2.2) |
| CAG audit findings (`cag_collector`) | cag.gov.in audit reports | Weekly, Sunday 06:00 | `no_source` (todo 2.3) |
| Appropriation Accounts (loader, not a collector) | cag.gov.in PDFs (see `backend/tests/fixtures/appropriation_accounts/SOURCES.md`) | Not scheduled; run by hand: `docker compose exec api python -m loaders.appropriation_accounts --all` | Loaded: 2021-22, 2022-23, 2023-24 (scheduling it is todo 2.2) |

All eight collectors run one after another in the weekly job (`weekly_all_collectors`); CGA also has its own monthly job (`monthly_cga`).
