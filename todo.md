# Roadmap to 9/10

Audit on 2026-11-22 (`docker-compose up --build`, every collector triggered, every endpoint hit, dashboard opened in a browser) scored the project **3/10**. The containers and API work. The project still fails at its one job: showing citizens **true** numbers about public money.

Work through the phases in order. Each phase lists the score it should unlock. A task is finished only when its **Done when** check passes.

**Ground rules for every task:**
- **No invented numbers.** A missing number shows as "No data", never as a random value.
- **Every figure is traceable.** Each stored record keeps the source URL, the time it was fetched, and the source document (or its hash).
- **Claims about portal behaviour need a source URL** (see `CLAUDE.md`). Write "unknown / not yet checked" instead of an unsourced claim.
- **Respect the portals.** Never work around CAPTCHAs, logins or bot blocks. If a source can only be reached that way, mark it unavailable and use a published alternative (official PDF/Excel reports, data.gov.in, an RTI reply).

---

## Phase 0 — Make it run from a fresh clone (3 → 4)

### 0.1 Restore the missing frontend `lib/` module
`.gitignore:19` (`lib/`, from a Python template) also matched `frontend/src/lib/`. Git never tracked it, and it no longer exists locally either. Every page fails with `Failed to resolve import "../lib/api"`.
- [x] Change `lib/` and `lib64/` in `.gitignore` to `/backend/lib/` and `/backend/lib64/`, or delete them.
- [x] Recreate `frontend/src/lib/api.ts`. It needs an axios instance `api` (base URL `import.meta.env.VITE_API_BASE_URL`), a typed function per endpoint (`fetchBudgetOverview`, `fetchDepartments`, `fetchDepartmentDetail`, `fetchSchemes`, `fetchSchemeDetail`, `fetchSchemeHistory`, `fetchDistrictHeatmap`, `fetchDistrictDetail`, `fetchSyncStatus`, `triggerCollector`, `triggerAllCollectors`, `fetchLowUtilAlerts`, `fetchCAGFindings`, `fetchTenders`, `fetchContractorLeaderboard`, `fetchDBTSchemes`, `fetchDBTGap`), and the types the pages import (`BudgetOverview`, `DepartmentSummary`, `SchemeSummary`, `SchemeDistrictProgress`, `SchemeVelocity`, `LowUtilizationAlert`, `CAGFinding`, `DBTSchemeSummary`, …). Mirror `backend/api/schemas.py`.
- [x] Recreate `frontend/src/lib/utils.ts` (`fmtLakhs`, `fmtPct`, `utilColor`, `gradeColor`, `divisionLabel`, `schemeBadge`, `schemeTypeLabel`) and `frontend/src/lib/districtCoordinates.ts` (`DISTRICT_COORDINATES` for the 20 districts).
- [ ] Verify the marker coordinates in `frontend/src/lib/districtCoordinates.ts` against an official gazetteer and add the source URL (currently approximate, unsourced).
- [ ] Better long-term: generate the TS types from `/openapi.json` (e.g. `openapi-typescript`) so the frontend and backend can't drift apart.

**Done when:** `git clone` → `cp .env.example .env` → `docker-compose up --build` renders every route in the browser with no Vite overlay, and `npm run build` (which runs `tsc`) exits 0. ✅ Checked 2026-11-22: all 12 routes render from a fresh clone with no overlay or console errors; `npm run build` exits 0.

### 0.2 Clean dev ergonomics
- [x] Remove the obsolete `version:` key from `docker-compose.yml`.
- [x] Turn off SQLAlchemy `echo` by default (`backend/database/connection.py:18`) and add a separate `SQL_ECHO` env var.
- [x] Pin frontend dependency versions exactly (keep `package-lock.json` authoritative) and use `npm ci` in `frontend/Dockerfile`.

**Done when:** `docker-compose up` prints no `version` warning, the API log has no SQL statements unless `SQL_ECHO=true`, and `frontend/Dockerfile` uses `npm ci`. ✅ Checked 2026-11-22.

### 0.3 Minimal CI from day one
Phases 1–3 are heavy refactors. Without CI, regressions go unnoticed until Phase 4.
- [x] Add `.github/workflows/ci.yml` running `ruff check backend`, `npm run build` (includes `tsc`) and `docker-compose build` on every push and PR. (Ruff is pinned in `backend/requirements-dev.txt`, configured in `backend/ruff.toml`; the existing 36 findings were fixed.)
- [ ] Add each new check (pytest, vitest, mypy, e2e) to this workflow as soon as the phase that introduces it lands. Phase 4.3 then only finishes and gates it.

