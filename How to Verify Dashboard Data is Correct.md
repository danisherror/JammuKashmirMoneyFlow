Great question — this is the most important habit when building a data tracker. Here's a complete verification guide.

---

## 🔍 How to Verify Dashboard Data is Correct

There are **3 layers** to verify:

```
Layer 1: Does the API return data at all?
Layer 2: Does the data match the original government source?
Layer 3: Are the calculations (%, gaps) mathematically correct?
```

---

## Layer 1 — Verify the API Directly

Before trusting the dashboard UI, check the raw API responses first.

### Step 1: Open Swagger UI
```
http://localhost:8000/docs
```
Every endpoint is listed here. Click any endpoint → **Try it out** → **Execute**. You see the exact JSON the frontend receives.

### Step 2: Use curl from terminal
```bash
# Check if API is alive
curl http://localhost:8000/api/v1/health

# Get J&K budget overview
curl http://localhost:8000/api/v1/budget/overview?financial_year=2024-25

# Get all departments
curl http://localhost:8000/api/v1/budget/departments?financial_year=2024-25

# Get MGNREGA scheme detail (find ID first from /schemes)
curl http://localhost:8000/api/v1/schemes?financial_year=2024-25

# Get district heatmap
curl http://localhost:8000/api/v1/districts/heatmap

# Check sync status — was the last collector run successful?
curl http://localhost:8000/api/v1/alerts/sync-status
```

### Step 3: Check the database directly
```bash
# Connect to Postgres inside Docker
docker exec -it jk-money-flow-postgres-1 psql -U postgres -d jk_money_flow

# Inside psql:

-- Are all 20 departments seeded?
SELECT code, name FROM departments ORDER BY code;

-- Are all 20 districts seeded?
SELECT code, name, division FROM districts ORDER BY division, name;

-- Are all 12 schemes seeded?
SELECT code, name, scheme_type FROM schemes ORDER BY code;

-- What budget allocations exist?
SELECT d.code, ba.budget_estimate, ba.financial_year
FROM budget_allocations ba
JOIN departments d ON d.id = ba.department_id
ORDER BY ba.budget_estimate DESC;

-- Did any scheme progress get collected?
SELECT s.code, dist.name, sp.utilization_pct, sp.snapshot_date
FROM scheme_progress sp
JOIN schemes s ON s.id = sp.scheme_id
JOIN districts dist ON dist.id = sp.district_id
ORDER BY sp.snapshot_date DESC
LIMIT 20;

-- What does the sync log say?
SELECT collector_name, status, started_at, records_inserted, records_updated, error_message
FROM data_sync_log
ORDER BY started_at DESC;
```

---

## Layer 2 — Cross-Check Against Official Government Sources

This is the most important step. For each data source, here is exactly what to compare and where to look.

---

### ✅ MGNREGA Data Verification

**Dashboard shows:** Person-days generated, households employed, fund utilization per district

**Official source to compare:**
```
https://nreganarayan.nic.in/netnrega/home.aspx
```

**Step by step:**
1. Go to the URL above
2. Click **"Reports"** → **"Financial"** or **"Physical"**
3. Select **State → Jammu & Kashmir**
4. Select financial year **2024-25**
5. Click **"District wise"**

**What to match:**

| Dashboard field | MGNREGA MIS field | Where to find it |
|---|---|---|
| `hh_demanded` | Households demanded employment | District-wise physical report |
| `hh_provided_employment` | Households provided employment | Same report |
| `person_days_generated` | Total person days generated | Same report |
| `funds_utilized` | Total expenditure | Financial statement |

**Quick sanity check:** J&K total person-days for FY2024-25 should be roughly **1.5–2 crore** person-days. If the dashboard shows 15 crore or 15,000 — something is wrong in unit conversion.

---

### ✅ Jal Jeevan Mission Verification

**Dashboard shows:** Households with tap connections, villages covered, % coverage

**Official source:**
```
https://ejalshakti.gov.in/jjmreport/JJMIndia.aspx
```

**Step by step:**
1. Go to URL above
2. On the map, click on **Jammu & Kashmir**
3. You will see state-level summary
4. Click **"District wise"** tab

**What to match:**

| Dashboard field | JJM portal field | Notes |
|---|---|---|
| `total_hh` | Total rural households | Should be ~15–17 lakh for J&K |
| `hh_with_tap` | HH with tap water connection | Check absolute number |
| `physical_pct` | % coverage | J&K should be ~85–90% as of 2024 |
| `villages_covered` | Villages 100% covered | Cross-check count |

**Quick sanity check:** J&K JJM coverage should be above 80%. If dashboard shows 20% or 200% — parser is broken.

---

### ✅ Budget Allocation Verification

**Dashboard shows:** Department-wise allocation for FY2024-25

**Official source:**
```
https://jkfinance.nic.in
```
→ Click **"Budget Documents"** → **"Annual Budget 2024-25"** → Download the PDF

**Step by step:**
1. Download the J&K Budget 2024-25 PDF
2. Go to **"Statement 11"** — Department-wise summary
3. Look for the column **"Budget Estimate 2024-25"**

**What to match (key departments):**

