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
| Collector | Source | Schedule |
|---|---|---|
| MGNREGA | nreganarayan.nic.in | Daily 6AM IST |
| JJM | ejalshakti.gov.in | Daily 6AM IST |
| PMAY | pmayg.nic.in | Weekly (Phase 2) |
| DBT | dbtbharat.gov.in | Daily (Phase 2) |
| Tenders | jktenders.gov.in | Daily (Phase 2) |
| CAG | cag.gov.in | Monthly (Phase 2) |