**Done when:** a PR that breaks the frontend build shows a red check on GitHub. ⏳ Workflow added 2026-11-22 and all three checks pass locally; not yet confirmed on GitHub (needs a push and a test PR).

---

## Phase 1 — Stop presenting fake data as real (4 → 6)

This is the most important phase. A transparency tool that shows random numbers is worse than no tool.

### 1.1 Remove the random-data fallbacks
In these collectors, the "live" path always throws, so the random generator always runs:
| Collector | What it does today |
|---|---|
| `pmay_collector.py` | loads the page, then `raise PlaywrightTimeoutError` unconditionally → `random.uniform` targets |
| `pfms_collector.py` | same pattern → random release factors |
| `tenders_collector.py` | same pattern → random tenders **and invented contractor names** ("M/S Sharma Constructions") |
| `dbt_collector.py` | raises → random enrolment/payment numbers |
| `cga_collector.py` | `_fetch_pdf()` returns `None`, `_parse_pdf()` is a stub → "Smart Simulation" |
| `cag_collector.py` | runs over the hardcoded `MOCK_FINDINGS` list |

- [ ] Delete every `_generate_simulated_data` / `_run_fallback_simulation` / `MOCK_FINDINGS` path. Follow the honest pattern already in `jjm_collector.py` and `mgnrega_collector.py`: a failure raises and is logged to `DataSyncLog`.
- [ ] Write a one-off migration/script that deletes rows already saved with `source` containing `simulated`/`Simulation`, or `raw_data.note == "simulated fallback"`.
- [ ] If demo data is still wanted for local development, put it behind `DEMO_MODE=true` (default `false`). Store it with `is_demo=true` and show a red site-wide "DEMO DATA — NOT REAL" banner while it's on. The API must refuse to start with `DEMO_MODE=true` when `APP_ENV=production`.

**Done when:** `grep -rn "random\." backend/collectors` returns nothing outside the demo module, and a fresh database plus a run of every collector contains only rows that came from a real source.

### 1.2 Report collector status truthfully
- [ ] Add statuses `partial` and `no_source` to `DataSyncLog`. Only `success` when real rows were written.
- [ ] Fix `next_run` in `/alerts/sync-status`. It hardcodes "06:00 IST daily", but `scheduler/jobs.py` schedules weekly + monthly. Read the real next fire time from APScheduler.
- [ ] Make the README's "Data Sources" table match the actual scheduler.

**Done when:** a collector that writes zero real rows logs `partial` or `no_source` (never `success`), and `next_run` in `/alerts/sync-status` equals APScheduler's `job.next_run_time` for that job.

### 1.3 Make the UI honest about provenance and freshness
- [ ] Every KPI, chart and table shows "Source: <portal> · fetched <date>" with a link to the source document.
- [ ] Empty states say "No data collected yet from <source> — last attempt failed: <reason>" instead of showing `0` or `0.0%`. Today a missing utilisation shows as `0.0%` with a `critical` gap flag (`/budget/gap-analysis`), which is misleading.
- [ ] Separate "₹0 spent" (a real zero) from "unknown" (`null`) all the way through the API schema and the UI.

**Done when:** on an empty database, every page shows "No data" states (no `0`, `0.0%` or `critical` flags), and every populated figure shows its source and fetch date.

### 1.4 Provenance in the data model
The ground rules require every record to be traceable, but the models can't store that today. `SchemeProgress` has only a free-text `source` and `raw_data`; `BudgetAllocation` and `Expenditure` have only a default `source` string.
- [ ] Add a `raw_snapshots` table: `id`, `source_url`, `fetched_at`, `sha256`, `content_type`, `storage_path`, `collector_name`.
- [ ] Add a non-null `snapshot_id` foreign key to every fact table (`budget_allocations`, `expenditures`, `scheme_progress`, `tenders`, `cag_findings`, DBT tables). Expose `source_url`, `fetched_at` and a snapshot download link in every API response schema.
- [ ] Add `GET /api/v1/snapshots/{id}` to download the stored raw file.

