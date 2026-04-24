# Future Roadmap & Pending Features

Here is a detailed breakdown of the remaining high-impact features for the J&K Public Money Flow Tracker. These represent the next major phases of development.

---

### 1. Tender & DBT Dedicated UI (Frontend)
**What to do:**
Currently, our backend collects data for public works tenders (`jktenders.gov.in`) and Direct Benefit Transfers (`dbtbharat.gov.in`), and we allow exporting this data as CSVs. However, there is no visual dashboard for this data.
*   **Tenders Page (`/tenders`)**: Build a dedicated data table showing recent tenders, their estimated vs. awarded costs, and status. Add a "Contractor Leaderboard" chart to visualize which contractors are winning the most government money, highlighting potential monopolies or concentration of public funds.
*   **DBT Page (`/dbt`)**: Build a page focusing on the "Last Mile Gap." Visualize the gap between the number of beneficiaries enrolled in a scheme vs. those who actually received money in their bank accounts, broken down by district.

---

### 2. Budget / CGA Collector (Backend Data Pipeline)
**What to do:**
Currently, the macro budget data (total department allocations and expenditures) relies on seed/mock data. To make it real-time, we need to build a complex collector.
*   **Automated PDF Downloading**: Write a Python script to monitor `cga.nic.in` (Controller General of Accounts) for the monthly J&K expenditure PDF uploads.
*   **PDF Extraction**: Use libraries like `pdfplumber` or `tabula-py` to parse the tabular data inside these PDFs, extracting the actual month-by-month spending for every department (PWD, Health, Education, etc.).
*   **Integration**: Feed this extracted data into the `budget_allocations` and `expenditures` tables so the dashboard's macro numbers update automatically every month.

---

### 3. CAG Audit Alert Feed (AI Integration)
**What to do:**
The Comptroller and Auditor General (CAG) publishes massive 300+ page audit reports detailing financial irregularities, unspent funds, and corruption in J&K. These are buried in PDFs and hard for citizens to read.
*   **PDF Parsing**: Automatically download new CAG reports for J&K.
*   **AI Summarization**: Pass the raw text paragraphs to the Claude API (or Gemini API) with a prompt to extract the specific department involved, the amount of money flagged (in Lakhs), and a 2-sentence plain English summary of the irregularity.
*   **Frontend Feed**: Create a Twitter-style "Audit Feed" on the Alerts page, tagging departments with severity badges (High/Medium/Low) based on the AI's classification.

---

### 4. Overview Sankey Diagram (Data Visualization)
**What to do:**
The current Overview page shows static numbers in cards. A Sankey Diagram is the industry standard for visualizing money flow.
*   **Integration**: Use `recharts` or a specialized library like `react-sankey` or `nivo` to build an interactive diagram on the `/` (Overview) page.
*   **Flow Mapping**: Visually map the flow of funds: `Central Govt / J&K Tax Revenue` (Left side) → `J&K Finance Dept` (Middle) → `Line Departments` (Right side).
*   **Interactivity**: Allow the user to hover over the thick bands of the diagram to see exactly what percentage of the UT budget is consumed by specific sectors (e.g., Security vs. Education vs. Infrastructure).

---

### 5. PFMS Collector (Advanced Backend Pipeline)
**What to do:**
The Public Financial Management System (PFMS) is the central nodal agency for releasing scheme funds. Currently, we track when money reaches the ground (via MGNREGA/JJM portals), but not when it leaves Delhi.
*   **Scraping PFMS**: Build a scraper (likely using Playwright due to complex JS/Captcha mechanics on `pfms.nic.in`) to track the exact date and amount of Central Sector funds released to J&K implementing agencies.
*   **Gap Analysis**: This allows us to calculate the ultimate gap metric: *Central Release → State Receipt → Actual Utilization*. This explicitly highlights where money is parked idle in nodal bank accounts.