| Department | Dashboard (₹ Cr) | Check PDF column |
|---|---|---|
| Finance Dept | ₹8,900 Cr | Includes pension, debt service |
| Police & Home | ₹4,200 Cr | Security-heavy UT |
| PWD | ₹4,500 Cr | Largest capital spender |
| School Education | ₹3,200 Cr | Largest workforce |
| Jal Shakti | ₹3,800 Cr | JJM + urban water |

> Note: Our seed data is in **lakhs**. Convert: `450000 lakhs ÷ 100 = ₹4,500 Cr`

---

## Layer 3 — Verify the Calculations

These are the formulas our code uses. Verify them manually with a calculator.

### Utilization %
```
Formula: (funds_utilized / funds_allocated) × 100

Example — MGNREGA Anantnag:
  Allocated:  ₹8,200 L
  Utilized:   ₹6,700 L
  Expected %: (6700 / 8200) × 100 = 81.7%
  
Check in DB:
  SELECT utilization_pct FROM scheme_progress 
  WHERE district_id = (SELECT id FROM districts WHERE code = 'ANN')
  AND scheme_id = (SELECT id FROM schemes WHERE code = 'MGNREGA');
```

### Gap Amount
```
Formula: gap_lakhs = allocated - utilized

Example — PWD:
  Allocated: ₹4,50,000 L (₹4,500 Cr)
  Utilized:  ₹1,80,000 L (₹1,800 Cr)
  Gap:       ₹2,70,000 L (₹2,700 Cr)
  
Check via API:
  curl http://localhost:8000/api/v1/budget/gap-analysis
```

### Physical % (MGNREGA)
```
Formula: (hh_provided_employment / hh_demanded) × 100

Example — Baramulla:
  Demanded:  52,300 households
  Provided:  44,100 households
  Expected:  (44100 / 52300) × 100 = 84.3%
```

### District Fund Share (how we split state-level fund data to districts)
```
Formula: district_share = district_person_days / total_state_person_days
         district_funds = state_funds × district_share

This is an APPROXIMATION — MGNREGA releases funds district-wise,
but the API only gives state totals in some endpoints.
Verify against MGNREGA's own district financial report to check
if our apportionment is close.
```

---

## Layer 4 — Trigger a Fresh Collect and Watch It

The most reliable end-to-end test:

### Step 1: Wipe existing scheme_progress data
```sql
-- In psql
DELETE FROM scheme_progress;
DELETE FROM data_sync_log;
```

### Step 2: Trigger collector manually
```bash
curl -X POST http://localhost:8000/api/v1/alerts/trigger/mgnrega
curl -X POST http://localhost:8000/api/v1/alerts/trigger/jjm
```

### Step 3: Watch the logs
```bash
docker logs jk-money-flow-api-1 -f
```
You should see:
```
⏰ Scheduler: Starting MGNREGA collection
[mgnrega_collector] Started. Log ID: 1
[mgnrega_collector] GET https://nreganarayan.nic.in/...
[mgnrega_collector] Parsed 20 district rows from HTML
[mgnrega_collector] Saved 20 new + 0 updated district records
[mgnrega_collector] Finished. Status=success Fetched=20 Inserted=20
```

### Step 4: Check what was inserted
```sql
SELECT
  d.name AS district,
  sp.target_physical,
  sp.achieved_physical,
  sp.physical_pct,
  sp.funds_allocated,
  sp.utilization_pct,
  sp.snapshot_date,
  sp.source
FROM scheme_progress sp
JOIN districts d ON d.id = sp.district_id
JOIN schemes s ON s.id = sp.scheme_id
WHERE s.code = 'MGNREGA'
ORDER BY sp.utilization_pct DESC;
```

### Step 5: Compare one row to official site
Pick **Baramulla** from your query result. Go to MGNREGA MIS, filter to J&K → Baramulla → FY2024-25. Compare `person_days_generated` number exactly. If it matches within 5% → ✅ collector is working correctly. If it's off by 10x → unit conversion bug in parser.

---

## 🚨 Red Flags to Watch For

| What you see | What it means | How to fix |
|---|---|---|
| All districts show exactly same utilization % | District apportionment bug | Check `gap_calculator.py` share formula |
| utilization_pct > 100 | Amount unit mismatch (crore vs lakh) | Check `data_cleaner.clean_amount()` |
| All values = 0 after collect | Parser hit fallback data | Check `data_sync_log.error_message` |
| Snapshot date is old | Scheduler not running | Check `docker logs`, verify `SCHEDULER_ENABLED=true` in `.env` |
| API returns empty arrays | Seeds didn't run | Call `curl -X POST localhost:8000/api/v1/admin/seed` or restart container |

---

## Cheat Sheet — 5-Minute Daily Verification

```bash
# 1. Was last night's collect successful?
curl -s http://localhost:8000/api/v1/alerts/sync-status | python3 -m json.tool

# 2. Does MGNREGA J&K total look reasonable?
curl -s "http://localhost:8000/api/v1/schemes?financial_year=2024-25" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  m=[x for x in d if x['code']=='MGNREGA'][0]; \
  print(f'MGNREGA util: {m[\"utilization_pct\"]}% | allocated: {m[\"funds_allocated_lakhs\"]} lakhs')"

# 3. Cross-check one number manually on official site
echo "Go to: https://nreganarayan.nic.in → J&K → District wise → 2024-25"
echo "Compare Anantnag person_days with what DB shows"
```