**Done when:** no fact row can be inserted without a `snapshot_id`, and any figure in the API can be followed to a downloadable raw file whose SHA-256 matches.

### 1.5 Store money without losing precision
Money columns are `BigInteger` in lakhs, so anything below ₹1 lakh is truncated (the tenders code already computes `round(x, 2)` lakhs, then stores it as an integer).
- [ ] Change every money column to `Numeric(14, 2)` (lakhs, two decimals) and use `Decimal` in Pydantic schemas. Do this in the Alembic baseline (3.1), or as its first migration if 3.1 is already done.
- [ ] Add a units note to each money field's schema description ("₹ lakhs").

**Done when:** a value of 0.37 lakh round-trips through DB → API → UI unchanged.

### 1.6 Collect politely and honestly
`base_collector.py:43` sends a fake Chrome User-Agent "because govt portals sometimes block non-browser user agents". That contradicts the "respect the portals" ground rule.
- [ ] Use an honest User-Agent naming the project and a contact URL (e.g. `JKMoneyFlowBot/1.0 (+<repo URL>)`).
- [ ] Check and honour `robots.txt` for each portal before fetching. Record the result (allowed / disallowed, date checked) next to the source URL.
- [ ] If a portal blocks the honest UA, mark that collector `no_source`. Don't spoof.

**Done when:** `grep -rn "Mozilla" backend/collectors` returns nothing, and each collector's source comment records its `robots.txt` status.

---

## Phase 2 — Real data, end to end (6 → 7.5)

One fully real pipeline is worth more than six fake ones. Do these one at a time and finish each before starting the next.

### 2.1 Fix the two honest collectors first
Observed on 2026-11-22:
- **JJM:** `GET https://ejalshakti.gov.in/jjmreport/api/JJMIndia/GetDistrictData?stateCode=01&type=D` → **404**.
- **MGNREGA:** the request to `nreganarayan.nic.in` failed with `[Errno -2] Name or service not known` (DNS lookup failed).

- [ ] **First check whether the MGNREGA domain is real.** The DNS failure may mean `nreganarayan.nic.in` never existed rather than an outage. The MGNREGA reports site may be `nreganarep.nic.in`, but that is not yet checked. Confirm the correct host with a source URL, then fix it in `mgnrega_collector.py` and in `CLAUDE.md`'s list of sources.
- [ ] Find the current official endpoint or report page for each one and record the source URL in a code comment. Check data.gov.in for an official dataset before scraping HTML.
- [ ] Save the raw response (HTML/JSON/PDF) to `raw_snapshots/` (or object storage) with a SHA-256 hash, and link it from every derived row. That lets anyone re-check a number later.
- [ ] Add parser tests against saved fixture files (see 4.1), so a change in the portal's layout breaks CI, not production.

**Done when:** JJM and MGNREGA district-level numbers for J&K appear on the dashboard, and each number links back to its source snapshot.

### 2.2 Budget from official documents (CGA / J&K budget)
Observed on 2026-11-22: the CAG publishes the J&K **Appropriation Accounts** and **Finance Accounts (Vol I/II)** every year as text PDFs (not scans), with a "Summary of Appropriation Accounts" table listing every grant (department) as Revenue/Capital × Voted/Charged, with final grant, gross expenditure, saving and excess in ₹ thousand. Source URLs are in `backend/tests/fixtures/appropriation_accounts/SOURCES.md`. The table layout changes slightly from year to year (see the module docstring), so every new year needs a fixture and a test.

- [x] Find published J&K accounts documents and record their URLs (Appropriation Accounts 2021-22, 2022-23, 2023-24 on cag.gov.in; Finance Accounts Vol I/II for the same years). Checked 2026-11-22.
- [x] Parse the Summary of Appropriation Accounts with `pdfplumber`: `backend/parsers/appropriation_accounts.py` (also runs as a CLI: `python -m parsers.appropriation_accounts <pdf> --format csv`). Tested against 3 real PDFs (2021-22, 2022-23, 2023-24) in `backend/tests/test_appropriation_accounts.py`. Each row must satisfy grant − expenditure = saving − excess and the rows must add up to the printed totals; otherwise the whole document is rejected.
- [x] Store annual figures in their own table, not in `budget_allocations` (the "grant" column is the *final* grant, original + supplementary, not the Budget Estimate) or `expenditures` (monthly). Done: `appropriation_account_lines` (amounts in ₹ thousand, exactly as printed; unique per year + grant + section + kind) and `source_snapshots` (URL, SHA-256, file path, size, fetch time) in `database/models.py`. Tables are created by `create_all` on startup; move them to Alembic with the rest in 3.1.
- [x] Map grant numbers to `departments` with `grant_department_map` (keyed on `financial_year` + `grant_no`, seeded from `GRANT_DEPARTMENT_MAP` in `database/seeds.py`). 19 of the 36 grants match a tracker department; the other 17 (e.g. Planning, Law, Irrigation and Flood Control, Housing and Urban Development) stay unmapped and are shown under their official name. `tests/test_grant_department_map.py` checks each mapped grant's name against every year's PDF. **Open:** decide whether the tracker's department list should become the 36 official grants (the seeded 20 are not from an official source).
- [x] Loader `backend/loaders/appropriation_accounts.py`: download → parse and validate → save to `raw_snapshots/appropriation_accounts/<sha256>.pdf` → replace that year's rows in one transaction. Reloading the same file changes nothing; a reissued file replaces the year's rows and keeps the old snapshot record. Run with `docker compose exec api python -m loaders.appropriation_accounts --all`. Loaded 2021-22 (73 rows), 2022-23 (75) and 2023-24 (77) on 2026-11-22; the SHA-256 of each download matched `SOURCES.md`.
- [ ] Run the loader on a schedule (monthly is enough) so a newly published year or a reissued PDF gets picked up, and record each run in `data_sync_log`.
- [ ] Go back further: 2020-21 (listed at https://saiindia.gov.in/uploads/state_accounts_report/account-report-Appropriation-2020-21-English-UT-J-K-062fdbe90c04c34-62439162.pdf; saiindia.gov.in timed out on 2026-11-22, but the same path on cag.gov.in worked for 2021-22, so try that), then 2019-20, which was published as a combined "UT J&K and Ladakh" account and must be labelled as such (see 2.6). Add a fixture + test for each year before loading it.
- [ ] Add 2024-25 when the CAG publishes it, with a new fixture; expect small layout changes.
- [ ] Net expenditure: the Appropriation Accounts are gross. The reconciliation table right after the summary (and Finance Accounts Statement 11) gives recoveries and net totals; parse it if the dashboard shows net spend.
- [ ] Budget Estimates are still needed for the current year, from the J&K budget documents (source not yet checked). Replace the seed allocations in `database/seeds.py` with them. Line 61 says the seeds are "scaled down by ~10% for demonstration", so they are made up. Cite each figure.
- [ ] Monthly spending: a published monthly accounts source for J&K (CGA or the Accountant General) is not yet found. Until it is, remove `CGACollector._run_fallback_simulation` (it invents numbers) and show "No data" for monthly spend.

**Done when:** every past-year department figure shown on the dashboard comes from `appropriation_account_lines` with a link to its snapshot and page, the parser tests pass on at least 3 saved PDFs (✅ 2026-11-22), and the current-year Budget Estimates in `budget_allocations` each cite an official document.

### 2.2a Three views: Live, Official, Combined
Agreed 2026-11-22. The dashboard offers three views of the same figures:

| View | Source | Best for |
|---|---|---|
| **Live** | Portal collectors (JJM, MGNREGA, PMAY, DBT, tenders) | Current year, district and scheme detail. Provisional. |
| **Official** | CAG PDFs (Appropriation Accounts now; Finance Accounts and audit reports later) | Past years, audited department totals with a page reference. |
| **Combined** (default) | Worked out from the two above at query time, never stored | One complete timeline for citizens. |

Rules for Combined:
1. A closed year covered by a CAG PDF shows the **PDF figure**.
2. The current year, or a year the CAG hasn't published yet, shows the live figure, labelled "provisional".
3. If both exist and differ by more than 2%, show the **PDF figure with a flag**: "Portal said ₹X, audited accounts say ₹Y". (Decided: PDF + flag, not both side by side.)
4. If neither exists, show "No data", never 0.

Every figure carries its source label, e.g. "Official · Appropriation Accounts 2022-23, p.4" or "Live · ejalshakti.gov.in, fetched 22 Nov".

- [x] **Step 1: official data in the database.** Tables, grant → department mapping and loader for the three parsed years (see 2.2).
- [x] **Step 2: API.** Add `?view=live|official|combined` (default `combined`) to the budget, department and scheme routes in `backend/api/routes/`. Put the Combined rules and the 2% threshold in one module, with tests. Every figure in a response carries `source_type`, `source_url`, `snapshot_id`, `page` and `fetched_at`, and Combined adds `mismatch: {live, official, diff_pct}` when rule 3 applies. Done 2026-11-22:
  - Rules and threshold: `backend/processors/combined_view.py` (pure, tested in `tests/test_combined_view.py`). Query layer: `backend/api/figures.py`. Route tests on the real 2022-23 PDF: `tests/test_view_routes.py`.
  - Responses keep their old scalar fields (so the dashboard keeps working until step 3) and add `view` plus `sources: {field: FigureSource}`. `FigureSource` also has `label`, `measure` (official `budget_estimate_lakhs` is the **final grant**, official `utilized_lakhs` is **gross expenditure**) and `provisional`.
  - Live and official are compared only per department. The UT-wide total in `/budget/overview` is not compared, since the budget table covers only 20 departments and the accounts cover every grant.
  - Missing figures are `null`, not 0, in every route touched (overview, departments, gap analysis, schemes). Gap analysis has a new `gap_flag: "no_data"`.
  - On the current database every 2023-24 department is flagged (live 55–88% below audited), because the seed allocations are made up (see 2.2). That's the flag doing its job.
  - **Open:** the official view lists only the 19 mapped departments. The 17 unmapped grants are counted in the overview total but have no route of their own yet.
- [ ] **Step 3: dashboard.** A Live / Official / Combined switch in the header (kept in the URL so links can be shared) and a source badge on every figure. Flagged figures show both numbers on hover or tap. Also update `frontend/src/lib/api.ts` to match: money fields are now `number | null`, `is_capital` is `boolean | null` (null for official figures, so don't show them as "REVENUE"), and there are new `view`/`sources` fields and a `no_data` gap flag.
- [ ] **Step 4: mismatch page.** List every Live-vs-Official difference above the threshold, next to the Alerts page.
- [ ] Portals report by scheme and the PDFs by department grant, so Combined can only compare them at department level, through `grant_department_map`. Until scheme spending can be added up per grant, show scheme-level figures as Live only.

### 2.3 CAG findings from real reports
- [ ] Download the real J&K audit reports, split them into paragraphs, and keep the page numbers.
- [ ] Use LLM extraction (Claude or Gemini) with a strict JSON schema. Store the **verbatim source paragraph + page number** next to the summary. Set the model in config, not hardcoded (`gemini-2.0-flash` is in `cag_collector.py` today).
- [ ] Check every extracted amount against the source text (the number must appear in the paragraph). Send anything that fails to a review queue; never publish it automatically.
- [ ] Upgrade `google-genai` (pinned at an early `0.3.0`) or switch providers; either way, read the model name from config.

**Done when:** every published finding shows its verbatim paragraph, report title and page number, and no finding with an unverified amount is visible publicly.

### 2.4 Tenders, DBT, PMAY, PFMS
- [ ] For each one, record whether a public, automation-friendly source exists (URL + date checked). If the only route is through a CAPTCHA or login, set the collector to `no_source`, hide the page or show "source unavailable", and note the alternative being pursued (published reports, RTI).
- [ ] Bring back the contractor leaderboard only with real award data, and name a contractor only when an official award notice is linked.

**Done when:** each of the four has a recorded status (live / `no_source`, with URL and date checked), and no page shows data for a `no_source` collector.

### 2.5 Remove hardcoded dates
- [ ] Work out the current financial year (April–March) instead of defaulting to `"2024-25"` (`api/routes/budget.py`, `alerts.py`, `dbt.py`, `pmay_collector.py`, `cga_collector.py`, …).
- [ ] Add a financial-year selector in the UI, populated from the years that actually have data.
- [ ] Fix `/schemes/{id}/history` returning `days_elapsed: 965` for a year that has already ended.

**Done when:** `grep -rn '"2024-25"' backend frontend/src` returns nothing outside tests and fixtures, and `days_elapsed` never exceeds the length of the financial year.

### 2.6 One canonical list of districts
Each portal spells districts differently (e.g. Budgam/Badgam, Shopian/Shupiyan, Bandipora/Bandipore). Data from before 31 Oct 2019 also includes Ladakh (Leh, Kargil), which is now a separate UT. Without a mapping, joins across sources quietly drop rows.
- [ ] Add a `district_aliases` table (alias → `district_id`, source) and resolve every scraped name through it in `data_cleaner.py`.
- [ ] Unknown names fail loudly: the row is skipped, and the name is logged and shown on the sync-status page so someone can add an alias.
- [ ] Exclude Leh/Kargil from J&K totals, or label them as historical, for years before 2019-20.

**Done when:** parser tests cover every alias seen in the saved fixtures, and no collector run logs an unmapped district without it showing up on the sync-status page.

### 2.7 Fallback plan if sources stay unavailable
Phase 2 depends on outside portals, and some may have no automation-friendly source at all.
- [ ] After 2.1–2.4, write down which sources are live. The 9/10 bar is **"every number shown is real, traceable and honestly labelled"**, not "all 8 collectors live".
- [ ] Minimum for a 9: at least three live sources with snapshots (e.g. JJM + budget documents + CAG). Every other source is shown as "source unavailable", with the reason and the alternative being pursued (published reports, RTI).

---

## Phase 3 — Production-grade backend (7.5 → 8.5)

### 3.1 Schema migrations
- [ ] Set up Alembic (it's already in `requirements.txt`, but there's no `alembic/` folder) and write a baseline migration from `database/models.py`. Replace `init_db()`'s `create_all` with `alembic upgrade head`.

**Done when:** a fresh database built by `alembic upgrade head` matches the models (`alembic check` reports no differences), and `create_all` is gone from startup.

### 3.2 Security
- [ ] Protect `POST /alerts/trigger/{name}` and `/alerts/trigger-all` with an admin API key or token. Right now anyone can make the server launch 8 headless Chromium browsers.
- [ ] Rate-limit public endpoints (e.g. `slowapi`) and cache read endpoints in Redis. Redis already runs but is barely used; the `cache_ttl_*` settings exist.
- [ ] Remove default secrets. Fail at startup if `SECRET_KEY` is the default value outside development. Move CORS origins into config.
- [ ] Run Playwright collectors in a separate worker process or container, not in the API's `BackgroundTasks`, so a hung browser can't take down the API. This also fixes the blocking sync `httpx.Client` and sync DB sessions that currently run inside the async app.

**Done when:** unauthenticated trigger calls return 401, burst requests get 429, the API refuses to start with the default `SECRET_KEY` outside development, and killing the worker mid-collection leaves the API responding.

### 3.3 Reliability
- [ ] Make collector writes idempotent (upsert on natural keys), with retries + backoff (`tenacity` is already a dependency) and a per-collector timeout.
- [ ] Use a scheduler job store (APScheduler + Postgres) so jobs aren't duplicated when there's more than one API replica.
- [ ] Use structured JSON logs (loguru `serialize=True`) and add `/health/ready`, which checks the database, Redis and the last successful run per collector.
- [ ] Send alerts (Telegram/email; the settings already exist in `config.py`) when a collector has failed N runs in a row or data is older than its SLA.

**Done when:** running a collector twice in a row inserts no duplicate rows, `/health/ready` returns 503 when Postgres is down, and a forced failure streak sends an alert.

### 3.4 Deployment and operations
A transparency tool earns a 9 only if citizens can actually reach it.
- [ ] Pick a host and deploy the frontend, API, worker, Postgres and Redis with HTTPS and a real domain.
- [ ] Back up Postgres every night and keep backups off the host, for at least 30 days. Test a restore once and write down the steps.
- [ ] Choose durable storage for `raw_snapshots` (object storage, not the container disk) and a retention policy. Snapshots that back published figures are never deleted.
- [ ] Add a public status page, or a `/status` route, that shows each collector's last success.

**Done when:** the public URL serves the dashboard over HTTPS, and a documented restore from last night's backup has been carried out successfully.

---

## Phase 4 — Tests and CI (8.5 → 9)

### 4.1 Backend tests (`pytest`)
- [ ] **Parser tests:** saved real HTML/JSON/PDF fixtures → expected rows, one file per collector. Started: `tests/test_appropriation_accounts.py` (3 real PDFs). `pytest` runs from `backend/` (`pytest.ini` sets the import path), and CI has a `backend-tests` job that installs only `pdfplumber`, `sqlalchemy` and `pytest` for now. Loader tests use in-memory SQLite: `tests/test_appropriation_loader.py`, `tests/test_grant_department_map.py`.
- [ ] **API tests:** `httpx.AsyncClient` against a test Postgres (testcontainers or the compose service), covering every route: happy path, 404, 422, empty data, and null-vs-zero handling.
- [ ] **Processor tests:** `gap_calculator.py` and `data_cleaner.py`, including edge cases (zero allocation, missing release, future dates).
- [ ] Coverage ≥ 80% on `api/`, `processors/` and collector parsers.

### 4.2 Frontend tests
- [ ] Vitest + React Testing Library on the formatters (`fmtLakhs`, `fmtPct`) and on the loading / error / empty states of each page.
- [ ] One Playwright e2e smoke test: the stack boots, and every nav route renders with no console errors.

### 4.3 CI (GitHub Actions)
- [ ] On every PR: `ruff` + `mypy` (backend), `tsc --noEmit` + `eslint` (frontend), pytest, vitest, a docker-compose build, and the e2e smoke test.
- [ ] Block merges on a red build. Add a `pre-commit` config so the same checks run locally.

**Done when:** branch protection on `main` requires the CI workflow, and the coverage report shows ≥ 80% on the targeted modules.

---

## Phase 5 — The polish that earns a 9+

### 5.1 Data-verification page for citizens
- [ ] Turn `How to Verify Dashboard Data is Correct.md` into an in-app `/methodology` page: where each number comes from, how gaps are calculated, known limitations, and a link to the raw snapshot for every figure.
- [ ] A "Report an error" link on each figure (opens a pre-filled GitHub issue).

**Done when:** `/methodology` exists and links to it from every page footer, and every figure has a working "Report an error" link.

### 5.2 UX and accessibility
- [ ] Responsive layout down to 360px, keyboard navigation, alt text / table alternatives for charts and the map, and WCAG AA contrast.
- [ ] Shareable URLs. Filters (year, district, scheme) live in the query string.
- [ ] Hindi/Urdu labels (i18n) for the main pages. (Polish beyond 9; do it last.)

**Done when:** Lighthouse accessibility ≥ 95 on every route, every page works at 360px with no horizontal scroll, and reloading a filtered URL restores the same view.

### 5.3 Open data
- [ ] Keep CSV/ZIP export, and add a licence + data dictionary file to every export.
- [ ] Publish a versioned public API with documented fields and units (all money in ₹ lakhs, stated explicitly). (Polish beyond 9.)
- [ ] State the licence of each source's data (e.g. GODL-India for data.gov.in), with a source URL, before republishing it.

**Done when:** every export ZIP contains `LICENSE` and `DATA_DICTIONARY.md`, and every money field in `/openapi.json` states its unit.

### 5.4 Docs and hygiene
- [ ] Rewrite `README.md`: architecture diagram, an honest table of each data source's status (live / no source / failing), how to add a collector, how to run tests.
- [ ] Fold `Project.md` into the README or `docs/`, and keep this file as the single roadmap.
- [ ] Add a `LICENSE` and `CONTRIBUTING.md`, and use descriptive commit messages (recent history is "fixing lots of bugs and enhancements" ×3).

**Done when:** a new contributor can go from clone to a running stack and a passing test suite using only `README.md`.

---

## Scorecard

| Area | Now | Target | Phases |
|---|---|---|---|
| Runs from a fresh clone | ✗ (frontend broken) | ✓ | 0 |
| Data is real and traceable | ✗ (6/8 collectors produce random data, no provenance columns) | ✓ | 1, 2 |
| Honest status and freshness | ✗ | ✓ | 1 |
| Migrations / security / reliability | ✗ | ✓ | 3 |
| Publicly deployed with backups | ✗ | ✓ | 3.4 |
| Tests + CI | 0 tests, no CI | ≥ 80% coverage, gated CI | 0.3, 4 |
| Methodology, a11y, open data | partial | ✓ | 5 |

Phases 0–1 alone get the project to about **6**. A **9** needs at least three sources live with snapshots (2.1 + 2.2 + 2.3, or the fallback in 2.7), plus Phases 3 and 4, including deployment (3.4). Phase 5 makes it trustworthy enough to share publicly.
